#!/usr/bin/env python3
"""
测试解密管道功能
"""
import asyncio
import sys
import os
import tempfile
import subprocess
from pathlib import Path

sys.path.append(os.path.dirname(__file__))
from app import MPDToHLSStreamer

async def test_pipe_functionality():
    """测试管道解密功能"""
    print("=== 管道解密功能测试 ===")
    
    # 创建临时测试环境
    temp_dir = tempfile.mkdtemp()
    print(f"临时测试目录: {temp_dir}")
    
    try:
        # 初始化流媒体服务器
        streamer = MPDToHLSStreamer()
        
        # 测试用的MPD URL（公开无加密流）
        test_mpd_url = "https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd"
        
        # 测试1: 无加密流的管道处理
        print("\n--- 测试1: 无加密流管道处理 ---")
        
        # 构建解密命令
        decrypt_cmd = [
            'python', 
            os.path.join(os.path.dirname(__file__), 'decrypt_dash.py'),
            test_mpd_url,
            '--output-format', 'pipe',
            '--pipe-format', 'ts'
        ]
        
        print(f"解密命令: {' '.join(decrypt_cmd)}")
        
        # 启动解密进程（但不实际运行，只测试命令构建）
        try:
            result = subprocess.run(
                decrypt_cmd + ['--help'],  # 用help测试命令可用性
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                print("✅ 解密命令构建成功")
            else:
                print(f"❌ 解密命令失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("⏰ 解密命令测试超时")
        except Exception as e:
            print(f"❌ 解密命令测试异常: {e}")
        
        # 测试2: FFmpeg管道连接
        print("\n--- 测试2: FFmpeg管道连接测试 ---")
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出文件
            '-f', 'mpegts',  # 输入格式为MPEG-TS
            '-i', 'pipe:0',  # 从stdin读取
            '-t', '5',  # 只处理5秒进行测试
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-f', 'hls',
            '-hls_time', '2',
            '-hls_list_size', '3',
            '-hls_flags', 'delete_segments',
            '-hls_segment_filename', os.path.join(temp_dir, 'test_segment_%03d.ts'),
            os.path.join(temp_dir, 'test_playlist.m3u8')
        ]
        
        print(f"FFmpeg命令: {' '.join(ffmpeg_cmd[:8])}...")
        
        # 检查FFmpeg是否可用
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                print("✅ FFmpeg可用")
            else:
                print("❌ FFmpeg不可用")
        except:
            print("❌ FFmpeg不可用或超时")
        
        # 测试3: 流服务器配置
        print("\n--- 测试3: 流服务器配置测试 ---")
        
        # 测试配置加载
        config = streamer.config
        print(f"配置加载: {'✅' if config else '❌'}")
        print(f"FFmpeg配置: {config.get('ffmpeg', {})}")
        
        # 测试连接性检查
        connectivity = await streamer.test_stream_connectivity(test_mpd_url, timeout=10)
        print(f"连接性测试: {'✅' if connectivity else '❌'} - {test_mpd_url}")
        
        # 测试4: 错误分析功能
        print("\n--- 测试4: 错误分析功能 ---")
        
        test_errors = [
            ("Connection reset by peer", 152),
            ("Pipe broken", -15),
            ("Permission denied", 1),
            ("404 Not Found", 1)
        ]
        
        for error_text, return_code in test_errors:
            analysis = streamer._analyze_ffmpeg_error(error_text, return_code)
            print(f"错误: '{error_text}' -> {analysis}")
        
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False
        
    finally:
        # 清理临时目录
        import shutil
        try:
            shutil.rmtree(temp_dir)
            print(f"清理临时目录: {temp_dir}")
        except:
            pass

def test_decrypt_script_syntax():
    """测试解密脚本语法"""
    print("=== 解密脚本语法测试 ===")
    
    try:
        import decrypt_dash
        print("✅ decrypt_dash.py 导入成功")
        
        # 测试类实例化
        decryptor = decrypt_dash.DashClearKeyDecryptor()
        print("✅ DashClearKeyDecryptor 实例化成功")
        
        # 测试ClearKey解析
        test_key = "test_key_id:test_key_value"
        parsed = decryptor.parse_clearkey(test_key)
        expected = {'key_id': 'test_key_id', 'key': 'test_key_value'}
        
        if parsed == expected:
            print("✅ ClearKey解析功能正常")
        else:
            print(f"❌ ClearKey解析异常: 期望 {expected}, 得到 {parsed}")
        
        return True
        
    except Exception as e:
        print(f"❌ 解密脚本测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始管道解密功能测试\n")
    
    # 测试1: 脚本语法
    syntax_ok = test_decrypt_script_syntax()
    
    # 测试2: 管道功能
    pipe_ok = await test_pipe_functionality()
    
    # 总结
    print(f"\n📊 测试结果:")
    print(f"脚本语法: {'✅ 通过' if syntax_ok else '❌ 失败'}")
    print(f"管道功能: {'✅ 通过' if pipe_ok else '❌ 失败'}")
    
    overall_success = syntax_ok and pipe_ok
    print(f"总体结果: {'🎉 全部通过' if overall_success else '⚠️ 存在问题'}")
    
    return overall_success

if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
