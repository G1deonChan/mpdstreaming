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
        self.script_path = os.path.join(os.path.dirname(__file__), 'decrypt_dash.py')
        self.tools = self._detect_tools()
        logger.info(f"解密工具检测完成: {[k for k, v in self.tools.items() if v]}")
    
    def _detect_tools(self) -> Dict[str, bool]:
        """检测可用的解密工具"""
        tools = {}
        
        # 检查yt-dlp
        try:
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, timeout=5)
            tools['yt-dlp'] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            tools['yt-dlp'] = False
            
        # 检查mp4decrypt
        try:
            result = subprocess.run(['mp4decrypt', '--version'], 
                                  capture_output=True, timeout=5)
            tools['mp4decrypt'] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            tools['mp4decrypt'] = False
            
        # 检查ffmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, timeout=5)
            tools['ffmpeg'] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            tools['ffmpeg'] = False
            
        return tools
    
    async def decrypt_stream(self, mpd_url: str, output_dir: str, 
                           license_key: str = None) -> Optional[str]:
        """解密DASH流 - 调用外部解密脚本"""
        if not os.path.exists(self.script_path):
            logger.error(f"解密脚本不存在: {self.script_path}")
            return None
            
        try:
            os.makedirs(output_dir, exist_ok=True)
            temp_output = os.path.join(output_dir, 'decrypted_video')
            
            # 构建解密命令
            cmd = ['python', self.script_path, mpd_url, temp_output]
            
            # 如果有ClearKey许可证
            if license_key:
                cmd.extend(['--license-key', license_key])
            
            logger.info(f"执行解密: {mpd_url}")
            
            # 异步执行解密脚本
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(__file__)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # 查找生成的文件
                for ext in ['mp4', 'mkv', 'webm', 'ts']:
                    potential_file = f'{temp_output}.{ext}'
                    if os.path.exists(potential_file):
                        logger.info(f"解密成功: {potential_file}")
                        return potential_file
                
                # 检查是否有其他输出文件
                for file in os.listdir(output_dir):
                    if file.startswith('decrypted_video') and not file.endswith('.log'):
                        full_path = os.path.join(output_dir, file)
                        logger.info(f"解密成功: {full_path}")
                        return full_path
                        
                logger.error("解密执行成功但找不到输出文件")
                logger.info(f"解密输出: {stdout.decode('utf-8', errors='ignore')}")
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"解密失败: {error_msg}")
                logger.info(f"解密输出: {stdout.decode('utf-8', errors='ignore')}")
            
            return None
            
        except Exception as e:
            logger.error(f"解密异常: {e}")
            return None
    
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
                    logger.info(f"清理临时文件: {input_file}")
                except Exception as cleanup_error:
                    logger.warning(f"清理临时文件失败: {cleanup_error}")
                return True
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"HLS转换失败: {error_msg}")
                logger.info(f"FFmpeg输出: {stdout.decode('utf-8', errors='ignore')}")
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

    async def test_stream_connectivity(self, url: str, timeout: int = 10) -> bool:
        """测试流URL的连接性"""
        try:
            async with ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.head(url) as response:
                    logger.info(f"流连接测试: {url} - {response.status}")
                    return response.status in [200, 206, 302, 404]  # 404可能是正常的（某些MPD endpoint）
        except asyncio.TimeoutError:
            logger.warning(f"流连接测试超时: {url}")
            return False
        except Exception as e:
            logger.warning(f"流连接测试失败: {url} - {e}")
            return False

    def _analyze_ffmpeg_error(self, output: str, return_code: int) -> str:
        """分析FFmpeg错误信息"""
        if not output:
            return f"进程异常退出 (代码: {return_code})"
        
        output_lower = output.lower()
        
        # 网络连接错误
        if "connection reset by peer" in output_lower:
            return "网络连接被重置，可能是源服务器问题或网络不稳定"
        elif "connection refused" in output_lower:
            return "连接被拒绝，源服务器可能不可达"
        elif "timeout" in output_lower or "timed out" in output_lower:
            return "连接超时，网络延迟过高或源服务器响应慢"
        elif "403" in output_lower or "forbidden" in output_lower:
            return "访问被禁止，可能需要认证或IP被封"
        elif "404" in output_lower or "not found" in output_lower:
            return "资源不存在，URL可能已失效"
        elif "500" in output_lower or "internal server error" in output_lower:
            return "源服务器内部错误"
        
        # SSL/TLS错误
        elif "ssl" in output_lower or "tls" in output_lower:
            return "SSL/TLS握手失败，可能是证书问题"
        
        # 格式/编解码错误
        elif "invalid data" in output_lower or "corrupt" in output_lower:
            return "数据损坏或格式不支持"
        elif "no decoder" in output_lower:
            return "缺少解码器或格式不支持"
        
        # 解密相关错误
        elif "decryption" in output_lower:
            return "解密失败，密钥可能不正确"
        
        # 输出相关错误
        elif "permission denied" in output_lower:
            return "文件权限错误"
        elif "disk full" in output_lower or "no space" in output_lower:
            return "磁盘空间不足"
        
        return f"未知错误 (代码: {return_code})"

    def _should_retry_error(self, error_analysis: str, current_restarts: int) -> bool:
        """判断错误是否应该重试"""
        error_lower = error_analysis.lower()
        
        # 不应重试的错误
        if any(keyword in error_lower for keyword in [
            "403", "forbidden", "not found", "404", 
            "permission denied", "disk full", "no space",
            "no decoder", "format not support", "被禁止", "不存在"
        ]):
            return False
        
        # 网络相关错误应该重试，但次数递减
        if any(keyword in error_lower for keyword in [
            "connection", "timeout", "network", "ssl", "tls", "连接", "超时", "网络"
        ]):
            return current_restarts < 2  # 网络错误最多重试2次
        
        # 其他错误可以重试
        return True

    def _get_retry_delay(self, error_analysis: str, retry_count: int) -> int:
        """根据错误类型和重试次数获取延迟时间"""
        base_delay = 5
        error_lower = error_analysis.lower()
        
        # 网络错误使用指数退避
        if any(keyword in error_lower for keyword in [
            "connection", "timeout", "network", "连接", "超时", "网络"
        ]):
            return min(base_delay * (2 ** (retry_count - 1)), 30)
        
        # 服务器错误稍长延迟
        if any(keyword in error_lower for keyword in [
            "500", "internal server error", "ssl", "tls"
        ]):
            return base_delay * 2
        
        return base_delay

    async def create_hls_stream(self, stream_id: str, mpd_url: str, 
                              license_key: str = None) -> str:
        """创建HLS流"""
        output_dir = os.path.join(self.temp_dir, stream_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # 首先测试流URL连接性
        logger.info(f"测试流URL连接性: {mpd_url}")
        if not await self.test_stream_connectivity(mpd_url):
            logger.error(f"流URL连接失败，无法创建HLS流: {stream_id}")
            raise Exception(f"无法连接到流URL: {mpd_url}")
        
        # 如果MPD流需要解密 - 使用管道传输到FFmpeg
        if license_key and 'clearkey' in license_key.lower():
            logger.info(f"检测到ClearKey加密流，使用外部解密器: {stream_id}")
            return await self._create_hls_with_decryption_pipe(stream_id, mpd_url, license_key, output_dir)
        else:
            # 标准FFmpeg处理（无加密）
            return await self._create_hls_with_ffmpeg(stream_id, mpd_url, license_key, output_dir)

    async def _create_hls_with_decryption_pipe(self, stream_id: str, mpd_url: str, 
                                              license_key: str, output_dir: str) -> str:
        """使用解密管道创建HLS流"""
        try:
            # 构建解密命令 - 输出到stdout供FFmpeg使用
            decrypt_cmd = [
                'python', 
                os.path.join(os.path.dirname(__file__), 'decrypt_dash.py'),
                mpd_url,
                '--license-key', license_key,
                '--output-format', 'pipe',  # 新参数：管道输出模式
                '--pipe-format', 'ts'  # 输出为TS格式方便FFmpeg处理
            ]
            
            # 构建FFmpeg命令 - 从stdin读取解密后的数据
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出文件
                '-f', 'mpegts',  # 输入格式为MPEG-TS
                '-i', 'pipe:0',  # 从stdin读取
                '-c:v', self.config['ffmpeg']['video_codec'],
                '-c:a', self.config['ffmpeg']['audio_codec'],
                '-f', 'hls',
                '-hls_time', str(self.config['ffmpeg']['hls_time']),
                '-hls_list_size', str(self.config['ffmpeg']['hls_list_size']),
                '-hls_flags', self.config['ffmpeg']['hls_flags'],
                '-hls_segment_filename', os.path.join(output_dir, 'segment_%03d.ts'),
                os.path.join(output_dir, 'playlist.m3u8')
            ]

            logger.info(f"启动解密管道: {' '.join(decrypt_cmd[:3])}... | {' '.join(ffmpeg_cmd[:5])}...")
            
            # 启动解密进程
            decrypt_process = subprocess.Popen(
                decrypt_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False  # 二进制模式
            )
            
            # 启动FFmpeg进程，连接解密进程的输出
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=decrypt_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 关闭解密进程的stdout在FFmpeg进程中，避免管道阻塞
            decrypt_process.stdout.close()

            # 保存会话信息 - 需要管理两个进程
            self.sessions[stream_id] = {
                'decrypt_process': decrypt_process,
                'ffmpeg_process': ffmpeg_process,
                'process': ffmpeg_process,  # 保持兼容性，主要监控FFmpeg
                'output_dir': output_dir,
                'created_at': time.time(),
                'status': 'starting',
                'cmd': ffmpeg_cmd,
                'decrypt_cmd': decrypt_cmd,
                'restart_count': 0,
                'method': 'decryption_pipe'
            }
            
            # 更新活跃流状态
            self.active_streams[stream_id] = {
                'status': 'starting',
                'started_at': time.time(),
                'mpd_url': mpd_url,
                'license_key': license_key,
                'method': 'decryption_pipe'
            }

            # 异步监控两个进程
            asyncio.create_task(self._monitor_decryption_pipe(stream_id))

            return os.path.join(output_dir, 'playlist.m3u8')
            
        except Exception as e:
            logger.error(f"启动解密管道失败: {e}")
            # 清理会话
            if stream_id in self.sessions:
                del self.sessions[stream_id]
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
            raise

    async def _create_hls_with_ffmpeg(self, stream_id: str, mpd_url: str, 
                                     license_key: str, output_dir: str) -> str:
        """使用标准FFmpeg创建HLS流（无加密或fallback）"""
        cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出文件
            '-reconnect', '1',  # 启用自动重连
            '-reconnect_streamed', '1',  # 对流媒体启用重连
            '-reconnect_delay_max', '30',  # 最大重连延迟30秒
            '-timeout', '30000000',  # 30秒超时（微秒）
            '-user_agent', 'Mozilla/5.0 (compatible; MPD-HLS-Streamer)',  # 设置User-Agent
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

        # 如果有ClearKey许可证，添加解密参数（仅作为fallback - 但通常不起作用）
        if license_key:
            clearkey = self.parse_clearkey_license(license_key)
            if clearkey:
                # FFmpeg的ClearKey支持有限，主要作为fallback
                decrypt_idx = cmd.index('-i')
                cmd.insert(decrypt_idx, '-decryption_key')
                cmd.insert(decrypt_idx + 1, clearkey['key'])
                logger.info(f"使用FFmpeg ClearKey fallback: key_id={clearkey['key_id']}, key=*** (可能不起作用)")

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
                'method': 'ffmpeg_direct'
            }
            
            # 更新活跃流状态
            self.active_streams[stream_id] = {
                'status': 'starting',
                'started_at': time.time(),
                'mpd_url': mpd_url,
                'license_key': license_key,
                'method': 'ffmpeg_direct'
            }

            # 异步监控FFmpeg进程
            asyncio.create_task(self._monitor_ffmpeg_process(stream_id))

            return os.path.join(output_dir, 'playlist.m3u8')
            
        except Exception as e:
            logger.error(f"启动FFmpeg失败: {e}")
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
                # 进程已退出，尝试读取输出
                try:
                    # 使用非阻塞方式读取输出
                    stdout = process.stdout.read() if process.stdout else ""
                    stderr = ""  # stderr已合并到stdout
                except:
                    stdout = ""
                    stderr = ""
                
                logger.error(f"FFmpeg进程意外退出 (stream_id: {stream_id})")
                logger.error(f"返回码: {process.returncode}")
                if stdout:
                    logger.error(f"标准输出: {stdout}")
                if stderr:
                    logger.error(f"错误输出: {stderr}")
                
                # 分析错误类型
                error_analysis = self._analyze_ffmpeg_error(stdout, process.returncode)
                logger.info(f"错误分析: {error_analysis}")
                
                # 更新状态
                if stream_id in self.active_streams:
                    self.active_streams[stream_id]['status'] = 'error'
                    self.active_streams[stream_id]['error'] = error_analysis
                session['status'] = 'error'
                session['error'] = error_analysis
                
                # 正确递增重启计数器
                current_restarts = session.get('restart_count', 0)
                
                # 根据错误类型决定是否重试
                should_retry = self._should_retry_error(error_analysis, current_restarts)
                
                # 尝试重启（如果重启次数未超限且错误可重试）
                if current_restarts < max_restarts and should_retry:
                    session['restart_count'] = current_restarts + 1
                    logger.info(f"尝试重启FFmpeg进程 (stream_id: {stream_id}, 第{session['restart_count']}次)")
                    
                    # 根据错误类型调整延迟时间
                    delay = self._get_retry_delay(error_analysis, session['restart_count'])
                    await asyncio.sleep(delay)
                    
                    await self._restart_ffmpeg_process(stream_id)
                else:
                    reason = "重启次数超限" if current_restarts >= max_restarts else "错误不可重试"
                    logger.error(f"FFmpeg进程停止重试: {reason} (stream_id: {stream_id})")
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
    
    async def _monitor_decryption_pipe(self, stream_id: str):
        """监控解密管道进程状态"""
        if stream_id not in self.sessions:
            return
        
        session = self.sessions[stream_id]
        decrypt_process = session['decrypt_process']
        ffmpeg_process = session['ffmpeg_process']
        max_restarts = 3
        
        try:
            # 等待进程启动
            await asyncio.sleep(2)
            
            # 检查两个进程的状态
            decrypt_status = decrypt_process.poll()
            ffmpeg_status = ffmpeg_process.poll()
            
            if decrypt_status is not None or ffmpeg_status is not None:
                # 至少一个进程已退出
                logger.error(f"解密管道进程退出 (stream_id: {stream_id})")
                
                # 收集错误信息
                error_info = []
                
                if decrypt_status is not None:
                    try:
                        _, stderr = decrypt_process.communicate(timeout=1)
                        decrypt_error = stderr.decode('utf-8', errors='ignore') if stderr else ""
                        error_info.append(f"解密进程退出 (代码: {decrypt_status}): {decrypt_error}")
                        logger.error(f"解密进程退出 - 代码: {decrypt_status}, 错误: {decrypt_error}")
                    except:
                        error_info.append(f"解密进程异常退出 (代码: {decrypt_status})")
                
                if ffmpeg_status is not None:
                    try:
                        stdout = ffmpeg_process.stdout.read() if ffmpeg_process.stdout else ""
                        error_info.append(f"FFmpeg进程退出 (代码: {ffmpeg_status}): {stdout}")
                        logger.error(f"FFmpeg进程退出 - 代码: {ffmpeg_status}, 输出: {stdout}")
                    except:
                        error_info.append(f"FFmpeg进程异常退出 (代码: {ffmpeg_status})")
                
                # 分析错误类型
                combined_error = " | ".join(error_info)
                error_analysis = self._analyze_ffmpeg_error(combined_error, ffmpeg_status or decrypt_status)
                logger.info(f"解密管道错误分析: {error_analysis}")
                
                # 更新状态
                if stream_id in self.active_streams:
                    self.active_streams[stream_id]['status'] = 'error'
                    self.active_streams[stream_id]['error'] = error_analysis
                session['status'] = 'error'
                session['error'] = error_analysis
                
                # 正确递增重启计数器
                current_restarts = session.get('restart_count', 0)
                
                # 根据错误类型决定是否重试
                should_retry = self._should_retry_error(error_analysis, current_restarts)
                
                # 尝试重启（如果重启次数未超限且错误可重试）
                if current_restarts < max_restarts and should_retry:
                    session['restart_count'] = current_restarts + 1
                    logger.info(f"尝试重启解密管道 (stream_id: {stream_id}, 第{session['restart_count']}次)")
                    
                    # 根据错误类型调整延迟时间
                    delay = self._get_retry_delay(error_analysis, session['restart_count'])
                    await asyncio.sleep(delay)
                    
                    await self._restart_decryption_pipe(stream_id)
                else:
                    reason = "重启次数超限" if current_restarts >= max_restarts else "错误不可重试"
                    logger.error(f"解密管道停止重试: {reason} (stream_id: {stream_id})")
            else:
                # 进程正在运行，等待一段时间后检查playlist文件
                await asyncio.sleep(5)
                playlist_path = os.path.join(session['output_dir'], 'playlist.m3u8')
                
                if os.path.exists(playlist_path):
                    # 更新状态为运行中
                    if stream_id in self.active_streams:
                        self.active_streams[stream_id]['status'] = 'running'
                    session['status'] = 'running'
                    logger.info(f"解密管道已成功启动 (stream_id: {stream_id})")
                else:
                    logger.warning(f"解密管道运行但未生成playlist文件 (stream_id: {stream_id})")
                
        except Exception as e:
            logger.error(f"监控解密管道时出错 (stream_id: {stream_id}): {e}")

    async def _restart_decryption_pipe(self, stream_id: str):
        """重启解密管道"""
        if stream_id not in self.sessions:
            return
        
        session = self.sessions[stream_id]
        
        # 停止旧进程
        if session['decrypt_process'].poll() is None:
            session['decrypt_process'].terminate()
            await asyncio.sleep(1)
            if session['decrypt_process'].poll() is None:
                session['decrypt_process'].kill()
        
        if session['ffmpeg_process'].poll() is None:
            session['ffmpeg_process'].terminate()
            await asyncio.sleep(1)
            if session['ffmpeg_process'].poll() is None:
                session['ffmpeg_process'].kill()
        
        # 获取流配置
        stream_config = None
        for stream in self.config['streams']:
            if stream['id'] == stream_id:
                stream_config = stream
                break
        
        if not stream_config:
            logger.error(f"找不到流配置，无法重启解密管道 (stream_id: {stream_id})")
            return
        
        try:
            # 保留重启计数器和错误信息
            restart_count = session.get('restart_count', 0)
            error_info = session.get('error', '')
            
            # 重新启动（清理旧会话，但保持重启计数）
            if stream_id in self.sessions:
                del self.sessions[stream_id]
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
            
            # 延迟一段时间再重启
            await asyncio.sleep(1)
            
            await self.create_hls_stream(
                stream_id,
                stream_config['url'],
                stream_config.get('license_key')
            )
            
            # 恢复重启计数器和错误信息
            if stream_id in self.sessions:
                self.sessions[stream_id]['restart_count'] = restart_count
                self.sessions[stream_id]['last_error'] = error_info
                
        except Exception as e:
            logger.error(f"重启解密管道失败 (stream_id: {stream_id}): {e}")
            # 标记为失败状态
            if stream_id in self.active_streams:
                self.active_streams[stream_id]['status'] = 'failed'
                self.active_streams[stream_id]['error'] = str(e)
    
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
            # 保留重启计数器和错误信息
            restart_count = session.get('restart_count', 0)
            error_info = session.get('error', '')
            
            # 重新启动（清理旧会话，但保持重启计数）
            if stream_id in self.sessions:
                del self.sessions[stream_id]
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
            
            # 延迟一段时间再重启
            await asyncio.sleep(1)
            
            await self.create_hls_stream(
                stream_id,
                stream_config['url'],
                stream_config.get('license_key')
            )
            
            # 恢复重启计数器和错误信息
            if stream_id in self.sessions:
                self.sessions[stream_id]['restart_count'] = restart_count
                self.sessions[stream_id]['last_error'] = error_info
                
        except Exception as e:
            logger.error(f"重启FFmpeg进程失败 (stream_id: {stream_id}): {e}")
            # 标记为失败状态
            if stream_id in self.active_streams:
                self.active_streams[stream_id]['status'] = 'failed'
                self.active_streams[stream_id]['error'] = str(e)

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
            
            # 根据不同的方法清理进程
            if session.get('method') == 'decryption_pipe':
                # 清理解密管道的两个进程
                if 'decrypt_process' in session and session['decrypt_process'].poll() is None:
                    session['decrypt_process'].terminate()
                    session['decrypt_process'].wait(timeout=5)
                    
                if 'ffmpeg_process' in session and session['ffmpeg_process'].poll() is None:
                    session['ffmpeg_process'].terminate()
                    session['ffmpeg_process'].wait(timeout=5)
            else:
                # 清理单个FFmpeg进程
                if 'process' in session and session['process'].poll() is None:
                    session['process'].terminate()
                    session['process'].wait(timeout=5)
            
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
        app.router.add_get('/{filename:[^/]+\\.(html|css|js)}', serve_html_file)
        
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
