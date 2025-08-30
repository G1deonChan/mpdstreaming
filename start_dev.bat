@echo off
REM Windows开发环境启动脚本

echo 🚀 启动MPD到HLS流媒体服务开发环境...

REM 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到Python，请先安装Python 3.11+
    pause
    exit /b 1
)

REM 检查FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到FFmpeg，请先安装FFmpeg
    echo 下载地址: https://ffmpeg.org/download.html
    pause
    exit /b 1
)

REM 创建虚拟环境（如果不存在）
if not exist "venv" (
    echo 📦 创建Python虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
echo 🔧 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo 📥 安装Python依赖...
pip install -r requirements.txt

REM 创建日志目录
if not exist "logs" mkdir logs

REM 检查配置文件
if not exist "config.yaml" (
    echo ⚠️  配置文件不存在，将使用默认配置
)

echo ✅ 环境准备完成！
echo.
echo 📡 启动服务器...
python app.py

pause
