#!/usr/bin/env python3
"""
健康检查脚本
用于Docker容器和监控系统
"""

import sys
import requests
import json
from urllib.parse import urlparse

def check_health(url="http://localhost:8080/health", timeout=10):
    """检查服务健康状态"""
    try:
        response = requests.get(url, timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 'healthy':
                print("✅ 服务健康")
                print(f"活跃流数量: {data.get('active_streams', 0)}")
                print(f"时间戳: {data.get('timestamp', 'N/A')}")
                return 0
            else:
                print(f"❌ 服务状态异常: {data.get('status')}")
                return 1
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            return 1
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务")
        return 1
    except requests.exceptions.Timeout:
        print("❌ 连接超时")
        return 1
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求错误: {e}")
        return 1
    except json.JSONDecodeError:
        print("❌ 响应格式错误")
        return 1
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return 1

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='MPD流媒体服务健康检查')
    parser.add_argument('--url', default='http://localhost:8080/health',
                       help='健康检查URL (默认: http://localhost:8080/health)')
    parser.add_argument('--timeout', type=int, default=10,
                       help='超时时间(秒) (默认: 10)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='静默模式，只返回退出码')
    
    args = parser.parse_args()
    
    if not args.quiet:
        print(f"🔍 检查服务健康状态: {args.url}")
    
    exit_code = check_health(args.url, args.timeout)
    
    if not args.quiet and exit_code == 0:
        print("🎉 健康检查通过")
    elif not args.quiet:
        print("💥 健康检查失败")
    
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
