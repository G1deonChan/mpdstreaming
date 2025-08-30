#!/usr/bin/env python3
"""
快速启动脚本 - 用于演示Web UI功能
"""

import asyncio
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import MPDToHLSStreamer

def main():
    print("🚀 启动MPD到HLS流媒体管理系统...")
    print("=" * 60)
    
    # 检查是否存在配置文件
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        print("⚠️  未找到config.yaml，将使用默认配置")
    
    try:
        # 创建并启动流媒体服务器
        streamer = MPDToHLSStreamer(config_path)
        print(f"🌐 Web管理界面: http://localhost:{streamer.config['server']['port']}")
        print(f"📊 健康检查: http://localhost:{streamer.config['server']['port']}/health")
        print(f"🔗 API接口: http://localhost:{streamer.config['server']['port']}/streams")
        print("=" * 60)
        print("💡 使用说明:")
        print("  1. 打开Web界面管理流配置")
        print("  2. 添加您的MPD流信息")
        print("  3. 启动流进行HLS转换")
        print("  4. 使用生成的HLS地址在播放器中播放")
        print("=" * 60)
        print("按 Ctrl+C 停止服务器")
        print()
        
        # 启动服务器
        streamer.run()
        
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
