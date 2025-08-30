#!/usr/bin/env python3
"""
DASH流ClearKey解密工具
使用多种方法解密MPEG-DASH加密流并转换为HLS
"""

import os
import sys
import asyncio
import subprocess
import tempfile
import logging
import json
from pathlib import Path
from typing import Dict, Optional, List
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
import base64
import binascii

logger = logging.getLogger(__name__)

class DashClearKeyDecryptor:
    """DASH ClearKey解密器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def parse_clearkey(self, license_key: str) -> Dict[str, str]:
        """解析ClearKey许可证"""
        if not license_key or ':' not in license_key:
            return {}
            
        key_id, key = license_key.split(':', 1)
        return {
            'key_id': key_id.strip(),
            'key': key.strip()
        }
    
    async def decrypt_with_yt_dlp(self, mpd_url: str, output_dir: str, 
                                 license_key: str = None) -> Optional[str]:
        """使用yt-dlp解密DASH流"""
        try:
            # 检查yt-dlp是否可用
            result = await asyncio.create_subprocess_exec(
                'yt-dlp', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            if result.returncode != 0:
                logger.warning("yt-dlp不可用")
                return None
            
            temp_output = os.path.join(output_dir, 'decrypted_video')
            
            cmd = [
                'yt-dlp',
                '--no-playlist',
                '--format', 'best[ext=mp4]/best',
                '--output', f'{temp_output}.%(ext)s',
                '--no-warnings',
                '--quiet'
            ]
            
            # 添加ClearKey解密参数
            if license_key:
                clearkey = self.parse_clearkey(license_key)
                if clearkey:
                    # yt-dlp的解密方式
                    cmd.extend([
                        '--allow-unplayable-formats',
                        '--external-downloader', 'ffmpeg',
                        '--external-downloader-args', f'-decryption_key {clearkey["key"]}'
                    ])
            
            cmd.append(mpd_url)
            
            logger.info(f"执行yt-dlp解密: {mpd_url}")
            
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
    
    async def decrypt_with_yt_dlp_to_pipe(self, mpd_url: str, license_key: str = None) -> subprocess.Popen:
        """使用yt-dlp解密DASH流并通过管道输出"""
        try:
            cmd = ['yt-dlp']
            
            # 基本下载选项
            cmd.extend([
                '--no-warnings',
                '--quiet',
                '-o', '-',  # 输出到stdout
                '-f', 'best[ext=mp4]/best',  # 优先选择mp4格式
            ])
            
            # 如果有ClearKey许可证
            if license_key:
                clearkey = self.parse_clearkey(license_key)
                if clearkey:
                    # 构建ClearKey的JSON格式
                    clearkey_json = json.dumps({
                        "keys": [{
                            "kty": "oct",
                            "kid": clearkey['key_id'],
                            "k": clearkey['key']
                        }]
                    })
                    
                    # 通过环境变量或临时文件传递密钥
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        f.write(clearkey_json)
                        key_file = f.name
                    
                    cmd.extend(['--external-downloader-args', f'clearkey:{key_file}'])
                    logger.info(f"使用ClearKey解密: key_id={clearkey['key_id'][:8]}...")
            
            cmd.append(mpd_url)
            
            logger.info(f"启动yt-dlp管道解密: {' '.join(cmd[:3])}...")
            
            # 启动进程，输出到stdout供管道使用
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False  # 二进制模式
            )
            
            return process
            
        except Exception as e:
            logger.error(f"yt-dlp管道解密启动失败: {e}")
            return None

    async def decrypt_with_manual_method(self, mpd_url: str, output_dir: str, 
                                        license_key: str) -> Optional[str]:
        """手动下载和解密方法"""
        try:
            # 1. 下载MPD清单
            mpd_content = self._download_mpd(mpd_url)
            if not mpd_content:
                return None
            
            # 2. 解析MPD获取加密信息和segment信息
            encryption_info, segments = self._parse_mpd(mpd_content, mpd_url)
            if not segments:
                logger.error("无法从MPD获取segment信息")
                return None
            
            # 3. 下载加密的segments（限制数量用于测试）
            encrypted_files = []
            for i, segment_info in enumerate(segments[:5]):  # 只下载前5个segment进行测试
                segment_file = os.path.join(output_dir, f'encrypted_segment_{i}.mp4')
                if self._download_segment(segment_info['url'], segment_file):
                    encrypted_files.append(segment_file)
            
            if not encrypted_files:
                logger.error("未能下载任何加密片段")
                return None
            
            # 4. 解密segments
            decrypted_files = []
            clearkey = self.parse_clearkey(license_key)
            
            for i, encrypted_file in enumerate(encrypted_files):
                decrypted_file = os.path.join(output_dir, f'decrypted_segment_{i}.mp4')
                if await self._decrypt_segment_with_clearkey(encrypted_file, decrypted_file, clearkey):
                    decrypted_files.append(decrypted_file)
            
            if not decrypted_files:
                logger.error("未能解密任何片段")
                return None
            
            # 5. 合并解密的segments
            merged_file = os.path.join(output_dir, 'merged_decrypted.mp4')
            if await self._merge_segments(decrypted_files, merged_file):
                # 清理临时文件
                for f in encrypted_files + decrypted_files:
                    try:
                        os.remove(f)
                    except:
                        pass
                return merged_file
            
            return None
            
        except Exception as e:
            logger.error(f"手动解密失败: {e}")
            return None
    
    def _download_mpd(self, mpd_url: str) -> Optional[str]:
        """下载MPD清单"""
        try:
            response = self.session.get(mpd_url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"下载MPD失败: {e}")
            return None
    
    def _parse_mpd(self, mpd_content: str, base_url: str) -> tuple:
        """解析MPD清单"""
        try:
            root = ET.fromstring(mpd_content)
            segments = []
            encryption_info = {}
            
            # 查找AdaptationSet
            for adaptation_set in root.findall('.//{urn:mpeg:dash:schema:mpd:2011}AdaptationSet'):
                # 查找ContentProtection
                for content_protection in adaptation_set.findall('.//{urn:mpeg:dash:schema:mpd:2011}ContentProtection'):
                    scheme_id = content_protection.get('schemeIdUri', '')
                    if 'clearkey' in scheme_id.lower():
                        encryption_info = {'type': 'clearkey'}
                
                # 查找Representation
                for representation in adaptation_set.findall('.//{urn:mpeg:dash:schema:mpd:2011}Representation'):
                    # 查找SegmentTemplate
                    segment_template = representation.find('.//{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate')
                    if segment_template is not None:
                        media_template = segment_template.get('media')
                        if media_template:
                            # 生成前几个segment URL
                            for i in range(1, 6):  # 前5个segment
                                segment_url = media_template.replace('$Number$', str(i))
                                segment_url = media_template.replace('$RepresentationID$', representation.get('id', ''))
                                segment_url = urljoin(base_url, segment_url)
                                segments.append({'url': segment_url, 'number': i})
            
            return encryption_info, segments
            
        except Exception as e:
            logger.error(f"解析MPD失败: {e}")
            return {}, []
    
    def _download_segment(self, segment_url: str, output_file: str) -> bool:
        """下载单个segment"""
        try:
            response = self.session.get(segment_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return os.path.exists(output_file) and os.path.getsize(output_file) > 0
            
        except Exception as e:
            logger.error(f"下载segment失败 {segment_url}: {e}")
            return False
    
    async def _decrypt_segment_with_clearkey(self, encrypted_file: str, decrypted_file: str, 
                                           clearkey: Dict[str, str]) -> bool:
        """使用ClearKey解密segment"""
        try:
            # 尝试使用mp4decrypt（如果可用）
            try:
                process = await asyncio.create_subprocess_exec(
                    'mp4decrypt',
                    '--key', f"{clearkey['key_id']}:{clearkey['key']}",
                    encrypted_file,
                    decrypted_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0 and os.path.exists(decrypted_file):
                    return True
                    
            except FileNotFoundError:
                logger.warning("mp4decrypt不可用，尝试其他方法")
            
            # 如果mp4decrypt不可用，尝试使用FFmpeg（虽然通常不支持）
            process = await asyncio.create_subprocess_exec(
                'ffmpeg', '-y',
                '-decryption_key', clearkey['key'],
                '-i', encrypted_file,
                '-c', 'copy',
                decrypted_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            return process.returncode == 0 and os.path.exists(decrypted_file)
            
        except Exception as e:
            logger.error(f"解密segment失败: {e}")
            return False
    
    async def _merge_segments(self, segment_files: List[str], output_file: str) -> bool:
        """合并视频片段"""
        try:
            # 创建文件列表
            temp_dir = os.path.dirname(output_file)
            file_list = os.path.join(temp_dir, 'file_list.txt')
            
            with open(file_list, 'w') as f:
                for segment_file in segment_files:
                    f.write(f"file '{segment_file}'\n")
            
            process = await asyncio.create_subprocess_exec(
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', file_list,
                '-c', 'copy',
                output_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # 清理临时文件列表
            try:
                os.remove(file_list)
            except:
                pass
            
            return process.returncode == 0 and os.path.exists(output_file)
            
        except Exception as e:
            logger.error(f"合并segments失败: {e}")
            return False
    
    async def convert_to_hls(self, input_file: str, output_dir: str) -> bool:
        """将解密的视频转换为HLS"""
        try:
            playlist_path = os.path.join(output_dir, 'playlist.m3u8')
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-f', 'hls',
                '-hls_time', '6',
                '-hls_list_size', '10',
                '-hls_flags', 'delete_segments',
                '-hls_segment_filename', os.path.join(output_dir, 'segment_%03d.ts'),
                playlist_path
            ]
            
            logger.info("开始转换为HLS格式")
            
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

# 主解密函数
async def decrypt_dash_to_hls(mpd_url: str, output_dir: str, license_key: str = None) -> bool:
    """解密DASH流并转换为HLS的主函数"""
    
    os.makedirs(output_dir, exist_ok=True)
    decryptor = DashClearKeyDecryptor()
    
    try:
        # 方法1: 尝试yt-dlp
        logger.info("尝试使用yt-dlp解密...")
        decrypted_file = await decryptor.decrypt_with_yt_dlp(mpd_url, output_dir, license_key)
        
        if decrypted_file:
            logger.info("yt-dlp解密成功，开始转换为HLS")
            return await decryptor.convert_to_hls(decrypted_file, output_dir)
        
        # 方法2: 手动解密方法
        if license_key:
            logger.info("yt-dlp失败，尝试手动解密方法...")
            decrypted_file = await decryptor.decrypt_with_manual_method(mpd_url, output_dir, license_key)
            
            if decrypted_file:
                logger.info("手动解密成功，开始转换为HLS")
                return await decryptor.convert_to_hls(decrypted_file, output_dir)
        
        # 方法3: 如果没有加密，直接用FFmpeg转换
        if not license_key:
            logger.info("无加密流，直接使用FFmpeg转换")
            playlist_path = os.path.join(output_dir, 'playlist.m3u8')
            
            process = await asyncio.create_subprocess_exec(
                'ffmpeg', '-y',
                '-i', mpd_url,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-f', 'hls',
                '-hls_time', '6',
                '-hls_list_size', '10',
                '-hls_flags', 'delete_segments',
                '-hls_segment_filename', os.path.join(output_dir, 'segment_%03d.ts'),
                playlist_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            return process.returncode == 0 and os.path.exists(playlist_path)
        
        logger.error("所有解密方法都失败了")
        return False
        
    except Exception as e:
        logger.error(f"解密转换过程中发生异常: {e}")
        return False

# 新增：管道模式解密函数
async def decrypt_dash_to_pipe(mpd_url: str, license_key: str = None, output_format: str = 'ts') -> int:
    """解密DASH流并通过管道输出 - 用于与FFmpeg连接"""
    
    decryptor = DashClearKeyDecryptor()
    
    try:
        # 使用yt-dlp进行管道解密
        logger.info(f"启动管道模式解密: {mpd_url}")
        
        if license_key:
            logger.info("检测到ClearKey许可证，使用yt-dlp解密管道")
            process = await decryptor.decrypt_with_yt_dlp_to_pipe(mpd_url, license_key)
        else:
            logger.info("无加密流，使用yt-dlp直接下载管道")
            process = await decryptor.decrypt_with_yt_dlp_to_pipe(mpd_url)
        
        if process:
            # 将解密后的数据转发到stdout
            try:
                while True:
                    chunk = process.stdout.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                
                # 等待进程完成
                returncode = process.wait()
                
                if returncode == 0:
                    logger.info("管道解密完成")
                    return 0
                else:
                    stderr_output = process.stderr.read().decode('utf-8', errors='ignore')
                    logger.error(f"管道解密失败: {stderr_output}")
                    return returncode
                    
            except Exception as e:
                logger.error(f"管道数据传输失败: {e}")
                process.kill()
                return 1
        else:
            logger.error("无法启动解密进程")
            return 1
            
    except Exception as e:
        logger.error(f"管道解密异常: {e}")
        return 1

# 命令行工具
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='DASH流ClearKey解密工具')
    parser.add_argument('mpd_url', help='MPD流URL')
    parser.add_argument('output', nargs='?', help='输出目录或文件名')
    parser.add_argument('--license-key', help='ClearKey许可证 (key_id:key)')
    parser.add_argument('--output-format', choices=['file', 'pipe'], default='file', help='输出格式')
    parser.add_argument('--pipe-format', choices=['mp4', 'ts'], default='ts', help='管道输出格式')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细日志')
    
    args = parser.parse_args()
    
    # 设置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    async def main():
        if args.output_format == 'pipe':
            # 管道模式 - 输出到stdout供FFmpeg使用
            exit_code = await decrypt_dash_to_pipe(args.mpd_url, args.license_key, args.pipe_format)
            sys.exit(exit_code)
        else:
            # 文件模式 - 保存到文件系统
            if not args.output:
                logger.error("文件模式需要指定输出目录")
                sys.exit(1)
                
            success = await decrypt_dash_to_hls(args.mpd_url, args.output, args.license_key)
            
            if success:
                print(f"✅ 解密转换成功! HLS播放列表: {os.path.join(args.output, 'playlist.m3u8')}")
                sys.exit(0)
            else:
                print("❌ 解密转换失败")
                sys.exit(1)
    
    asyncio.run(main())
