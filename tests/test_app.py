#!/usr/bin/env python3
"""
测试脚本 - 验证MPD到HLS转换功能
"""

import unittest
import asyncio
import tempfile
import os
from unittest.mock import patch, MagicMock
import sys
import yaml

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import MPDToHLSStreamer

class TestMPDToHLSStreamer(unittest.TestCase):
    
    def setUp(self):
        """测试前准备"""
        # 创建临时配置文件
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        test_config = {
            'server': {'host': '127.0.0.1', 'port': 8081},
            'streams': [],
            'ffmpeg': {
                'hls_time': 6,
                'hls_list_size': 10,
                'hls_flags': 'delete_segments',
                'video_codec': 'libx264',
                'audio_codec': 'aac'
            }
        }
        yaml.dump(test_config, self.temp_config)
        self.temp_config.close()
        
        self.streamer = MPDToHLSStreamer(self.temp_config.name)
    
    def tearDown(self):
        """测试后清理"""
        os.unlink(self.temp_config.name)
        # 清理streamer资源
        if hasattr(self.streamer, '__del__'):
            self.streamer.__del__()
    
    def test_parse_kodi_props(self):
        """测试Kodi属性解析"""
        kodi_text = """#KODIPROP:inputstream.adaptive.manifest_type=mpd
#KODIPROP:inputstream.adaptive.license_type=clearkey
#KODIPROP:inputstream.adaptive.license_key=1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321
https://example.com/sample/stream.mpd"""
        
        result = self.streamer.parse_kodi_props(kodi_text)
        
        self.assertEqual(result['url'], 'https://example.com/sample/stream.mpd')
        self.assertEqual(result['manifest_type'], 'mpd')
        self.assertEqual(result['license_type'], 'clearkey')
        self.assertEqual(result['license_key'], '1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321')
    
    def test_parse_clearkey_license(self):
        """测试ClearKey许可证解析"""
        license_key = "1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321"
        result = self.streamer.parse_clearkey_license(license_key)
        
        self.assertEqual(result['key_id'], '1234567890abcdef1234567890abcdef')
        self.assertEqual(result['key'], 'fedcba0987654321fedcba0987654321')
    
    def test_load_config(self):
        """测试配置文件加载"""
        config = self.streamer.load_config()
        
        self.assertIn('server', config)
        self.assertIn('streams', config)
        self.assertIn('ffmpeg', config)
        self.assertEqual(config['server']['port'], 8081)
    
    def test_get_default_config(self):
        """测试默认配置"""
        default_config = self.streamer.get_default_config()
        
        self.assertIn('server', default_config)
        self.assertIn('streams', default_config)
        self.assertIn('ffmpeg', default_config)
        self.assertEqual(default_config['server']['host'], '0.0.0.0')

class TestStreamManager(unittest.TestCase):
    """测试流管理工具"""
    
    def setUp(self):
        # 假设有一个运行的服务器用于测试
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from stream_manager import StreamManager
        self.manager = StreamManager("http://localhost:8081")
    
    @patch('requests.get')
    def test_health_check(self, mock_get):
        """测试健康检查"""
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'healthy', 'active_streams': 0}
        mock_get.return_value = mock_response
        
        result = self.manager.health_check()
        self.assertEqual(result['status'], 'healthy')
    
    @patch('requests.get')
    def test_list_streams(self, mock_get):
        """测试获取流列表"""
        mock_response = MagicMock()
        mock_response.json.return_value = {'streams': []}
        mock_get.return_value = mock_response
        
        result = self.manager.list_streams()
        self.assertIn('streams', result)

if __name__ == '__main__':
    unittest.main()
