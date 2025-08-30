#!/usr/bin/env python3
"""
MPD流管理工具
用于添加、管理和测试MPD到HLS的流转换
"""

import requests
import json
import sys
import argparse
from typing import Dict, Any

class StreamManager:
    def __init__(self, server_url: str = "http://localhost:8080"):
        self.server_url = server_url.rstrip('/')
    
    def add_stream_from_kodi_format(self, kodi_text: str, name: str = None) -> Dict[str, Any]:
        """从Kodi格式添加流"""
        data = {
            'kodi_format': kodi_text
        }
        if name:
            data['name'] = name
        
        try:
            response = requests.post(f"{self.server_url}/streams", json=data)
            return response.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_streams(self) -> Dict[str, Any]:
        """列出所有流"""
        try:
            response = requests.get(f"{self.server_url}/streams")
            return response.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            response = requests.get(f"{self.server_url}/health")
            return response.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}

def main():
    parser = argparse.ArgumentParser(description='MPD流管理工具')
    parser.add_argument('--server', default='http://localhost:8080', 
                       help='服务器URL (默认: http://localhost:8080)')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 添加流命令
    add_parser = subparsers.add_parser('add', help='添加新流')
    add_parser.add_argument('--kodi-format', required=True, 
                           help='Kodi格式的流信息')
    add_parser.add_argument('--name', help='流名称')
    
    # 列出流命令
    subparsers.add_parser('list', help='列出所有流')
    
    # 健康检查命令
    subparsers.add_parser('health', help='服务器健康检查')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = StreamManager(args.server)
    
    if args.command == 'add':
        result = manager.add_stream_from_kodi_format(args.kodi_format, args.name)
        if result.get('success'):
            print(f"✅ 流添加成功！")
            print(f"流ID: {result['stream_id']}")
            print(f"HLS URL: {args.server}{result['hls_url']}")
        else:
            print(f"❌ 添加失败: {result.get('error')}")
    
    elif args.command == 'list':
        result = manager.list_streams()
        if 'streams' in result:
            print(f"📺 共有 {len(result['streams'])} 个流:")
            for stream in result['streams']:
                print(f"  - {stream['id']}: {stream['name']}")
                print(f"    HLS URL: {args.server}{stream['hls_url']}")
        else:
            print(f"❌ 获取流列表失败: {result.get('error')}")
    
    elif args.command == 'health':
        result = manager.health_check()
        if result.get('status') == 'healthy':
            print(f"✅ 服务器健康")
            print(f"活跃流数量: {result.get('active_streams', 0)}")
        else:
            print(f"❌ 服务器不健康: {result.get('error')}")

if __name__ == '__main__':
    main()
