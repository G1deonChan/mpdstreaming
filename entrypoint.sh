#!/bin/bash

# 容器启动初始化脚本
# 创建必要的目录结构和配置文件

set -e

echo "🚀 MPD流媒体服务启动初始化..."

# 创建配置目录
mkdir -p /app/config
mkdir -p /app/logs
mkdir -p /tmp/hls

# 设置权限
chmod 755 /app/config
chmod 755 /app/logs  
chmod 755 /tmp/hls

echo "📁 目录结构创建完成"

# 启动应用程序
echo "🎬 启动MPD流媒体服务..."
exec python3 /app/app.py
