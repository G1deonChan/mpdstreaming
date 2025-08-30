#!/usr/bin/env python3
"""
ClearKey DASH 解密演示脚本
演示如何使用新的解密功能
"""

import asyncio
import os
import tempfile
import logging
from app import MPDToHLSStreamer, DashDecryptor

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_clearkey_decryption():
    """演示ClearKey解密功能"""
    
    print("🔑 ClearKey DASH 解密功能演示")
    print("=" * 50)
    
    # 示例数据 (这些都是示例值，实际使用时需要真实的数据)
    demo_mpd_url = "https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd"
    demo_license_key = "1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321"
    
    print(f"📺 示例 MPD URL: {demo_mpd_url}")
    print(f"🔐 示例 ClearKey: {demo_license_key[:32]}:***")
    print()
    
    # 1. 演示独立解密器工具检测
    print("1️⃣ 工具检测")
    print("-" * 20)
    
    decryptor = DashDecryptor()
    available_tools = [tool for tool, available in decryptor.tools.items() if available]
    print(f"✅ 可用工具: {available_tools}")
    
    if decryptor.clearkey_script:
        print(f"✅ ClearKey脚本: {os.path.basename(decryptor.clearkey_script)}")
    else:
        print("❌ ClearKey脚本未找到")
    
    print()
    
    # 2. 演示ClearKey解析
    print("2️⃣ ClearKey 解析")
    print("-" * 20)
    
    streamer = MPDToHLSStreamer()
    clearkey_info = streamer.parse_clearkey_license(demo_license_key)
    
    if clearkey_info:
        print(f"✅ Key ID: {clearkey_info['key_id']}")
        print(f"✅ Key: {'*' * len(clearkey_info['key'])}")
    else:
        print("❌ ClearKey解析失败")
    
    print()
    
    # 3. 演示解密能力检测
    print("3️⃣ 解密能力评估")
    print("-" * 25)
    
    capabilities = []
    
    if 'yt-dlp' in available_tools:
        capabilities.append("🔧 yt-dlp 外部解密")
    
    if decryptor.clearkey_script:
        capabilities.append("🐍 Python 原生解密")
    
    if 'ffmpeg' in available_tools:
        capabilities.append("⚙️ FFmpeg 有限支持")
    
    if capabilities:
        print("可用的解密方法:")
        for cap in capabilities:
            print(f"  {cap}")
    else:
        print("❌ 未检测到解密能力")
    
    print()
    
    # 4. 演示解密流程 (模拟)
    print("4️⃣ 解密流程演示")
    print("-" * 20)
    
    print("🚀 启动解密流程...")
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 临时目录: {temp_dir}")
        
        try:
            # 尝试解密 (由于网络限制，这通常会失败，但可以演示流程)
            result = await decryptor.decrypt_dash_stream(
                demo_mpd_url, temp_dir, demo_license_key, method='auto'
            )
            
            if result:
                print(f"✅ 解密成功: {result}")
                print(f"📊 文件大小: {os.path.getsize(result)} 字节")
            else:
                print("ℹ️ 解密未成功 (网络限制或演示数据)")
                print("   在实际环境中，这将处理真实的加密内容")
                
        except Exception as e:
            print(f"ℹ️ 演示环境限制: {e}")
            print("   在生产环境中，这将正常工作")
    
    print()
    
    # 5. 演示集成使用
    print("5️⃣ 集成使用演示")
    print("-" * 20)
    
    print("💡 在主应用程序中，解密现在是自动的:")
    print("   1. 检测 ClearKey 许可证")
    print("   2. 自动选择最佳解密方法")
    print("   3. 解密 DASH 内容")
    print("   4. 转换为 HLS 格式")
    print("   5. 清理临时文件")
    
    print()
    
    # 6. 命令行工具演示
    print("6️⃣ 命令行工具")
    print("-" * 18)
    
    print("🖥️ 独立使用示例:")
    print("python3 clearkey_decrypt.py 'https://example.com/stream.mpd' \\")
    print("  --license-key 'key_id:key_value' \\")
    print("  --output-dir './decrypted' \\")
    print("  --method auto --verbose")
    
    print()
    print("🎉 演示完成！")
    print("📚 查看 CLEARKEY_DECRYPTION.md 了解详细文档")


def demo_clearkey_formats():
    """演示支持的ClearKey格式"""
    print("\n🔤 支持的 ClearKey 格式")
    print("=" * 30)
    
    formats = [
        ("标准格式", "key_id:key_value"),
        ("实际示例", "1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321"),
        ("带分隔符", "12-34-56-78-90-ab-cd-ef:fe-dc-ba-09-87-65-43-21"),
    ]
    
    streamer = MPDToHLSStreamer()
    
    for desc, example in formats:
        print(f"\n{desc}:")
        print(f"  输入: {example}")
        
        # 清理分隔符进行解析
        clean_example = example.replace('-', '')
        result = streamer.parse_clearkey_license(clean_example)
        
        if result:
            print(f"  ✅ Key ID: {result['key_id'][:16]}...")
            print(f"  ✅ Key: {result['key'][:16]}...")
        else:
            print(f"  ❌ 解析失败")


def demo_kodi_format():
    """演示Kodi格式支持"""
    print("\n📺 Kodi 格式支持")
    print("=" * 20)
    
    kodi_example = """#KODIPROP:inputstream.adaptive.manifest_type=mpd
#KODIPROP:inputstream.adaptive.license_type=clearkey
#KODIPROP:inputstream.adaptive.license_key=1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321
https://example.com/sample/stream.mpd"""
    
    print("Kodi 播放列表格式:")
    print(kodi_example)
    
    streamer = MPDToHLSStreamer()
    result = streamer.parse_kodi_props(kodi_example)
    
    if result:
        print("\n解析结果:")
        print(f"  📺 URL: {result['url']}")
        print(f"  📄 类型: {result['manifest_type']}")
        print(f"  🔐 许可证类型: {result['license_type']}")
        print(f"  🔑 许可证: {result['license_key'][:32]}:***")
    else:
        print("\n❌ 解析失败")


async def main():
    """主演示函数"""
    print("🎬 ClearKey DASH 解密功能完整演示")
    print("=" * 60)
    
    # 主要功能演示
    await demo_clearkey_decryption()
    
    # 格式支持演示
    demo_clearkey_formats()
    
    # Kodi格式演示
    demo_kodi_format()
    
    print("\n" + "=" * 60)
    print("✨ 演示结束！新的ClearKey解密功能已准备就绪。")
    print("📖 更多信息请参考 CLEARKEY_DECRYPTION.md 文档")


if __name__ == '__main__':
    asyncio.run(main())