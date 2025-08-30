# 使用官方Python基础镜像 (支持ARM64)
FROM python:3.11-slim

# 设置环境变量以避免debconf交互式提示
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    wget \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# 复制requirements文件并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 复制应用代码和启动脚本
COPY . .
COPY entrypoint.sh /app/

# 创建必要的目录
RUN mkdir -p static logs config \
    && chmod +x *.py \
    && chmod +x entrypoint.sh \
    && find . -name "*.sh" -exec chmod +x {} \;

# 设置环境变量
ENV PYTHONPATH=/app \
    CONFIG_PATH=/app/config/config.yaml \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /tmp/hls \
    && chown -R appuser:appuser /tmp/hls

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# 启动命令
CMD ["/app/entrypoint.sh"]
