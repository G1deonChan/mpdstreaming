# 🚀 MPD流媒体服务部署检查清单

在部署MPD流媒体服务之前，请完成以下检查项目：

## 📋 部署前准备

### 1. 环境检查
- [ ] Docker已安装并正常运行
- [ ] Docker Compose已安装
- [ ] 系统架构确认 (ARM64/AMD64)
- [ ] 网络端口8080可用
- [ ] 足够的磁盘空间 (建议至少5GB)

### 2. 配置文件准备 (可选)
- [ ] **自动配置**: 容器将自动创建默认配置文件 ✅
- [ ] **手动配置** (可选): 复制 `config.example.yaml` 为 `config.yaml`
- [ ] **自定义配置** (可选): 更新MPD流URL为实际地址
- [ ] **许可证配置** (可选): 配置正确的license_key (如果需要)
- [ ] 验证YAML格式正确性 (如果使用自定义配置)
- [ ] 确保敏感信息已替换为示例值 (如果使用自定义配置)

### 3. 安全检查
- [ ] 阅读 `SECURITY.md` 安全指南
- [ ] 检查 `.gitignore` 包含敏感配置
- [ ] 验证配置文件不包含真实密钥
- [ ] 确认防火墙规则允许必要端口

### 4. CI/CD配置 (可选)
- [ ] 阅读 `DOCKER_HUB_SETUP.md` 配置指南
- [ ] 创建Docker Hub账户和访问令牌
- [ ] 在GitHub仓库设置 `DOCKERHUB_USERNAME` 和 `DOCKERHUB_TOKEN` secrets
- [ ] 验证GitHub Actions权限设置正确
- [ ] 了解CI/CD策略：代码推送时仅运行测试，发布时才构建镜像

## 🐳 Docker部署检查

### 基础部署
```bash
# 1. 拉取或构建镜像
docker pull xinmeng96/mpdstreaming:latest
# 或者克隆项目本地构建

# 2. 直接启动 (使用自动配置)
docker run -d --name mpd-hls-streamer -p 8080:8080 xinmeng96/mpdstreaming:latest

# 或者使用Docker Compose
./start.sh

# 或者使用生产环境配置
./start.sh --production
```

### 验证步骤
- [ ] 容器启动成功: `./start.sh status`
- [ ] Web界面可访问: http://localhost:8080
- [ ] API响应正常: `curl http://localhost:8080/api/status`
- [ ] 健康检查通过: `python healthcheck.py`
- [ ] 日志无错误: `./start.sh logs`

## 🔍 功能测试

### Web界面测试
- [ ] 主页加载正常
- [ ] 流列表显示正确
- [ ] 添加流功能正常
- [ ] 编辑流功能正常
- [ ] 删除流功能正常
- [ ] 启动/停止流功能正常
- [ ] 实时状态更新正常

### API测试
- [ ] GET `/api/status` 返回状态
- [ ] GET `/api/streams` 返回流列表
- [ ] POST `/api/streams` 可添加流
- [ ] PUT `/api/streams/{id}` 可更新流
- [ ] DELETE `/api/streams/{id}` 可删除流
- [ ] POST `/api/streams/{id}/start` 可启动流
- [ ] POST `/api/streams/{id}/stop` 可停止流

### 流媒体测试
- [ ] MPD流可正常解析
- [ ] HLS转换功能正常
- [ ] 播放列表生成正确
- [ ] 视频播放无问题
- [ ] 音频同步正常

## 📊 监控部署 (可选)

### 启用监控
```bash
# 启动包含监控的完整服务
./start.sh -m
```

### 监控验证
- [ ] 监控容器启动成功
- [ ] 监控脚本正常运行
- [ ] 监控日志无错误
- [ ] 可通过命令行查看监控信息

### 监控测试
```bash
# 测试监控功能
python monitor.py
python monitor.py --continuous --interval 30
python monitor.py --json
```

## 🔧 生产环境优化

### 性能优化
- [ ] 配置适当的FFmpeg参数
- [ ] 调整HLS段大小和数量
- [ ] 配置Nginx缓存 (如果使用)
- [ ] 设置适当的容器资源限制

### 安全加固
- [ ] 使用非root用户运行容器
- [ ] 配置适当的网络策略
- [ ] 启用HTTPS (生产环境)
- [ ] 配置适当的访问控制
- [ ] 定期更新依赖包

### 监控告警
- [ ] 配置健康检查监控
- [ ] 设置资源使用告警
- [ ] 配置日志收集
- [ ] 设置服务重启策略

## 🚨 故障排查

### 常见问题检查
- [ ] 检查Docker日志: `docker logs mpd-hls-streamer`
- [ ] 检查服务状态: `./start.sh status`
- [ ] 验证配置文件: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
- [ ] 检查端口占用: `netstat -tlnp | grep 8080`
- [ ] 验证FFmpeg安装: `docker exec mpd-hls-streamer ffmpeg -version`

### 调试模式
```bash
# 启用调试日志
export LOG_LEVEL=DEBUG
./start.sh restart

# 查看详细日志
./start.sh logs -f
```

## ✅ 部署完成确认

部署成功的标志：
- [ ] Web界面http://localhost:8080可正常访问
- [ ] API接口响应正常
- [ ] 至少一个测试流可以正常播放
- [ ] 健康检查通过
- [ ] 日志无严重错误
- [ ] 服务可以正常重启
- [ ] 监控功能正常 (如果启用)

## 📚 后续维护

### 定期检查
- [ ] 定期更新镜像版本
- [ ] 监控资源使用情况
- [ ] 检查日志文件大小
- [ ] 验证备份策略
- [ ] 测试服务恢复能力

### 升级准备
- [ ] 备份当前配置
- [ ] 测试新版本兼容性
- [ ] 准备回滚方案
- [ ] 通知相关用户

---

## 💡 技术支持

如果在部署过程中遇到问题：

1. 检查项目的 `README.md` 文档
2. 查看 `SECURITY.md` 安全指南
3. 检查GitHub Issues
4. 查看项目的 `PROJECT_SUMMARY.md`

祝您部署顺利！🎉
