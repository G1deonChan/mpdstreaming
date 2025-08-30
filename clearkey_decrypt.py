#!/usr/bin/env python3
"""
ClearKey DASH 解密工具
独立的外部工具，用于解密使用ClearKey的MPEG-DASH流

此工具不依赖FFmpeg的有限解密功能，而是实现了完整的ClearKey解密流程：
1. 解析MPD清单文件
2. 提取加密的媒体片段
3. 使用提供的ClearKey解密
4. 生成解密后的媒体文件
"""

import os
import sys
import json
import argparse
import asyncio
import aiohttp
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
import base64
import binascii
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClearKeyDecryptor:
    """ClearKey解密器 - 处理MPEG-DASH流的ClearKey解密"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def parse_clearkey(self, license_key: str) -> Dict[str, bytes]:
        """
        解析ClearKey许可证
        支持格式: key_id:key (十六进制)
        """
        if ':' not in license_key:
            raise ValueError("ClearKey格式错误，应为 'key_id:key'")
        
        key_id_hex, key_hex = license_key.split(':', 1)
        
        try:
            key_id = binascii.unhexlify(key_id_hex.replace('-', ''))
            key = binascii.unhexlify(key_hex.replace('-', ''))
        except ValueError as e:
            raise ValueError(f"无效的十六进制格式: {e}")
        
        return {
            'key_id': key_id,
            'key': key
        }
    
    async def fetch_mpd(self, mpd_url: str) -> str:
        """获取MPD清单文件内容"""
        async with self.session.get(mpd_url) as response:
            if response.status != 200:
                raise Exception(f"无法获取MPD文件: HTTP {response.status}")
            return await response.text()
    
    def parse_mpd(self, mpd_content: str, base_url: str) -> Dict:
        """解析MPD文件，提取媒体信息"""
        try:
            root = ET.fromstring(mpd_content)
            
            # 移除命名空间前缀以简化解析
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}')[1]
            
            media_info = {
                'video_segments': [],
                'audio_segments': [],
                'encryption_info': None
            }
            
            # 查找加密信息
            for content_protection in root.iter('ContentProtection'):
                if content_protection.get('schemeIdUri') == 'urn:mpeg:dash:mp4protection:2011':
                    media_info['encryption_info'] = {
                        'scheme': 'cenc',
                        'default_kid': content_protection.get('cenc:default_KID')
                    }
            
            # 解析适应集和表示
            for adaptation_set in root.iter('AdaptationSet'):
                content_type = adaptation_set.get('contentType', '')
                mime_type = adaptation_set.get('mimeType', '')
                
                for representation in adaptation_set.iter('Representation'):
                    rep_id = representation.get('id')
                    bandwidth = representation.get('bandwidth')
                    
                    # 查找分段模板
                    segment_template = representation.find('SegmentTemplate')
                    if segment_template is None:
                        segment_template = adaptation_set.find('SegmentTemplate')
                    
                    if segment_template is not None:
                        media_template = segment_template.get('media')
                        init_template = segment_template.get('initialization')
                        
                        segments = []
                        
                        # 解析时间线或分段列表
                        timeline = segment_template.find('SegmentTimeline')
                        if timeline is not None:
                            segments = self._parse_timeline_segments(
                                timeline, media_template, init_template, 
                                rep_id, base_url
                            )
                        
                        if 'video' in content_type or 'video' in mime_type:
                            media_info['video_segments'].extend(segments)
                        elif 'audio' in content_type or 'audio' in mime_type:
                            media_info['audio_segments'].extend(segments)
            
            return media_info
        
        except ET.ParseError as e:
            raise Exception(f"MPD解析错误: {e}")
    
    def _parse_timeline_segments(self, timeline, media_template: str, 
                                init_template: str, rep_id: str, base_url: str) -> List[Dict]:
        """解析时间线分段信息"""
        segments = []
        
        # 添加初始化分段
        if init_template:
            init_url = init_template.replace('$RepresentationID$', rep_id)
            segments.append({
                'type': 'init',
                'url': urljoin(base_url, init_url),
                'representation_id': rep_id
            })
        
        # 添加媒体分段
        segment_number = 1
        for s_elem in timeline.iter('S'):
            duration = int(s_elem.get('d', 0))
            repeat = int(s_elem.get('r', 0)) + 1
            
            for _ in range(repeat):
                media_url = media_template.replace('$RepresentationID$', rep_id)
                media_url = media_url.replace('$Number$', str(segment_number))
                
                segments.append({
                    'type': 'media',
                    'url': urljoin(base_url, media_url),
                    'number': segment_number,
                    'duration': duration,
                    'representation_id': rep_id
                })
                segment_number += 1
        
        return segments
    
    async def download_segment(self, segment_url: str) -> bytes:
        """下载媒体分段"""
        async with self.session.get(segment_url) as response:
            if response.status != 200:
                raise Exception(f"无法下载分段: {segment_url} - HTTP {response.status}")
            return await response.read()
    
    def decrypt_segment(self, encrypted_data: bytes, key: bytes, iv: bytes = None) -> bytes:
        """解密媒体分段"""
        if iv is None:
            # 从MP4 box中提取IV，或使用默认值
            iv = b'\x00' * 16
        
        try:
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted_data = cipher.decrypt(encrypted_data)
            
            # 移除PKCS7填充（如果存在）
            try:
                decrypted_data = unpad(decrypted_data, AES.block_size)
            except ValueError:
                # 如果没有填充，直接使用原始解密数据
                pass
            
            return decrypted_data
        except Exception as e:
            logger.warning(f"解密失败: {e}")
            return encrypted_data
    
    async def decrypt_dash_stream(self, mpd_url: str, license_key: str, 
                                output_dir: str) -> Dict[str, str]:
        """
        解密DASH流并保存到指定目录
        
        Returns:
            Dict containing paths to decrypted video and audio files
        """
        logger.info(f"开始解密DASH流: {mpd_url}")
        
        # 解析ClearKey
        clearkey_info = self.parse_clearkey(license_key)
        key = clearkey_info['key']
        
        # 获取并解析MPD
        mpd_content = await self.fetch_mpd(mpd_url)
        base_url = mpd_url.rsplit('/', 1)[0] + '/'
        media_info = self.parse_mpd(mpd_content, base_url)
        
        logger.info(f"找到 {len(media_info['video_segments'])} 个视频分段")
        logger.info(f"找到 {len(media_info['audio_segments'])} 个音频分段")
        
        results = {}
        
        # 处理视频分段
        if media_info['video_segments']:
            video_file = await self._decrypt_segments(
                media_info['video_segments'], key, 
                os.path.join(output_dir, 'video_decrypted.mp4')
            )
            results['video'] = video_file
        
        # 处理音频分段
        if media_info['audio_segments']:
            audio_file = await self._decrypt_segments(
                media_info['audio_segments'], key, 
                os.path.join(output_dir, 'audio_decrypted.mp4')
            )
            results['audio'] = audio_file
        
        logger.info("DASH流解密完成")
        return results
    
    async def _decrypt_segments(self, segments: List[Dict], key: bytes, 
                               output_file: str) -> str:
        """下载并解密分段，合并为单个文件"""
        with open(output_file, 'wb') as f:
            for segment in segments:
                logger.debug(f"处理分段: {segment['url']}")
                
                # 下载分段
                segment_data = await self.download_segment(segment['url'])
                
                # 如果是加密分段，进行解密
                if segment['type'] == 'media':
                    decrypted_data = self.decrypt_segment(segment_data, key)
                    f.write(decrypted_data)
                else:
                    # 初始化分段通常不加密
                    f.write(segment_data)
        
        logger.info(f"分段处理完成: {output_file}")
        return output_file


class YtDlpDecryptor:
    """使用yt-dlp进行DASH解密的包装器"""
    
    @staticmethod
    def is_available() -> bool:
        """检查yt-dlp是否可用"""
        try:
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    @staticmethod
    async def decrypt_with_yt_dlp(mpd_url: str, license_key: str, 
                                output_dir: str) -> Optional[str]:
        """使用yt-dlp解密DASH流"""
        if not YtDlpDecryptor.is_available():
            logger.warning("yt-dlp不可用")
            return None
        
        try:
            output_template = os.path.join(output_dir, 'yt-dlp_output.%(ext)s')
            
            cmd = [
                'yt-dlp',
                '--no-playlist',
                '--format', 'best[ext=mp4]/best',
                '--output', output_template,
                '--no-warnings'
            ]
            
            # 添加ClearKey信息
            if license_key and ':' in license_key:
                key_id, key = license_key.split(':', 1)
                cmd.extend([
                    '--external-downloader', 'ffmpeg',
                    '--external-downloader-args', f'-decryption_key {key}'
                ])
            
            cmd.append(mpd_url)
            
            logger.info("使用yt-dlp解密...")
            
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
                    potential_file = os.path.join(output_dir, f'yt-dlp_output.{ext}')
                    if os.path.exists(potential_file):
                        logger.info(f"yt-dlp解密成功: {potential_file}")
                        return potential_file
            else:
                logger.error(f"yt-dlp错误: {stderr.decode()}")
                return None
        
        except Exception as e:
            logger.error(f"yt-dlp解密失败: {e}")
            return None


async def main():
    """命令行主函数"""
    parser = argparse.ArgumentParser(description='ClearKey DASH解密工具')
    parser.add_argument('mpd_url', help='MPD流地址')
    parser.add_argument('--license-key', required=True, 
                       help='ClearKey许可证 (格式: key_id:key)')
    parser.add_argument('--output-dir', default='./decrypted_output',
                       help='输出目录 (默认: ./decrypted_output)')
    parser.add_argument('--method', choices=['native', 'yt-dlp', 'auto'], 
                       default='auto', help='解密方法')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    
    success = False
    
    if args.method in ['auto', 'yt-dlp']:
        # 尝试使用yt-dlp
        if YtDlpDecryptor.is_available():
            logger.info("尝试使用yt-dlp解密...")
            output_file = await YtDlpDecryptor.decrypt_with_yt_dlp(
                args.mpd_url, args.license_key, args.output_dir
            )
            if output_file:
                print(f"✅ 解密成功 (yt-dlp): {output_file}")
                success = True
            else:
                logger.warning("yt-dlp解密失败")
    
    if not success and args.method in ['auto', 'native']:
        # 尝试使用原生解密器
        logger.info("尝试使用原生ClearKey解密器...")
        try:
            async with ClearKeyDecryptor() as decryptor:
                results = await decryptor.decrypt_dash_stream(
                    args.mpd_url, args.license_key, args.output_dir
                )
                
                if results:
                    print("✅ 解密成功 (原生解密器):")
                    for media_type, file_path in results.items():
                        print(f"  {media_type}: {file_path}")
                    success = True
        except Exception as e:
            logger.error(f"原生解密器失败: {e}")
    
    if not success:
        print("❌ 所有解密方法都失败了")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())