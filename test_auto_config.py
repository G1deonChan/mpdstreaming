#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动配置功能测试脚本
"""

import sys
import os
import asyncio
import yaml
from app import MPDToHLSStreamer

def test_auto_config():
    print("🧪 测试自动配置创建...")
    
    # 备份现有配置
    backup_path = None
    if os.path.exists('config.yaml'):
        backup_path = 'config.yaml.backup'
        os.rename('config.yaml', backup_path)
        print("📁 已备份现有配置")
    
    try:
        # 测试自动创建配置
        server = MPDToHLSStreamer()
        server.load_config()  # 同步调用，不用await
        
        # 检查配置是否创建成功（检查实际创建的路径）
        config_path = server.config_path
        if os.path.exists(config_path):
            print(f"✅ 自动配置创建成功: {config_path}")
            
            # 读取并验证配置内容
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            print(f"📋 流数量: {len(config.get('streams', []))}")
            print(f"🌐 服务器端口: {config.get('server', {}).get('port', 'N/A')}")
            print(f"📂 输出目录: {config.get('server', {}).get('output_dir', 'N/A')}")
            
            # 验证是否包含示例流
            streams = config.get('streams', [])
            if streams:
                first_stream = streams[0]
                print(f"🎬 示例流ID: {first_stream.get('id', 'N/A')}")
                print(f"🎬 示例流名称: {first_stream.get('name', 'N/A')}")
        else:
            print(f"❌ 配置文件未在预期路径创建: {config_path}")
            return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    finally:
        # 恢复原配置
        if backup_path and os.path.exists(backup_path):
            if os.path.exists('config.yaml'):
                os.remove('config.yaml')
            os.rename(backup_path, 'config.yaml')
            print("🔄 已恢复原配置")
    
    print("🎉 自动配置功能测试通过！")
    return True

if __name__ == "__main__":
    result = test_auto_config()
    sys.exit(0 if result else 1)
