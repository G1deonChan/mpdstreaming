#!/usr/bin/env python3
"""
示例使用脚本
演示如何使用MPD到HLS流媒体转换服务
"""

import time
import requests
import json

def main():
    server_url = "http://localhost:8080"
    
    print("🎥 MPD到HLS流媒体转换服务示例")
    print("=" * 50)
    
    # 1. 健康检查
    print("\n1. 检查服务器状态...")
    try:
        response = requests.get(f"{server_url}/health")
        health = response.json()
        print(f"✅ 服务器状态: {health.get('status')}")
        print(f"📊 活跃流数量: {health.get('active_streams', 0)}")
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        return
    
    # 2. 添加示例流
    print("\n2. 添加示例MPD流...")
    
    # 使用示例Kodi格式
    kodi_format = """#KODIPROP:inputstream.adaptive.manifest_type=mpd
#KODIPROP:inputstream.adaptive.license_type=clearkey
#KODIPROP:inputstream.adaptive.license_key=1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321
https://example.com/sample/stream.mpd"""
    
    stream_data = {
        "name": "示例TV频道",
        "kodi_format": kodi_format
    }
    
    try:
        response = requests.post(
            f"{server_url}/streams",
            json=stream_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                stream_id = result['stream_id']
                hls_url = f"{server_url}{result['hls_url']}"
                print(f"✅ 流添加成功!")
                print(f"📺 流ID: {stream_id}")
                print(f"🔗 HLS播放URL: {hls_url}")
                
                # 3. 等待流生成
                print(f"\n3. 等待HLS流生成...")
                print("⏳ 这可能需要几秒钟时间...")
                
                # 等待一段时间让FFmpeg处理
                time.sleep(10)
                
                # 4. 检查HLS播放列表
                print(f"\n4. 检查HLS播放列表...")
                try:
                    playlist_response = requests.get(hls_url)
                    if playlist_response.status_code == 200:
                        print("✅ HLS播放列表生成成功!")
                        print(f"📄 播放列表前几行:")
                        lines = playlist_response.text.split('\n')[:5]
                        for line in lines:
                            if line.strip():
                                print(f"    {line}")
                    else:
                        print(f"❌ 无法获取播放列表: HTTP {playlist_response.status_code}")
                except Exception as e:
                    print(f"❌ 检查播放列表时出错: {e}")
                
            else:
                print(f"❌ 添加流失败: {result.get('error')}")
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"响应: {response.text}")
    
    except Exception as e:
        print(f"❌ 添加流时出错: {e}")
    
    # 5. 列出所有流
    print(f"\n5. 获取所有流列表...")
    try:
        response = requests.get(f"{server_url}/streams")
        streams = response.json()
        
        if 'streams' in streams and streams['streams']:
            print(f"📺 共找到 {len(streams['streams'])} 个流:")
            for stream in streams['streams']:
                print(f"  - {stream['name']} ({stream['id']})")
                print(f"    HLS URL: {server_url}{stream['hls_url']}")
        else:
            print("📭 暂无配置的流")
    
    except Exception as e:
        print(f"❌ 获取流列表时出错: {e}")
    
    print(f"\n" + "=" * 50)
    print("🎉 示例演示完成!")
    print(f"💡 您可以使用支持HLS的播放器（如VLC、ffplay等）播放生成的HLS URL")
    print(f"🌐 或者访问 {server_url} 使用Web管理界面")

if __name__ == '__main__':
    main()
