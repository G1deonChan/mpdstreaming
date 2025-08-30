#!/usr/bin/env python3
"""
MPD流媒体服务监控脚本
提供详细的服务状态监控和报告功能
"""

import sys
import time
import requests
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple


class ServiceMonitor:
    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
    def check_service_health(self) -> Tuple[bool, Dict]:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                return True, data
            else:
                return False, {"error": f"HTTP {response.status_code}"}
                
        except requests.exceptions.ConnectionError:
            return False, {"error": "连接失败"}
        except requests.exceptions.Timeout:
            return False, {"error": "连接超时"}
        except Exception as e:
            return False, {"error": str(e)}
    
    def get_streams_status(self) -> Tuple[bool, List[Dict]]:
        """获取流状态"""
        try:
            response = requests.get(f"{self.base_url}/api/streams", timeout=self.timeout)
            
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, []
                
        except Exception:
            return False, []
    
    def check_stream_health(self, stream_id: str) -> Dict:
        """检查单个流的健康状态"""
        try:
            response = requests.get(f"{self.base_url}/api/streams/{stream_id}/status", 
                                  timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def generate_report(self) -> Dict:
        """生成监控报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "service": {},
            "streams": {},
            "summary": {}
        }
        
        # 检查服务状态
        service_ok, service_data = self.check_service_health()
        report["service"]["healthy"] = service_ok
        report["service"]["data"] = service_data
        
        # 检查流状态
        streams_ok, streams_data = self.get_streams_status()
        report["streams"]["accessible"] = streams_ok
        report["streams"]["data"] = streams_data
        
        # 统计信息
        if streams_ok:
            active_streams = sum(1 for s in streams_data if s.get('active', False))
            total_streams = len(streams_data)
            report["summary"] = {
                "total_streams": total_streams,
                "active_streams": active_streams,
                "inactive_streams": total_streams - active_streams
            }
        
        return report
    
    def print_report(self, report: Dict, quiet: bool = False):
        """打印监控报告"""
        if quiet:
            return
            
        print(f"\n🔍 MPD流媒体服务监控报告")
        print(f"📅 时间: {report['timestamp']}")
        print(f"{'='*50}")
        
        # 服务状态
        service = report["service"]
        if service["healthy"]:
            print("✅ 服务状态: 健康")
            if "status" in service["data"]:
                print(f"   状态: {service['data']['status']}")
        else:
            print("❌ 服务状态: 异常")
            print(f"   错误: {service['data'].get('error', '未知错误')}")
        
        # 流状态
        if report["streams"]["accessible"]:
            summary = report["summary"]
            print(f"\n📺 流状态:")
            print(f"   总数: {summary['total_streams']}")
            print(f"   活跃: {summary['active_streams']}")
            print(f"   非活跃: {summary['inactive_streams']}")
            
            # 详细流信息
            if summary['total_streams'] > 0:
                print(f"\n📋 流详情:")
                for stream in report["streams"]["data"]:
                    status = "🟢 活跃" if stream.get('active', False) else "🔴 停止"
                    print(f"   {stream.get('id', 'N/A')}: {status}")
                    print(f"      名称: {stream.get('name', 'N/A')}")
                    print(f"      URL: {stream.get('mpd_url', 'N/A')[:50]}...")
        else:
            print("\n❌ 无法获取流状态")
        
        print(f"{'='*50}")
    
    def continuous_monitor(self, interval: int = 30, quiet: bool = False):
        """持续监控模式"""
        if not quiet:
            print(f"🚀 开始持续监控 (间隔: {interval}秒)")
            print("按 Ctrl+C 停止监控\n")
        
        try:
            while True:
                report = self.generate_report()
                self.print_report(report, quiet)
                
                if not quiet:
                    print(f"\n⏰ 下次检查: {interval}秒后")
                    print("-" * 50)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            if not quiet:
                print("\n\n🛑 监控已停止")


def main():
    parser = argparse.ArgumentParser(description='MPD流媒体服务监控脚本')
    parser.add_argument('--url', default='http://localhost:8080',
                       help='服务基础URL (默认: http://localhost:8080)')
    parser.add_argument('--timeout', type=int, default=10,
                       help='超时时间(秒) (默认: 10)')
    parser.add_argument('--continuous', '-c', action='store_true',
                       help='持续监控模式')
    parser.add_argument('--interval', '-i', type=int, default=30,
                       help='监控间隔(秒) (默认: 30)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='静默模式')
    parser.add_argument('--json', action='store_true',
                       help='输出JSON格式')
    
    args = parser.parse_args()
    
    monitor = ServiceMonitor(args.url, args.timeout)
    
    if args.continuous:
        monitor.continuous_monitor(args.interval, args.quiet)
    else:
        report = monitor.generate_report()
        
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            monitor.print_report(report, args.quiet)
        
        # 返回适当的退出码
        service_healthy = report["service"]["healthy"]
        sys.exit(0 if service_healthy else 1)


if __name__ == "__main__":
    main()
