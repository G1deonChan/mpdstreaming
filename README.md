# MPD到HLS流媒体转换服务

这是一个基于Python和FFmpeg的服务，能够将MPD（MPEG-DASH）视频流转换为HLS（HTTP Live Streaming）格式，特别针对ARM64架构的Linux机器优化。

## 功能特性

- 🎥 支持MPD到HLS的实时转换
- 🔐 支持ClearKey许可证解密
- ⚙️ 通过YAML配置文件管理流
- 🐳 Docker容器化部署
- 🏗️ GitHub Actions CI/CD (仅在发布时构建镜像)
- 🌐 功能完整的Web管理界面
- 📱 RESTful API接口
- 🔍 健康检查和监控
- ⚡ 实时流状态更新
- 🎛️ 流的启动/停止控制
- 📋 可视化流管理

## 快速开始

### 方法1: 使用启动脚本 (推荐)

项目提供了便捷的启动脚本，支持多种部署选项：

**Linux/macOS:**
```bash
# 基础服务
./start.sh

# 包含监控服务
./start.sh -m

# 构建并启动
./start.sh -b start

# 查看服务状态
./start.sh status

# 查看日志
./start.sh logs -f

# 停止服务
./start.sh stop

# 完全清理
./start.sh clean
```

**Windows:**
```cmd
REM 基础服务
start.bat

REM 包含监控服务
start.bat -m

REM 构建并启动
start.bat -b start

REM 查看服务状态
start.bat status

REM 查看日志
start.bat logs -f

REM 停止服务
start.bat stop

REM 完全清理
start.bat clean
```

### 方法2: 使用Docker直接运行

**从Docker Hub拉取 (推荐):**
```bash
# 拉取最新版本
docker pull xinmeng96/mpdstreaming:latest

# 运行容器
docker run -d \
  --name mpd-hls-streamer \
  -p 8080:8080 \
  -v ./config.yaml:/app/config.yaml:ro \
  xinmeng96/mpdstreaming:latest
```

**从GitHub Container Registry拉取:**
```bash
# 拉取最新版本
docker pull ghcr.io/g1deonchan/mpdstreaming:latest

# 运行容器
docker run -d \
  --name mpd-hls-streamer \
  -p 8080:8080 \
  -v ./config.yaml:/app/config.yaml:ro \
  ghcr.io/g1deonchan/mpdstreaming:latest
```

### 方法3: 使用Docker Compose

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

### 🔧 自动配置 (推荐)

容器启动时会**自动创建**默认配置文件，无需手动准备：

- 容器首次启动时自动创建 `config.yaml`
- 包含示例流配置，可立即使用  
- 通过Web界面轻松管理所有配置
- 配置更改自动持久化到文件

**Docker运行示例**:
```bash
# 无需提前准备config.yaml文件
docker run -d \
  --name mpd-hls-streamer \
  -p 8080:8080 \
  xinmeng96/mpdstreaming:latest
```

### ⚙️ 手动配置 (可选)

⚠️ **安全提醒**: 请查看 [SECURITY.md](SECURITY.md) 了解安全配置最佳实践。

如果需要自定义配置，可以挂载您自己的 `config.yaml` 文件：

```bash
# 使用自定义配置文件
docker run -d \
  --name mpd-hls-streamer \
  -p 8080:8080 \
  -v ./my-config.yaml:/app/config/config.yaml:ro \
  xinmeng96/mpdstreaming:latest
```

**配置文件格式**:
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

#### 流管理工具
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

#### 监控工具
使用 `monitor.py` 进行服务监控：

```bash
# 一次性监控检查
python monitor.py

# 持续监控模式
python monitor.py --continuous --interval 60

# 输出JSON格式
python monitor.py --json

# 监控指定服务
python monitor.py --url http://localhost:8080

# 静默模式（仅返回退出码）
python monitor.py --quiet
```

监控功能包括：
- ✅ **服务健康检查**: API响应状态
- 📊 **流状态监控**: 活跃/非活跃流统计
- 📈 **实时监控**: 持续监控模式
- 📋 **详细报告**: 服务和流的详细信息
- 🔔 **异常告警**: 通过退出码支持告警集成

#### 健康检查工具
使用 `healthcheck.py` 进行轻量级健康检查：

```bash
# 基础健康检查
python healthcheck.py

# 指定URL和超时
python healthcheck.py --url http://localhost:8080/health --timeout 5

# 静默模式
python healthcheck.py --quiet
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

## CI/CD策略

项目采用优化的CI/CD策略：

### 🔄 持续集成 (CI)
- **触发条件**: 推送到主分支或创建PR
- **执行内容**: 
  - 代码质量检查 (flake8)
  - 单元测试 (pytest)
  - Docker构建测试 (仅构建，不推送)
  - 配置文件验证
  - 安全检查

### 🚀 持续部署 (CD)
- **触发条件**: 创建release标签 (如 `v1.0.0`)
- **执行内容**:
  - 多架构Docker镜像构建 (AMD64 + ARM64)
  - 推送到GitHub Container Registry
  - 推送到Docker Hub (如果配置了secrets)
  - 安全漏洞扫描

这种策略的优势：
- ✅ 减少不必要的镜像构建
- ✅ 节省GitHub Actions运行时间
- ✅ 保持高质量的代码检查
- ✅ 仅在正式发布时构建镜像

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

## 📋 部署检查清单

部署前请查看 **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** 确保所有步骤都已正确完成。

## 📚 相关文档

- [项目总结](PROJECT_SUMMARY.md) - 项目结构和功能概览
- [安全指南](SECURITY.md) - 安全配置最佳实践
- [部署检查清单](DEPLOYMENT_CHECKLIST.md) - 完整的部署验证步骤
- [Docker Hub配置](DOCKER_HUB_SETUP.md) - Docker Hub发布配置指南
- [许可证](LICENSE) - MIT许可证详情

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
