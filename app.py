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
import time
import requests
from typing import Dict, List, Optional
import binascii
from typing import Dict, List, Optional
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DashDecryptor:
    """DASH流解密器 - 支持ClearKey解密"""
    
    def __init__(self):
        self.tools = self._detect_tools()
        self.clearkey_script = self._find_clearkey_script()
        logger.info(f"解密工具检测完成: {[k for k, v in self.tools.items() if v]}")
        if self.clearkey_script:
            logger.info(f"找到ClearKey解密脚本: {self.clearkey_script}")
    
    def _detect_tools(self) -> Dict[str, bool]:
        """检测可用的解密工具"""
        tools = {}
        for tool in ['yt-dlp', 'youtube-dl', 'ffmpeg']:
            try:
                result = subprocess.run([tool, '--version'], 
                                      capture_output=True, timeout=5)
                tools[tool] = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                tools[tool] = False
        return tools
    
    def _find_clearkey_script(self) -> Optional[str]:
        """查找ClearKey解密脚本"""
        script_name = 'clearkey_decrypt.py'
        
        # 在当前目录查找
        current_dir_script = os.path.join(os.getcwd(), script_name)
        if os.path.exists(current_dir_script):
            return current_dir_script
        
        # 在脚本同目录查找
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, script_name)
        if os.path.exists(script_path):
            return script_path
        
        return None
    
    async def decrypt_with_yt_dlp(self, mpd_url: str, output_dir: str, 
                                license_key: str = None) -> Optional[str]:
        """使用yt-dlp解密DASH流"""
        if not self.tools.get('yt-dlp'):
            logger.warning("yt-dlp不可用，尝试其他方法")
            return None
        
        try:
            temp_output = os.path.join(output_dir, 'temp_video')
            
            # 构建yt-dlp命令
            cmd = [
                'yt-dlp',
                '--no-playlist',
                '--format', 'best[ext=mp4]/best',
                '--output', f'{temp_output}.%(ext)s',
                '--no-warnings'
            ]
            
            # 如果有ClearKey许可证
            if license_key and ':' in license_key:
                key_id, key = license_key.split(':', 1)
                # yt-dlp的ClearKey格式
                cmd.extend([
                    '--external-downloader', 'ffmpeg',
                    '--external-downloader-args', f'-decryption_key {key}'
                ])
            
            cmd.append(mpd_url)
            
            logger.info(f"执行yt-dlp解密: {mpd_url}")
            
            # 异步执行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # 查找生成的文件
                for ext in ['mp4', 'mkv', 'webm']:
                    potential_file = f'{temp_output}.{ext}'
                    if os.path.exists(potential_file):
                        logger.info(f"yt-dlp解密成功: {potential_file}")
                        return potential_file
                
                logger.error("yt-dlp执行成功但找不到输出文件")
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"yt-dlp解密失败: {error_msg}")
            
            return None
            
        except Exception as e:
            logger.error(f"yt-dlp解密异常: {e}")
            return None
    
    async def decrypt_with_standalone(self, mpd_url: str, output_dir: str, 
                                    license_key: str = None) -> Optional[str]:
        """使用独立的ClearKey解密脚本解密DASH流"""
        if not self.clearkey_script:
            logger.warning("ClearKey解密脚本不可用")
            return None
        
        if not license_key:
            logger.warning("缺少ClearKey许可证")
            return None
        
        try:
            logger.info(f"使用独立ClearKey解密器: {mpd_url}")
            
            # 创建临时输出目录
            decrypt_output_dir = os.path.join(output_dir, 'clearkey_temp')
            os.makedirs(decrypt_output_dir, exist_ok=True)
            
            # 执行解密脚本
            cmd = [
                'python3', self.clearkey_script,
                mpd_url,
                '--license-key', license_key,
                '--output-dir', decrypt_output_dir,
                '--method', 'auto'
            ]
            
            logger.debug(f"执行命令: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # 查找生成的文件
                output_files = []
                for root, dirs, files in os.walk(decrypt_output_dir):
                    for file in files:
                        if file.endswith(('.mp4', '.mkv', '.webm')):
                            output_files.append(os.path.join(root, file))
                
                if output_files:
                    # 返回第一个找到的文件
                    output_file = output_files[0]
                    logger.info(f"独立解密器成功: {output_file}")
                    return output_file
                else:
                    logger.error("独立解密器执行成功但未找到输出文件")
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"独立解密器失败: {error_msg}")
            
            return None
            
        except Exception as e:
            logger.error(f"独立解密器异常: {e}")
            return None
    
    async def decrypt_dash_stream(self, mpd_url: str, output_dir: str, 
                                license_key: str = None, 
                                method: str = 'auto') -> Optional[str]:
        """
        解密DASH流 - 统一入口，支持多种解密方法
        
        Args:
            mpd_url: MPD流地址
            output_dir: 输出目录
            license_key: ClearKey许可证
            method: 解密方法 ('auto', 'yt-dlp', 'standalone')
            
        Returns:
            解密后的视频文件路径，失败时返回None
        """
        if not license_key:
            logger.warning("无ClearKey许可证，跳过解密")
            return None
        
        logger.info(f"开始DASH解密，方法: {method}")
        
        decrypted_file = None
        
        if method in ['auto', 'standalone']:
            # 优先尝试独立解密器
            decrypted_file = await self.decrypt_with_standalone(
                mpd_url, output_dir, license_key
            )
        
        if not decrypted_file and method in ['auto', 'yt-dlp']:
            # 备用yt-dlp
            decrypted_file = await self.decrypt_with_yt_dlp(
                mpd_url, output_dir, license_key
            )
        
        if decrypted_file:
            logger.info(f"DASH解密成功: {decrypted_file}")
        else:
            logger.error("所有解密方法都失败了")
        
        return decrypted_file
    
    async def convert_to_hls(self, input_file: str, output_dir: str, 
                           stream_id: str, hls_config: Dict) -> bool:
        """将解密的视频文件转换为HLS"""
        try:
            playlist_path = os.path.join(output_dir, 'playlist.m3u8')
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-c:v', hls_config.get('video_codec', 'libx264'),
                '-c:a', hls_config.get('audio_codec', 'aac'),
                '-f', 'hls',
                '-hls_time', str(hls_config.get('hls_time', 6)),
                '-hls_list_size', str(hls_config.get('hls_list_size', 10)),
                '-hls_flags', hls_config.get('hls_flags', 'delete_segments'),
                '-hls_segment_filename', os.path.join(output_dir, 'segment_%03d.ts'),
                playlist_path
            ]
            
            logger.info(f"转换为HLS: {stream_id}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(playlist_path):
                logger.info(f"HLS转换成功: {playlist_path}")
                # 删除临时的解密文件
                try:
                    os.remove(input_file)
                except:
                    pass
                return True
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"HLS转换失败: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"HLS转换异常: {e}")
            return False

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
        self.dash_decryptor = DashDecryptor()  # 初始化解密器
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
            # 移除可能的空格和特殊字符
            key_id = key_id.strip()
            key = key.strip()
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
        
        # 如果有ClearKey许可证，尝试先解密DASH流
        input_source = mpd_url
        temp_decrypted_file = None
        
        if license_key:
            logger.info(f"检测到ClearKey许可证，尝试解密DASH流...")
            try:
                # 使用增强的解密器
                temp_decrypted_file = await self.dash_decryptor.decrypt_dash_stream(
                    mpd_url, output_dir, license_key, method='auto'
                )
                
                if temp_decrypted_file:
                    input_source = temp_decrypted_file
                    logger.info(f"DASH解密成功，使用解密后的文件: {temp_decrypted_file}")
                else:
                    logger.warning("DASH解密失败，尝试使用FFmpeg的有限解密支持")
            except Exception as e:
                logger.error(f"DASH解密出错: {e}，回退到FFmpeg")
        
        # 构建FFmpeg命令
        cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出文件
            '-i', input_source,
            '-c:v', self.config['ffmpeg']['video_codec'],
            '-c:a', self.config['ffmpeg']['audio_codec'],
            '-f', 'hls',
            '-hls_time', str(self.config['ffmpeg']['hls_time']),
            '-hls_list_size', str(self.config['ffmpeg']['hls_list_size']),
            '-hls_flags', self.config['ffmpeg']['hls_flags'],
            '-hls_segment_filename', os.path.join(output_dir, 'segment_%03d.ts'),
            os.path.join(output_dir, 'playlist.m3u8')
        ]

        # 如果没有通过外部工具解密成功，且有ClearKey许可证，尝试使用FFmpeg的解密参数
        if license_key and not temp_decrypted_file:
            clearkey = self.parse_clearkey_license(license_key)
            if clearkey:
                # FFmpeg的ClearKey解密参数（有限支持）
                cmd.extend(['-decryption_key', clearkey['key']])
                logger.info(f"使用FFmpeg ClearKey解密: key_id={clearkey['key_id']}, key=***")

        logger.info(f"启动FFmpeg进程: {' '.join(cmd[:10])}... (已隐藏敏感参数)")
        
        try:
            # 启动FFmpeg进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并stderr到stdout
                universal_newlines=True,
                bufsize=1  # 行缓冲
            )

            # 保存会话信息
            self.sessions[stream_id] = {
                'process': process,
                'output_dir': output_dir,
                'created_at': time.time(),
                'status': 'starting',
                'cmd': cmd,
                'restart_count': 0,
                'temp_decrypted_file': temp_decrypted_file  # 记录临时解密文件
            }
            
            # 更新活跃流状态
            self.active_streams[stream_id] = {
                'status': 'starting',
                'started_at': time.time(),
                'mpd_url': mpd_url,
                'license_key': license_key,
                'decryption_used': temp_decrypted_file is not None
            }

            # 异步监控FFmpeg进程
            asyncio.create_task(self._monitor_ffmpeg_process(stream_id))

            return os.path.join(output_dir, 'playlist.m3u8')
            
        except Exception as e:
            logger.error(f"启动FFmpeg失败: {e}")
            # 清理临时解密文件
            if temp_decrypted_file and os.path.exists(temp_decrypted_file):
                try:
                    os.remove(temp_decrypted_file)
                except:
                    pass
            
            # 清理会话
            if stream_id in self.sessions:
                del self.sessions[stream_id]
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
            raise

    async def _monitor_ffmpeg_process(self, stream_id: str):
        """监控FFmpeg进程状态"""
        if stream_id not in self.sessions:
            return
        
        session = self.sessions[stream_id]
        process = session['process']
        max_restarts = 3
        
        try:
            # 等待进程启动
            await asyncio.sleep(2)
            
            # 检查进程状态
            if process.poll() is not None:
                # 进程已退出，读取输出
                stdout, stderr = process.communicate()
                logger.error(f"FFmpeg进程意外退出 (stream_id: {stream_id})")
                logger.error(f"返回码: {process.returncode}")
                if stdout:
                    logger.error(f"标准输出: {stdout}")
                if stderr:
                    logger.error(f"错误输出: {stderr}")
                
                # 更新状态
                if stream_id in self.active_streams:
                    self.active_streams[stream_id]['status'] = 'error'
                session['status'] = 'error'
                
                # 尝试重启（如果重启次数未超限）
                if session.get('restart_count', 0) < max_restarts:
                    session['restart_count'] = session.get('restart_count', 0) + 1
                    logger.info(f"尝试重启FFmpeg进程 (stream_id: {stream_id}, 第{session['restart_count']}次)")
                    await self._restart_ffmpeg_process(stream_id)
                else:
                    logger.error(f"FFmpeg进程重启次数超限，停止重试 (stream_id: {stream_id})")
            else:
                # 进程正在运行，等待一段时间后检查playlist文件
                await asyncio.sleep(5)
                playlist_path = os.path.join(session['output_dir'], 'playlist.m3u8')
                
                if os.path.exists(playlist_path):
                    # 更新状态为运行中
                    if stream_id in self.active_streams:
                        self.active_streams[stream_id]['status'] = 'running'
                    session['status'] = 'running'
                    logger.info(f"FFmpeg流已成功启动 (stream_id: {stream_id})")
                else:
                    logger.warning(f"FFmpeg进程运行但未生成playlist文件 (stream_id: {stream_id})")
                
        except Exception as e:
            logger.error(f"监控FFmpeg进程时出错 (stream_id: {stream_id}): {e}")
    
    async def _restart_ffmpeg_process(self, stream_id: str):
        """重启FFmpeg进程"""
        if stream_id not in self.sessions:
            return
        
        session = self.sessions[stream_id]
        
        # 停止旧进程
        if session['process'].poll() is None:
            session['process'].terminate()
            await asyncio.sleep(1)
            if session['process'].poll() is None:
                session['process'].kill()
        
        # 获取流配置
        stream_config = None
        for stream in self.config['streams']:
            if stream['id'] == stream_id:
                stream_config = stream
                break
        
        if not stream_config:
            logger.error(f"找不到流配置，无法重启 (stream_id: {stream_id})")
            return
        
        try:
            # 重新启动
            await self.create_hls_stream(
                stream_id,
                stream_config['url'],
                stream_config.get('license_key')
            )
        except Exception as e:
            logger.error(f"重启FFmpeg进程失败 (stream_id: {stream_id}): {e}")

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
        
        # 检查FFmpeg进程状态
        process_status = 'stopped'
        process_info = {}
        
        if session_info and 'process' in session_info:
            process = session_info['process']
            if process.poll() is None:
                process_status = 'running'
                process_info = {
                    'pid': process.pid,
                    'cmd': session_info.get('cmd', [])[:5],  # 只显示命令的前几个参数
                }
            else:
                process_status = 'exited'
                process_info = {
                    'returncode': process.returncode,
                    'restart_count': session_info.get('restart_count', 0)
                }
        
        # 检查输出文件
        playlist_exists = False
        segment_count = 0
        if session_info and 'output_dir' in session_info:
            playlist_path = os.path.join(session_info['output_dir'], 'playlist.m3u8')
            playlist_exists = os.path.exists(playlist_path)
            
            # 统计segment文件数量
            if os.path.exists(session_info['output_dir']):
                try:
                    segment_files = [f for f in os.listdir(session_info['output_dir']) if f.endswith('.ts')]
                    segment_count = len(segment_files)
                except:
                    segment_count = 0
        
        status = {
            'id': stream_id,
            'name': stream_config['name'],
            'enabled': stream_config.get('enabled', True),
            'running': stream_id in self.sessions,
            'status': active_info.get('status', 'stopped'),
            'process_status': process_status,
            'process_info': process_info,
            'started_at': active_info.get('started_at'),
            'uptime': time.time() - active_info.get('started_at', time.time()) if active_info.get('started_at') else 0,
            'hls_url': f'/stream/{stream_id}/playlist.m3u8' if stream_id in self.sessions else None,
            'output_info': {
                'playlist_exists': playlist_exists,
                'segment_count': segment_count,
                'output_dir': session_info.get('output_dir') if session_info else None
            }
        }
        
        return web.json_response(status)
    
    async def handle_test_stream(self, request):
        """测试流URL是否可访问"""
        stream_id = request.match_info['stream_id']
        
        # 检查流配置是否存在
        stream_config = None
        for stream in self.config['streams']:
            if stream['id'] == stream_id:
                stream_config = stream
                break
        
        if not stream_config:
            return web.json_response({'success': False, 'error': '流不存在'}, status=404)
        
        try:
            # 测试MPD URL访问
            async with ClientSession() as session:
                async with session.get(stream_config['url'], timeout=10) as response:
                    test_result = {
                        'url': stream_config['url'],
                        'accessible': response.status == 200,
                        'status_code': response.status,
                        'content_type': response.headers.get('content-type', 'unknown'),
                        'content_length': response.headers.get('content-length', 'unknown'),
                        'server': response.headers.get('server', 'unknown')
                    }
                    
                    if response.status == 200:
                        # 读取部分内容检查是否为有效的MPD
                        content_preview = await response.text()
                        test_result['is_mpd'] = 'MPD' in content_preview[:1000]
                        test_result['content_preview'] = content_preview[:200] + '...' if len(content_preview) > 200 else content_preview
                    
                    return web.json_response({'success': True, 'test_result': test_result})
                    
        except Exception as e:
            return web.json_response({
                'success': False, 
                'error': f'测试失败: {str(e)}',
                'test_result': {
                    'url': stream_config['url'],
                    'accessible': False,
                    'error': str(e)
                }
            })

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
        
        # 添加CORS中间件，支持反向代理
        @web.middleware
        async def cors_handler(request, handler):
            response = await handler(request)
            # 添加CORS头部
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            
            # 记录访问日志，便于调试反向代理问题
            client_ip = request.headers.get('X-Forwarded-For', request.headers.get('X-Real-IP', request.remote))
            logger.info(f"访问请求 - IP: {client_ip}, 路径: {request.path}, 方法: {request.method}")
            
            return response
        
        app.middlewares.append(cors_handler)
        
        # 路由配置
        app.router.add_get('/health', self.handle_health_check)
        app.router.add_get('/streams', self.handle_list_streams)
        app.router.add_post('/streams', self.handle_add_stream)
        app.router.add_put('/streams/{stream_id}', self.handle_update_stream)
        app.router.add_delete('/streams/{stream_id}', self.handle_delete_stream)
        app.router.add_post('/streams/{stream_id}/start', self.handle_start_stream)
        app.router.add_post('/streams/{stream_id}/stop', self.handle_stop_stream)
        app.router.add_get('/streams/{stream_id}/status', self.handle_get_stream_status)
        app.router.add_get('/streams/{stream_id}/test', self.handle_test_stream)
        app.router.add_get('/stream/{stream_id}/playlist.m3u8', self.handle_stream_request)
        app.router.add_get('/stream/{stream_id}/{segment}', self.handle_segment_request)
        
        # 根路径处理，支持反向代理（必须在静态文件路由之前）
        async def handle_root(request):
            # 记录根路径访问
            client_ip = request.headers.get('X-Forwarded-For', request.headers.get('X-Real-IP', request.remote))
            logger.info(f"根路径访问 - IP: {client_ip}, User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
            
            # 尝试直接返回demo.html内容，避免重定向问题
            try:
                demo_path = os.path.join('static', 'demo.html')
                if os.path.exists(demo_path):
                    with open(demo_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return web.Response(text=content, content_type='text/html')
                else:
                    # 如果demo.html不存在，返回简单的欢迎页面
                    welcome_html = '''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>MPD流媒体服务</title>
                        <meta charset="utf-8">
                        <style>
                            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                            .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                            h1 { color: #333; }
                            .status { color: #28a745; font-weight: bold; }
                            ul { list-style: none; padding: 0; }
                            li { margin: 10px 0; }
                            a { color: #007bff; text-decoration: none; padding: 8px 15px; border: 1px solid #007bff; border-radius: 5px; display: inline-block; }
                            a:hover { background: #007bff; color: white; }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>🎬 MPD到HLS流媒体转换服务</h1>
                            <p class="status">✅ 服务运行正常！</p>
                            <p>通过反向代理访问成功</p>
                            <h3>📋 可用功能:</h3>
                            <ul>
                                <li><a href="/index.html">📊 完整管理界面</a></li>
                                <li><a href="/demo.html">🎬 演示页面</a></li>
                                <li><a href="/health">❤️ 健康检查</a></li>
                                <li><a href="/streams">🔗 API接口</a></li>
                            </ul>
                        </div>
                    </body>
                    </html>
                    '''
                    return web.Response(text=welcome_html, content_type='text/html')
            except Exception as e:
                logger.error(f"处理根路径请求时出错: {e}")
                error_html = f'''
                <!DOCTYPE html>
                <html>
                <head><title>服务错误</title></head>
                <body>
                    <h1>服务暂时不可用</h1>
                    <p>错误信息: {str(e)}</p>
                    <p><a href="/health">检查服务健康状态</a></p>
                </body>
                </html>
                '''
                return web.Response(text=error_html, status=500, content_type='text/html')
        
        # 先添加根路径处理器
        app.router.add_get('/', handle_root)
        
        # 添加HTML文件的直接访问路由
        async def serve_html_file(request):
            filename = request.match_info['filename']
            client_ip = request.headers.get('X-Forwarded-For', request.headers.get('X-Real-IP', request.remote))
            logger.info(f"静态文件访问 - IP: {client_ip}, 文件: {filename}")
            
            file_path = os.path.join('static', filename)
            if os.path.exists(file_path) and filename.endswith(('.html', '.css', '.js')):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 根据文件扩展名设置正确的Content-Type
                    if filename.endswith('.html'):
                        content_type = 'text/html'
                    elif filename.endswith('.css'):
                        content_type = 'text/css'
                    elif filename.endswith('.js'):
                        content_type = 'application/javascript'
                    else:
                        content_type = 'text/plain'
                    
                    return web.Response(text=content, content_type=content_type)
                except Exception as e:
                    logger.error(f"读取文件 {filename} 时出错: {e}")
                    return web.Response(text='File Error', status=500)
            else:
                return web.Response(text='File Not Found', status=404)
        
        # 添加HTML、CSS、JS文件的路由
        app.router.add_get(r'/{filename:[^/]+\.(html|css|js)}', serve_html_file)
        
        # 然后添加静态文件服务（使用不同的路径避免冲突）
        app.router.add_static('/static', path='static', name='static', follow_symlinks=True)
        
        # 添加OPTIONS处理支持CORS预检
        async def handle_options(request):
            return web.Response(status=200, headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            })
        
        # 为所有路径添加OPTIONS支持
        app.router.add_route('OPTIONS', '/{path:.*}', handle_options)
        
        return app

    def run(self):
        """运行服务器"""
        app = self.create_app()
        
        logger.info(f"启动MPD转HLS流媒体服务器...")
        logger.info(f"服务器地址: http://{self.config['server']['host']}:{self.config['server']['port']}")
        logger.info(f"支持的访问方式:")
        logger.info(f"  - 直接访问: http://{self.config['server']['host']}:{self.config['server']['port']}")
        logger.info(f"  - 通过反向代理: 确保代理正确转发X-Forwarded-For和X-Real-IP头")
        logger.info(f"  - Web管理界面: /index.html")
        logger.info(f"  - 演示页面: /demo.html") 
        logger.info(f"  - API健康检查: /health")
        
        web.run_app(
            app,
            host=self.config['server']['host'],
            port=self.config['server']['port'],
            access_log=logger
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
