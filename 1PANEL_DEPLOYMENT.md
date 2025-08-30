# 1Panel部署指南

本文档专门为1Panel用户提供详细的部署指导。

## 🚀 快速部署

### 方法1：使用专用配置文件（推荐）

1. **下载项目文件**
   ```bash
   git clone https://github.com/G1deonChan/mpdstreaming.git
   cd mpdstreaming
   ```

2. **在1Panel中创建编排**
   - 应用商店 → 编排模板 → 创建编排
   - 编排名称：`mpdstreaming`
   - **推荐配置文件**：`docker-compose.1panel-simple.yml`（最稳定，无挂载问题）
   - 备选配置文件：`docker-compose.simple.yml`
   - 点击"创建"

3. **访问服务**
   - 访问 `http://your-server-ip:8080`
   - 开始使用Web界面管理流媒体

### 方法2：使用简化配置

如果您只需要主服务，可以使用简化配置：

1. **使用简化配置文件**
   - 选择配置文件：`docker-compose.simple.yml`
   - 这个版本只包含主服务，部署更简单

2. **手动创建编排**
   在1Panel编排界面直接输入：
   ```yaml
   services:
     mpdstreaming:
       image: xinmeng96/mpdstreaming:latest
       container_name: mpd-hls-streamer
       ports:
         - "8080:8080"
       volumes:
         - mpd-config:/app/config
       restart: unless-stopped
       healthcheck:
         test: ["CMD", "python3", "/app/healthcheck.py", "--quiet"]
         interval: 30s
         timeout: 10s
         retries: 3
         start_period: 40s

   volumes:
     mpd-config:
   ```

## 📋 部署步骤详解

### 步骤1：准备工作

1. **确保1Panel已安装Docker**
   - 1Panel → 容器 → 设置 → Docker安装状态

2. **检查端口占用**
   - 确保8080端口未被占用
   - 如有冲突，修改配置文件中的端口映射

### 步骤2：创建编排

1. **进入编排管理**
   - 1Panel → 容器 → 编排

2. **创建新编排**
   - 点击"创建编排"
   - 编排名称：`mpdstreaming`
   - 选择项目中的`docker-compose.1panel.yml`文件

3. **启动服务**
   - 点击"启动"按钮
   - 等待容器启动完成

### 步骤3：验证部署

1. **检查容器状态**
   - 1Panel → 容器 → 容器列表
   - 确认`mpd-hls-streamer`状态为运行中

2. **访问Web界面**
   - 浏览器访问：`http://your-server-ip:8080`
   - 如果看到管理界面，说明部署成功

3. **健康检查**
   - 访问：`http://your-server-ip:8080/health`
   - 应该返回健康状态信息

## 🔧 配置说明

### 端口配置

默认配置使用的端口：
- `8080` - 主服务端口
- `80` - Nginx HTTP端口（仅完整版）
- `443` - Nginx HTTPS端口（仅完整版）

如需修改端口，编辑配置文件中的`ports`部分。

### 数据持久化

配置使用以下卷进行数据持久化：
- `mpd-config` - 配置文件存储
- `./logs` - 日志文件（可选）

### 环境变量

可在编排配置中调整的环境变量：
```yaml
environment:
  - CONFIG_PATH=/app/config/config.yaml  # 配置文件路径
  - LOG_LEVEL=INFO                       # 日志级别
  - PYTHONUNBUFFERED=1                   # Python输出缓冲
```

## 🛠️ 故障排除

### 常见问题

1. **"no such file or directory"错误**
   - 原因：使用了包含`build: .`的配置文件
   - 解决：使用`docker-compose.1panel-simple.yml`或删除build配置

2. **nginx挂载失败错误**
   - 错误：`cannot create subdirectories in "/etc/nginx/nginx.conf": not a directory`
   - 原因：nginx.conf文件挂载路径问题
   - 解决：使用`docker-compose.1panel-simple.yml`（不包含nginx）

3. **容器启动失败**
   - 检查端口是否被占用
   - 查看容器日志：1Panel → 容器 → 容器列表 → 查看日志

4. **无法访问Web界面**
   - 检查防火墙设置
   - 确认端口映射正确
   - 检查容器健康状态

5. **版本警告**
   - `version` is obsolete 警告可以忽略
   - 或使用不包含version字段的配置文件

### 日志查看

在1Panel中查看日志：
1. 容器 → 容器列表
2. 找到`mpd-hls-streamer`容器
3. 点击"日志"按钮查看运行状态

### 重启服务

如需重启服务：
1. 容器 → 编排 → 找到mpdstreaming编排
2. 点击"重启"按钮

## 🎯 使用建议

### 推荐配置

**生产环境：** 使用`docker-compose.1panel.yml`
- 包含完整功能
- 包含Nginx反向代理
- 适合正式部署

**测试环境：** 使用`docker-compose.simple.yml`
- 仅包含主服务
- 部署简单
- 适合快速测试

### 性能优化

1. **资源限制**
   ```yaml
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: '0.5'
   ```

2. **日志轮转**
   ```yaml
   logging:
     options:
       max-size: "10m"
       max-file: "3"
   ```

## 📞 获取帮助

如果在1Panel部署过程中遇到问题：

1. 检查本文档的故障排除部分
2. 查看项目的[部署检查清单](DEPLOYMENT_CHECKLIST.md)
3. 在GitHub仓库提交Issue

---

## 🎉 部署成功

部署成功后，您可以：

1. **管理流媒体**
   - 访问Web界面添加MPD流
   - 实时监控流状态

2. **获取播放链接**
   - 格式：`http://your-server-ip:8080/stream/{stream_id}/playlist.m3u8`

3. **API接口使用**
   - 查看所有流：`GET /streams`
   - 添加新流：`POST /streams`

祝您使用愉快！🚀
