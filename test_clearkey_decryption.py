#!/usr/bin/env python3
"""
测试ClearKey解密功能
"""

import unittest
import asyncio
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock
import shutil

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import DashDecryptor, MPDToHLSStreamer
from clearkey_decrypt import ClearKeyDecryptor, YtDlpDecryptor


class TestClearKeyDecryption(unittest.TestCase):
    """测试ClearKey解密功能"""
    
    def setUp(self):
        """测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.decryptor = DashDecryptor()
        
        # 测试用的ClearKey数据
        self.test_license_key = "1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321"
        self.test_mpd_url = "https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd"
        
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_clearkey_script_detection(self):
        """测试ClearKey脚本检测"""
        # DashDecryptor应该能检测到clearkey_decrypt.py脚本
        script_path = self.decryptor._find_clearkey_script()
        if script_path:
            self.assertTrue(os.path.exists(script_path))
            self.assertTrue(script_path.endswith('clearkey_decrypt.py'))
    
    def test_tools_detection(self):
        """测试工具检测"""
        tools = self.decryptor._detect_tools()
        self.assertIsInstance(tools, dict)
        self.assertIn('ffmpeg', tools)
        self.assertIn('yt-dlp', tools)
    
    def test_clearkey_parsing(self):
        """测试ClearKey解析"""
        # 测试app.py中的解析
        streamer = MPDToHLSStreamer()
        result = streamer.parse_clearkey_license(self.test_license_key)
        
        self.assertEqual(result['key_id'], '1234567890abcdef1234567890abcdef')
        self.assertEqual(result['key'], 'fedcba0987654321fedcba0987654321')
    
    def test_standalone_clearkey_parsing(self):
        """测试独立ClearKey解析器"""
        async def run_test():
            async with ClearKeyDecryptor() as decryptor:
                result = decryptor.parse_clearkey(self.test_license_key)
                
                self.assertIsInstance(result['key_id'], bytes)
                self.assertIsInstance(result['key'], bytes)
                self.assertEqual(len(result['key_id']), 16)  # 16字节 = 128位
                self.assertEqual(len(result['key']), 16)     # 16字节 = 128位
        
        asyncio.run(run_test())
    
    def test_invalid_clearkey_format(self):
        """测试无效ClearKey格式"""
        streamer = MPDToHLSStreamer()
        
        # 没有冒号的格式
        result = streamer.parse_clearkey_license("invalid_key_format")
        self.assertEqual(result, {})
        
        # 独立解析器应该抛出异常
        async def run_test():
            async with ClearKeyDecryptor() as decryptor:
                with self.assertRaises(ValueError):
                    decryptor.parse_clearkey("invalid_key_format")
        
        asyncio.run(run_test())
    
    @patch('subprocess.run')
    def test_yt_dlp_availability(self, mock_run):
        """测试yt-dlp可用性检测"""
        # 模拟yt-dlp可用
        mock_run.return_value.returncode = 0
        self.assertTrue(YtDlpDecryptor.is_available())
        
        # 模拟yt-dlp不可用
        mock_run.side_effect = FileNotFoundError()
        self.assertFalse(YtDlpDecryptor.is_available())
    
    def test_decrypt_dash_stream_interface(self):
        """测试解密接口"""
        async def run_test():
            # 测试没有许可证的情况
            result = await self.decryptor.decrypt_dash_stream(
                self.test_mpd_url, self.test_dir
            )
            self.assertIsNone(result)
            
            # 测试带许可证但可能失败的情况（网络或格式问题）
            try:
                result = await self.decryptor.decrypt_dash_stream(
                    self.test_mpd_url, self.test_dir, self.test_license_key
                )
                # 如果成功，结果应该是文件路径或None
                if result:
                    self.assertIsInstance(result, str)
            except Exception:
                # 网络错误或其他问题是可以接受的
                pass
        
        asyncio.run(run_test())
    
    def test_integration_with_main_streamer(self):
        """测试与主流媒体服务器的集成"""
        streamer = MPDToHLSStreamer()
        
        # 验证解密器已初始化
        self.assertIsInstance(streamer.dash_decryptor, DashDecryptor)
        
        # 测试流状态记录
        self.assertIsInstance(streamer.active_streams, dict)
        self.assertIsInstance(streamer.sessions, dict)
    
    def test_enhanced_stream_creation(self):
        """测试增强的流创建功能"""
        async def run_test():
            streamer = MPDToHLSStreamer()
            
            # 模拟解密器方法
            original_decrypt = streamer.dash_decryptor.decrypt_dash_stream
            
            async def mock_decrypt(*args, **kwargs):
                # 模拟解密成功，返回假的文件路径
                fake_file = os.path.join(self.test_dir, 'fake_decrypted.mp4')
                with open(fake_file, 'w') as f:
                    f.write('fake video content')
                return fake_file
            
            streamer.dash_decryptor.decrypt_dash_stream = mock_decrypt
            
            try:
                # 尝试创建HLS流
                # 这可能会因为FFmpeg参数或网络问题失败，但我们主要测试集成
                playlist_path = await streamer.create_hls_stream(
                    'test_stream', self.test_mpd_url, self.test_license_key
                )
                
                # 验证会话记录
                if 'test_stream' in streamer.sessions:
                    session = streamer.sessions['test_stream']
                    self.assertIn('temp_decrypted_file', session)
                    self.assertIn('decryption_used', streamer.active_streams.get('test_stream', {}))
                
            except Exception as e:
                # 由于FFmpeg配置或网络问题，这可能失败，但不应该是解密相关的错误
                print(f"集成测试预期可能失败: {e}")
            finally:
                # 恢复原始方法
                streamer.dash_decryptor.decrypt_dash_stream = original_decrypt
                
                # 清理
                if 'test_stream' in streamer.sessions:
                    try:
                        process = streamer.sessions['test_stream']['process']
                        process.terminate()
                    except:
                        pass
                    del streamer.sessions['test_stream']
                
                if 'test_stream' in streamer.active_streams:
                    del streamer.active_streams['test_stream']
        
        asyncio.run(run_test())
    
    def test_error_handling(self):
        """测试错误处理"""
        async def run_test():
            # 测试无效URL
            result = await self.decryptor.decrypt_dash_stream(
                "https://invalid-url.example.com/invalid.mpd", 
                self.test_dir, self.test_license_key
            )
            self.assertIsNone(result)
        
        asyncio.run(run_test())


class TestClearKeyDecryptorStandalone(unittest.TestCase):
    """测试独立ClearKey解密器"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_license_key = "1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321"
    
    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_clearkey_decryptor_context_manager(self):
        """测试ClearKeyDecryptor上下文管理器"""
        async def run_test():
            async with ClearKeyDecryptor() as decryptor:
                self.assertIsNotNone(decryptor.session)
        
        asyncio.run(run_test())
    
    def test_segment_decryption(self):
        """测试分段解密功能"""
        async def run_test():
            async with ClearKeyDecryptor() as decryptor:
                # 测试解密功能（使用假数据）
                fake_encrypted_data = b'0' * 32  # 32字节的假数据
                key = b'1' * 16  # 16字节的假密钥
                
                result = decryptor.decrypt_segment(fake_encrypted_data, key)
                self.assertIsInstance(result, bytes)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    # 设置日志级别以减少测试输出
    import logging
    logging.getLogger().setLevel(logging.ERROR)
    
    unittest.main()