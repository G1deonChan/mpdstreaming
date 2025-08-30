# 🔒 安全配置说明

## ⚠️ 重要提醒

在将此项目部署到生产环境之前，请注意以下安全事项：

### 1. 配置文件安全
- **不要**在配置文件中使用真实的许可证密钥
- **不要**将包含真实凭据的配置文件提交到Git仓库
- 使用环境变量或外部配置管理系统存储敏感信息

### 2. 示例配置
项目中的所有配置都是示例格式：
```yaml
# 这些都是示例值，请替换为您的实际配置
url: "https://example.com/sample/stream.mpd"
license_key: "1234567890abcdef1234567890abcdef:fedcba0987654321fedcba0987654321"
```

### 3. 生产环境配置建议

#### 方法1：环境变量
```bash
export MPD_STREAM_URL="your-actual-stream-url"
export CLEARKEY_LICENSE="your-actual-license-key"
```

#### 方法2：外部配置文件
```bash
# 将真实配置存储在Git仓库外部
cp config.example.yaml /etc/mpd-streaming/config.yaml
# 编辑 /etc/mpd-streaming/config.yaml 添加真实配置
```

#### 方法3：Docker Secrets
```yaml
# docker-compose.yml
services:
  mpdstreaming:
    secrets:
      - mpd_config
secrets:
  mpd_config:
    file: ./secrets/config.yaml
```

### 4. 网络安全
- 在生产环境中使用HTTPS
- 配置适当的防火墙规则
- 考虑使用反向代理（如nginx）
- 启用访问日志和监控

### 5. 容器安全
- 不要以root用户运行容器
- 使用非特权端口
- 定期更新基础镜像
- 扫描镜像安全漏洞

### 6. .gitignore检查
确保以下文件不会被提交：
```
config.yaml          # 如果包含真实配置
.env
secrets/
*.key
*.pem
production.yaml
```

## 🛡️ 最佳实践

1. **分离配置**: 将开发、测试、生产环境的配置分开
2. **定期轮换**: 定期更换许可证密钥和其他凭据
3. **最小权限**: 只给应用程序必要的权限
4. **监控告警**: 设置安全事件监控和告警
5. **备份恢复**: 制定配置和数据的备份恢复策略

## 📞 如有疑问

如果您对安全配置有任何疑问，请：
1. 查阅相关服务的官方文档
2. 咨询您的系统管理员
3. 在GitHub Issues中提问（但不要包含敏感信息）
