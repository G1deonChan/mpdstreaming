# MPD到HLS流媒体转换服务

这是一个基于Python和FFmpeg的服务，能够将MPD（MPEG-DASH）视频流转换为HLS（HTTP Live Streaming）格式，特别针对ARM64架构的Linux机器优化。

## 功能特性

- 🎥 支持MPD到HLS的实时转换
- 🔐 支持ClearKey许可证解密
- ⚙️ 通过YAML配置文件管理流
- 🐳 Docker容器化部署
- 🏗️ GitHub Actions自动构建多架构镜像
- 🌐 功能完整的Web管理界面
- 📱 RESTful API接口
- 🔍 健康检查和监控
- ⚡ 实时流状态更新
- 🎛️ 流的启动/停止控制
- 📋 可视化流管理

## 快速开始

### 使用Docker运行

```bash
# 拉取镜像
docker pull ghcr.io/your-username/mpdstreaming:latest

# 运行容器
docker run -d \
  --name mpd-hls-streamer \
  -p 8080:8080 \
  -v ./config.yaml:/app/config.yaml \
  ghcr.io/your-username/mpdstreaming:latest
```

### 使用Docker Compose

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 本地开发运行

```bash
# 安装依赖
pip install -r requirements.txt

# 安装FFmpeg（Ubuntu/Debian）
sudo apt-get update && sudo apt-get install -y ffmpeg

# 运行服务
python app.py
```

## 配置说明

⚠️ **安全提醒**: 请查看 [SECURITY.md](SECURITY.md) 了解安全配置最佳实践。

编辑 `config.yaml` 文件来配置您的流（或从 `config.example.yaml` 复制）：

```yaml
# 注意：这些是示例值，请替换为您的实际配置
server:
  host: "0.0.0.0"
  port: 8080

streams:
  - id: "stream_1"
    name: "示例MPD流"
    url: "https://your-domain.com/stream.mpd"  # 替换为实际URL
    manifest_type: "mpd"
    license_type: "clearkey"
    license_key: "your_key_id:your_key_value"  # 替换为实际密钥

ffmpeg:
  hls_time: 6
  hls_list_size: 10
  hls_flags: "delete_segments"
  video_codec: "libx264"
  audio_codec: "aac"
```

## 使用方法

### Web界面

访问 `http://localhost:8080` 使用Web管理界面：

#### 功能特性：
- 📊 **实时监控**: 服务器状态和流统计信息
- ➕ **流管理**: 添加、编辑、删除流配置
- ⚡ **流控制**: 启动、停止单个或所有流
- 🎬 **测试播放**: 一键测试HLS播放
- 📋 **配置编辑**: 可视化编辑流参数
- 📱 **响应式设计**: 支持移动设备访问

#### 界面说明：
- **主页**: `/` 或 `/demo.html` - 演示版界面（推荐）
- **完整版**: `/index.html` - 功能完整的管理界面
- **健康检查**: `/health` - 服务器状态API
- **API文档**: 通过界面直接管理，无需手动调用API

### API接口

#### 获取所有流
```bash
curl http://localhost:8080/streams
```

#### 添加新流（Kodi格式）
```bash
curl -X POST http://localhost:8080/streams \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试流",
    "kodi_format": "#KODIPROP:inputstream.adaptive.manifest_type=mpd\n#KODIPROP:inputstream.adaptive.license_type=clearkey\n#KODIPROP:inputstream.adaptive.license_key=key_id:key\nhttps://example.com/stream.mpd"
  }'
```

#### 获取HLS流
访问 `http://localhost:8080/stream/{stream_id}/playlist.m3u8`

### 命令行工具

使用 `stream_manager.py` 工具：

```bash
# 添加流
python stream_manager.py add \
  --kodi-format "#KODIPROP:inputstream.adaptive.manifest_type=mpd
#KODIPROP:inputstream.adaptive.license_type=clearkey
#KODIPROP:inputstream.adaptive.license_key=your_key_id:your_key_value
https://your-domain.com/stream.mpd" \
  --name "您的频道名称"

# 列出所有流
python stream_manager.py list

# 健康检查
python stream_manager.py health
```

## Kodi格式示例

支持的Kodi属性格式：

```
#KODIPROP:inputstream.adaptive.manifest_type=mpd
#KODIPROP:inputstream.adaptive.license_type=clearkey
#KODIPROP:inputstream.adaptive.license_key=1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321
https://example.com/sample/stream.mpd
```

## 架构支持

该项目支持以下架构：
- `linux/amd64` - x86_64架构
- `linux/arm64` - ARM64架构（专门优化）

## 部署选项

### 1. 单容器部署
```bash
docker run -d --name mpd-streamer -p 8080:8080 ghcr.io/your-username/mpdstreaming:latest
```

### 2. 使用Docker Compose（推荐）
包含nginx反向代理和SSL终止

### 3. Kubernetes部署
可以使用提供的Docker镜像在Kubernetes集群中部署

## 监控和日志

- 健康检查端点: `/health`
- 日志输出到标准输出，可通过Docker logs查看
- 支持结构化日志格式

## 性能优化

- 自动清理过期的转换会话
- FFmpeg参数优化适合ARM64架构
- 支持并发流处理
- 内存和CPU使用监控

## 故障排除

### 常见问题

1. **FFmpeg未找到**
   - 确保Docker镜像包含FFmpeg
   - 本地运行时需要安装FFmpeg

2. **许可证解密失败**
   - 检查ClearKey格式是否正确
   - 验证key_id和key的十六进制格式

3. **流无法播放**
   - 检查原始MPD URL是否可访问
   - 验证网络连接和防火墙设置

### 调试模式

设置环境变量启用调试：
```bash
export LOG_LEVEL=DEBUG
python app.py
```

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 技术栈

- **后端**: Python 3.11, aiohttp
- **流处理**: FFmpeg
- **容器化**: Docker, Docker Compose
- **CI/CD**: GitHub Actions
- **配置**: YAML
- **前端**: HTML5, JavaScript (原生)

## 更新日志

### v1.0.0
- 初始版本发布
- 支持MPD到HLS转换
- ClearKey许可证支持
- Docker多架构构建
- Web管理界面
