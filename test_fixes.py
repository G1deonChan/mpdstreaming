#!/usr/bin/env python3
"""
测试修复后的功能
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from app import MPDToHLSStreamer

async def test_error_analysis():
    """测试错误分析功能"""
    streamer = MPDToHLSStreamer()
    
    # 测试各种错误类型的分析
    test_cases = [
        ("Connection reset by peer", 152, "网络连接被重置"),
        ("404 Not Found", 1, "资源不存在"),
        ("SSL handshake failed", 1, "SSL/TLS握手失败"),
        ("Permission denied", 1, "文件权限错误"),
        ("Unknown error", 999, "未知错误")
    ]
    
    print("=== 错误分析测试 ===")
    for output, code, expected_keyword in test_cases:
        result = streamer._analyze_ffmpeg_error(output, code)
        print(f"输入: {output}")
        print(f"分析: {result}")
        print(f"包含预期关键词: {expected_keyword.lower() in result.lower()}")
        print("-" * 50)

async def test_retry_logic():
    """测试重试逻辑"""
    streamer = MPDToHLSStreamer()
    
    print("\n=== 重试逻辑测试 ===")
    
    # 测试不同错误的重试决策
    error_types = [
        "网络连接被重置，可能是源服务器问题或网络不稳定",
        "访问被禁止，可能需要认证或IP被封",
        "资源不存在，URL可能已失效",
        "连接超时，网络延迟过高或源服务器响应慢"
    ]
    
    for error in error_types:
        for retry_count in range(4):
            should_retry = streamer._should_retry_error(error, retry_count)
            delay = streamer._get_retry_delay(error, retry_count + 1)
            print(f"错误: {error[:30]}...")
            print(f"重试次数: {retry_count}, 是否重试: {should_retry}, 延迟: {delay}s")
        print("-" * 50)

async def test_connectivity():
    """测试连接性检查"""
    streamer = MPDToHLSStreamer()
    
    print("\n=== 连接性测试 ===")
    
    # 测试URL（使用公开可访问的URL）
    test_urls = [
        "https://www.google.com/",  # 应该成功
        "https://httpbin.org/status/404",  # 404但连接成功
        "https://nonexistentdomain12345.com/",  # 应该失败
    ]
    
    for url in test_urls:
        try:
            result = await streamer.test_stream_connectivity(url, timeout=5)
            print(f"URL: {url}")
            print(f"连接性: {result}")
        except Exception as e:
            print(f"URL: {url}")
            print(f"错误: {e}")
        print("-" * 50)

async def main():
    """运行所有测试"""
    await test_error_analysis()
    await test_retry_logic()
    await test_connectivity()

if __name__ == '__main__':
    asyncio.run(main())
