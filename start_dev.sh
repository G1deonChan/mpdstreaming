#!/bin/bash

# 开发环境启动脚本

set -e

echo "🚀 启动MPD到HLS流媒体服务开发环境..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装Python 3.11+"
    exit 1
fi

# 检查FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ 未找到FFmpeg，请先安装FFmpeg"
    echo "Ubuntu/Debian: sudo apt-get install ffmpeg"
    echo "CentOS/RHEL: sudo yum install ffmpeg"
    echo "macOS: brew install ffmpeg"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "📦 创建Python虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "📥 安装Python依赖..."
pip install -r requirements.txt

# 创建日志目录
mkdir -p logs

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo "⚠️  配置文件不存在，将使用默认配置"
fi

echo "✅ 环境准备完成！"
echo ""
echo "📡 启动服务器..."
python app.py
