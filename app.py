#!/usr/bin/env python3
"""
MPD to HLS Streaming Server
支持MPD视频流通过Internal remuxer转换为HLS推流
"""

import os
import json
import yaml
import asyncio
import aiohttp
from aiohttp import web, ClientSession
import logging
from pathlib import Path
import subprocess
import tempfile
import shutil
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET
import base64
import binascii
from typing import Dict, List, Optional
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MPDToHLSStreamer:
    def __init__(self, config_path: str = None):
        # 使用环境变量或默认路径
        if config_path is None:
            config_path = os.getenv('CONFIG_PATH', '/app/config/config.yaml')
        self.config_path = config_path
        self.config = self.load_config()
        self.temp_dir = tempfile.mkdtemp()
        self.sessions: Dict[str, dict] = {}
        self.active_streams: Dict[str, dict] = {}  # 记录活跃的流状态
        logger.info(f"初始化MPD转HLS流媒体服务器，临时目录: {self.temp_dir}")
        logger.info(f"配置文件路径: {self.config_path}")

    def load_config(self) -> dict:
        """加载配置文件，如果不存在则创建默认配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"已加载配置文件: {self.config_path}")
            return config
        except FileNotFoundError:
            logger.info(f"配置文件 {self.config_path} 不存在，正在创建默认配置文件...")
            default_config = self.get_default_config()
            self.save_default_config(default_config)
            return default_config
        except Exception as e:
            logger.error(f"加载配置文件时出错: {e}")
            logger.info("使用默认配置")
            return self.get_default_config()

    def save_default_config(self, config: dict):
        """保存默认配置到文件"""
        try:
            # 确保配置目录存在
            config_dir = Path(self.config_path).parent
            config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
            logger.info(f"已创建默认配置文件: {self.config_path}")
        except Exception as e:
            logger.error(f"创建配置文件时出错: {e}")
            logger.info("继续使用内存中的默认配置")

    def save_config(self):
        """保存当前配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, indent=2)
            logger.info(f"配置已保存到: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件时出错: {e}")
            return False

    def get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            'server': {
                'host': '0.0.0.0',
                'port': 8080
            },
            'streams': [
                {
                    'id': 'example_stream_1',
                    'name': '示例MPD流1',
                    'url': 'https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd',
                    'manifest_type': 'mpd',
                    'license_type': 'clearkey',
                    'license_key': 'example_key_id:example_key_value',
                    'active': False
                },
                {
                    'id': 'example_stream_2', 
                    'name': '示例MPD流2',
                    'url': 'https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.mpd',
                    'manifest_type': 'mpd',
                    'license_type': 'none',
                    'license_key': '',
                    'active': False
                }
            ],
            'ffmpeg': {
                'hls_time': 6,
                'hls_list_size': 10,
                'hls_flags': 'delete_segments',
                'video_codec': 'libx264',
                'audio_codec': 'aac'
            }
        }

    def parse_kodi_props(self, stream_text: str) -> dict:
        """解析Kodi属性格式的流信息"""
        lines = stream_text.strip().split('\n')
        props = {}
        url = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('#KODIPROP:'):
                # 解析属性
                prop_part = line[len('#KODIPROP:'):]
                if '=' in prop_part:
                    key, value = prop_part.split('=', 1)
                    props[key] = value
            elif line.startswith('http'):
                url = line
        
        return {
            'url': url,
            'manifest_type': props.get('inputstream.adaptive.manifest_type'),
            'license_type': props.get('inputstream.adaptive.license_type'),
            'license_key': props.get('inputstream.adaptive.license_key')
        }

    async def fetch_mpd(self, url: str, headers: dict = None) -> str:
        """获取MPD清单文件"""
        async with ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    raise Exception(f"无法获取MPD文件: {response.status}")

    def parse_clearkey_license(self, license_key: str) -> Dict[str, str]:
        """解析ClearKey许可证"""
        if ':' in license_key:
            key_id, key = license_key.split(':', 1)
            return {
                'key_id': key_id,
                'key': key
            }
        return {}

    async def create_hls_stream(self, stream_id: str, mpd_url: str, 
                              license_key: str = None) -> str:
        """创建HLS流"""
        output_dir = os.path.join(self.temp_dir, stream_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # FFmpeg命令构建
        cmd = [
            'ffmpeg',
            '-i', mpd_url,
            '-c:v', self.config['ffmpeg']['video_codec'],
            '-c:a', self.config['ffmpeg']['audio_codec'],
            '-f', 'hls',
            '-hls_time', str(self.config['ffmpeg']['hls_time']),
            '-hls_list_size', str(self.config['ffmpeg']['hls_list_size']),
            '-hls_flags', self.config['ffmpeg']['hls_flags'],
            '-hls_segment_filename', os.path.join(output_dir, 'segment_%03d.ts'),
            os.path.join(output_dir, 'playlist.m3u8')
        ]

        # 如果有ClearKey许可证，添加解密参数
        if license_key:
            clearkey = self.parse_clearkey_license(license_key)
            if clearkey:
                # 添加解密密钥
                cmd.extend(['-decryption_key', clearkey['key']])

        logger.info(f"启动FFmpeg进程: {' '.join(cmd)}")
        
        # 启动FFmpeg进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # 保存会话信息
        self.sessions[stream_id] = {
            'process': process,
            'output_dir': output_dir,
            'created_at': time.time(),
            'status': 'starting'
        }
        
        # 更新活跃流状态
        self.active_streams[stream_id] = {
            'status': 'running',
            'started_at': time.time(),
            'mpd_url': mpd_url,
            'license_key': license_key
        }

        return os.path.join(output_dir, 'playlist.m3u8')

    async def handle_stream_request(self, request):
        """处理流请求"""
        stream_id = request.match_info['stream_id']
        
        # 检查流是否存在于配置中
        stream_config = None
        for stream in self.config['streams']:
            if stream['id'] == stream_id:
                stream_config = stream
                break
        
        if not stream_config:
            return web.Response(text="流不存在", status=404)

        try:
            # 创建HLS流
            playlist_path = await self.create_hls_stream(
                stream_id,
                stream_config['url'],
                stream_config.get('license_key')
            )

            # 等待播放列表文件生成
            for _ in range(30):  # 等待最多30秒
                if os.path.exists(playlist_path):
                    break
                await asyncio.sleep(1)
            else:
                return web.Response(text="流生成超时", status=500)

            # 返回播放列表
            with open(playlist_path, 'r') as f:
                playlist_content = f.read()

            return web.Response(
                text=playlist_content,
                content_type='application/vnd.apple.mpegurl',
                headers={'Access-Control-Allow-Origin': '*'}
            )

        except Exception as e:
            logger.error(f"处理流请求失败: {e}")
            return web.Response(text=f"内部错误: {str(e)}", status=500)

    async def handle_segment_request(self, request):
        """处理段文件请求"""
        stream_id = request.match_info['stream_id']
        segment_name = request.match_info['segment']
        
        if stream_id not in self.sessions:
            return web.Response(text="流不存在", status=404)
        
        segment_path = os.path.join(
            self.sessions[stream_id]['output_dir'],
            segment_name
        )
        
        if not os.path.exists(segment_path):
            return web.Response(text="段文件不存在", status=404)
        
        # 返回段文件
        with open(segment_path, 'rb') as f:
            content = f.read()
        
        return web.Response(
            body=content,
            content_type='video/MP2T',
            headers={'Access-Control-Allow-Origin': '*'}
        )

    async def handle_add_stream(self, request):
        """处理添加流的API请求"""
        try:
            data = await request.json()
            
            # 解析流数据
            if 'kodi_format' in data:
                stream_info = self.parse_kodi_props(data['kodi_format'])
            else:
                stream_info = data
            
            # 生成流ID
            stream_id = f"stream_{len(self.config['streams']) + 1}"
            
            # 添加到配置
            new_stream = {
                'id': stream_id,
                'name': data.get('name', f'Stream {stream_id}'),
                'url': stream_info['url'],
                'license_key': stream_info.get('license_key'),
                'manifest_type': stream_info.get('manifest_type', 'mpd'),
                'license_type': stream_info.get('license_type')
            }
            
            self.config['streams'].append(new_stream)
            
            # 保存配置
            self.save_config()
            
            return web.json_response({
                'success': True,
                'stream_id': stream_id,
                'hls_url': f'/stream/{stream_id}/playlist.m3u8'
            })
            
        except Exception as e:
            logger.error(f"添加流失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=400)

    async def handle_update_stream(self, request):
        """更新流配置"""
        stream_id = request.match_info['stream_id']
        
        try:
            data = await request.json()
            
            # 查找并更新流配置
            for i, stream in enumerate(self.config['streams']):
                if stream['id'] == stream_id:
                    # 更新配置
                    self.config['streams'][i].update({
                        'name': data.get('name', stream['name']),
                        'url': data.get('url', stream['url']),
                        'license_key': data.get('license_key', stream.get('license_key')),
                        'license_type': data.get('license_type', stream.get('license_type')),
                        'manifest_type': data.get('manifest_type', stream.get('manifest_type')),
                        'enabled': data.get('enabled', stream.get('enabled', True))
                    })
                    
                    # 保存配置
                    self.save_config()
                    
                    return web.json_response({'success': True})
            
            return web.json_response({'success': False, 'error': '流不存在'}, status=404)
            
        except Exception as e:
            logger.error(f"更新流失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=400)

    async def handle_delete_stream(self, request):
        """删除流配置"""
        stream_id = request.match_info['stream_id']
        
        try:
            # 首先停止流（如果正在运行）
            if stream_id in self.sessions:
                self.cleanup_session(stream_id)
            
            # 从配置中删除
            original_count = len(self.config['streams'])
            self.config['streams'] = [s for s in self.config['streams'] if s['id'] != stream_id]
            
            if len(self.config['streams']) < original_count:
                # 保存配置
                self.save_config()
                
                # 从活跃流中删除
                if stream_id in self.active_streams:
                    del self.active_streams[stream_id]
                
                return web.json_response({'success': True})
            else:
                return web.json_response({'success': False, 'error': '流不存在'}, status=404)
                
        except Exception as e:
            logger.error(f"删除流失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=400)

    async def handle_start_stream(self, request):
        """启动流"""
        stream_id = request.match_info['stream_id']
        
        # 检查流配置是否存在
        stream_config = None
        for stream in self.config['streams']:
            if stream['id'] == stream_id:
                stream_config = stream
                break
        
        if not stream_config:
            return web.json_response({'success': False, 'error': '流不存在'}, status=404)
        
        if not stream_config.get('enabled', True):
            return web.json_response({'success': False, 'error': '流已被禁用'}, status=400)
        
        # 检查是否已经在运行
        if stream_id in self.sessions:
            return web.json_response({'success': False, 'error': '流已在运行'}, status=400)
        
        try:
            # 启动流
            await self.create_hls_stream(
                stream_id,
                stream_config['url'],
                stream_config.get('license_key')
            )
            
            return web.json_response({
                'success': True,
                'message': '流启动成功',
                'hls_url': f'/stream/{stream_id}/playlist.m3u8'
            })
            
        except Exception as e:
            logger.error(f"启动流失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def handle_stop_stream(self, request):
        """停止流"""
        stream_id = request.match_info['stream_id']
        
        if stream_id not in self.sessions:
            return web.json_response({'success': False, 'error': '流未运行'}, status=400)
        
        try:
            # 停止流
            self.cleanup_session(stream_id)
            
            # 从活跃流中删除
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
            
            return web.json_response({
                'success': True,
                'message': '流停止成功'
            })
            
        except Exception as e:
            logger.error(f"停止流失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def handle_get_stream_status(self, request):
        """获取流状态"""
        stream_id = request.match_info['stream_id']
        
        # 检查流配置是否存在
        stream_config = None
        for stream in self.config['streams']:
            if stream['id'] == stream_id:
                stream_config = stream
                break
        
        if not stream_config:
            return web.json_response({'success': False, 'error': '流不存在'}, status=404)
        
        session_info = self.sessions.get(stream_id, {})
        active_info = self.active_streams.get(stream_id, {})
        
        status = {
            'id': stream_id,
            'name': stream_config['name'],
            'enabled': stream_config.get('enabled', True),
            'running': stream_id in self.sessions,
            'status': active_info.get('status', 'stopped'),
            'started_at': active_info.get('started_at'),
            'uptime': time.time() - active_info.get('started_at', time.time()) if active_info.get('started_at') else 0,
            'hls_url': f'/stream/{stream_id}/playlist.m3u8' if stream_id in self.sessions else None
        }
        
        return web.json_response(status)

    async def handle_list_streams(self, request):
        """列出所有流"""
        streams = []
        for stream in self.config['streams']:
            stream_status = self.active_streams.get(stream['id'], {})
            streams.append({
                'id': stream['id'],
                'name': stream['name'],
                'url': stream['url'],
                'license_type': stream.get('license_type'),
                'manifest_type': stream.get('manifest_type'),
                'hls_url': f'/stream/{stream["id"]}/playlist.m3u8',
                'status': stream_status.get('status', 'stopped'),
                'started_at': stream_status.get('started_at'),
                'enabled': stream.get('enabled', True)
            })
        
        return web.json_response({'streams': streams})

    async def handle_health_check(self, request):
        """健康检查"""
        return web.json_response({
            'status': 'healthy',
            'active_streams': len(self.sessions),
            'timestamp': time.time()
        })

    def cleanup_old_sessions(self):
        """清理旧会话"""
        current_time = time.time()
        expired_sessions = []
        
        for stream_id, session in self.sessions.items():
            # 如果会话超过1小时未使用，则清理
            if current_time - session['created_at'] > 3600:
                expired_sessions.append(stream_id)
        
        for stream_id in expired_sessions:
            self.cleanup_session(stream_id)

    def cleanup_session(self, stream_id: str):
        """清理指定会话"""
        if stream_id in self.sessions:
            session = self.sessions[stream_id]
            
            # 终止FFmpeg进程
            if session['process'].poll() is None:
                session['process'].terminate()
                session['process'].wait()
            
            # 清理临时文件
            if os.path.exists(session['output_dir']):
                shutil.rmtree(session['output_dir'])
            
            del self.sessions[stream_id]
            logger.info(f"已清理会话: {stream_id}")

    def create_app(self):
        """创建Web应用"""
        app = web.Application()
        
        # 路由配置
        app.router.add_get('/health', self.handle_health_check)
        app.router.add_get('/streams', self.handle_list_streams)
        app.router.add_post('/streams', self.handle_add_stream)
        app.router.add_put('/streams/{stream_id}', self.handle_update_stream)
        app.router.add_delete('/streams/{stream_id}', self.handle_delete_stream)
        app.router.add_post('/streams/{stream_id}/start', self.handle_start_stream)
        app.router.add_post('/streams/{stream_id}/stop', self.handle_stop_stream)
        app.router.add_get('/streams/{stream_id}/status', self.handle_get_stream_status)
        app.router.add_get('/stream/{stream_id}/playlist.m3u8', self.handle_stream_request)
        app.router.add_get('/stream/{stream_id}/{segment}', self.handle_segment_request)
        
        # 静态文件服务（如果需要Web界面）
        app.router.add_static('/', path='static', name='static')
        
        # 根路径重定向到演示页面
        async def redirect_to_demo(request):
            return web.HTTPFound('/demo.html')
        
        app.router.add_get('/', redirect_to_demo)
        
        return app

    def run(self):
        """运行服务器"""
        app = self.create_app()
        
        logger.info(f"启动MPD转HLS流媒体服务器...")
        logger.info(f"服务器地址: http://{self.config['server']['host']}:{self.config['server']['port']}")
        
        web.run_app(
            app,
            host=self.config['server']['host'],
            port=self.config['server']['port']
        )

    def __del__(self):
        """清理资源"""
        try:
            # 清理所有会话
            for stream_id in list(self.sessions.keys()):
                self.cleanup_session(stream_id)
            
            # 清理临时目录
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except:
            pass

if __name__ == '__main__':
    streamer = MPDToHLSStreamer()
    streamer.run()
