#!/usr/bin/env python3
"""
Web UI 功能测试脚本
"""

import requests
import json
import time
import sys

def test_server_health(base_url):
    """测试服务器健康状态"""
    print("🔍 测试服务器健康状态...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 服务器健康: {data.get('status')}")
            print(f"📊 活跃流数: {data.get('active_streams', 0)}")
            return True
        else:
            print(f"❌ 健康检查失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_stream_api(base_url):
    """测试流管理API"""
    print("\n📡 测试流管理API...")
    
    # 1. 获取流列表
    try:
        response = requests.get(f"{base_url}/streams")
        if response.status_code == 200:
            streams = response.json().get('streams', [])
            print(f"✅ 获取流列表成功: {len(streams)} 个流")
        else:
            print(f"❌ 获取流列表失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API请求失败: {e}")
        return False
    
    # 2. 添加测试流
    test_stream = {
        "name": "测试流",
        "url": "https://example.com/test.mpd",
        "manifest_type": "mpd",
        "enabled": True
    }
    
    try:
        response = requests.post(
            f"{base_url}/streams",
            json=test_stream,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                stream_id = result.get('stream_id')
                print(f"✅ 添加测试流成功: {stream_id}")
                
                # 3. 获取流状态
                try:
                    status_response = requests.get(f"{base_url}/streams/{stream_id}/status")
                    if status_response.status_code == 200:
                        status = status_response.json()
                        print(f"✅ 获取流状态成功: {status.get('status', 'unknown')}")
                    else:
                        print(f"⚠️  获取流状态失败: HTTP {status_response.status_code}")
                except Exception as e:
                    print(f"⚠️  获取流状态出错: {e}")
                
                # 4. 删除测试流
                try:
                    delete_response = requests.delete(f"{base_url}/streams/{stream_id}")
                    if delete_response.status_code == 200:
                        delete_result = delete_response.json()
                        if delete_result.get('success'):
                            print(f"✅ 删除测试流成功")
                        else:
                            print(f"⚠️  删除测试流失败: {delete_result.get('error')}")
                    else:
                        print(f"⚠️  删除请求失败: HTTP {delete_response.status_code}")
                except Exception as e:
                    print(f"⚠️  删除测试流出错: {e}")
                
                return True
            else:
                print(f"❌ 添加流失败: {result.get('error')}")
                return False
        else:
            print(f"❌ 添加流请求失败: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 添加流出错: {e}")
        return False

def test_web_ui(base_url):
    """测试Web界面访问"""
    print("\n🌐 测试Web界面...")
    
    pages = [
        ('/', '主页重定向'),
        ('/demo.html', '演示界面'),
        ('/index.html', '完整界面'),
        ('/health', '健康检查API')
    ]
    
    for path, name in pages:
        try:
            response = requests.get(f"{base_url}{path}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {name} 访问成功")
            else:
                print(f"⚠️  {name} 访问失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {name} 访问出错: {e}")

def main():
    print("🧪 MPD流媒体服务 Web UI 测试")
    print("=" * 50)
    
    # 默认服务器地址
    base_url = "http://localhost:8080"
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"🎯 测试目标: {base_url}")
    print("=" * 50)
    
    # 等待服务器启动
    print("⏳ 等待服务器启动...")
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                print("✅ 服务器已就绪")
                break
        except:
            pass
        
        if i < max_retries - 1:
            print(f"⏳ 等待中... ({i + 1}/{max_retries})")
            time.sleep(2)
        else:
            print("❌ 服务器启动超时")
            return False
    
    # 执行测试
    success = True
    
    # 测试服务器健康状态
    if not test_server_health(base_url):
        success = False
    
    # 测试流管理API
    if not test_stream_api(base_url):
        success = False
    
    # 测试Web界面
    test_web_ui(base_url)
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 所有测试通过！")
        print(f"💡 您可以访问 {base_url} 使用Web管理界面")
        print(f"📚 演示界面: {base_url}/demo.html")
        print(f"⚙️  完整界面: {base_url}/index.html")
    else:
        print("❌ 部分测试失败，请检查服务器配置")
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
