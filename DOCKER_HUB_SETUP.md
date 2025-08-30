# 🐳 Docker Hub 发布配置指南

本指南将帮助您配置GitHub仓库，以便在发布release时自动推送Docker镜像到Docker Hub。

## 📋 配置步骤

### 1. 创建Docker Hub账户和访问令牌

1. 访问 [Docker Hub](https://hub.docker.com/) 并登录或注册账户
2. 点击右上角头像 → **Account Settings**
3. 选择 **Security** 标签页
4. 点击 **New Access Token**
5. 输入Token名称（如：`github-actions`）
6. 选择权限：**Read, Write, Delete**
7. 点击 **Generate** 并**立即复制**令牌（只显示一次）

### 2. 在GitHub仓库中设置Secrets

1. 进入您的GitHub仓库
2. 点击 **Settings** 标签页
3. 在侧边栏中选择 **Secrets and variables** → **Actions**
4. 点击 **New repository secret** 添加以下secrets：

#### 必需的Secrets：

| Secret名称 | 说明 | 示例值 |
|-----------|------|--------|
| `DOCKERHUB_USERNAME` | Docker Hub用户名 | `your-dockerhub-username` |
| `DOCKERHUB_TOKEN` | Docker Hub访问令牌 | `dckr_pat_xxxxx...` |

### 3. 验证配置

添加secrets后，您的配置应该如下所示：

```
Repository secrets:
├── DOCKERHUB_USERNAME: your-dockerhub-username
└── DOCKERHUB_TOKEN: dckr_pat_xxxxx... (hidden)
```

## 🚀 发布流程

### 自动发布到Docker Hub

当您创建一个新的release标签时，GitHub Actions将自动：

1. **构建多架构镜像** (linux/amd64, linux/arm64)
2. **推送到GitHub Container Registry** (ghcr.io)
3. **推送到Docker Hub** (仅在发布标签时)

### 创建Release

```bash
# 创建并推送标签
git tag v1.0.0
git push origin v1.0.0

# 或者在GitHub网页上创建Release
```

### 发布后的镜像地址

发布成功后，您的镜像将在以下位置可用：

#### GitHub Container Registry
```bash
docker pull ghcr.io/g1deonchan/mpdstreaming:latest
docker pull ghcr.io/g1deonchan/mpdstreaming:v1.0.0
```

#### Docker Hub
```bash
docker pull your-dockerhub-username/mpdstreaming:latest
docker pull your-dockerhub-username/mpdstreaming:v1.0.0
```

## 📝 更新文档

发布后，记得更新以下文件中的镜像地址：

### README.md
```bash
# 更新Docker Hub镜像地址
docker pull your-dockerhub-username/mpdstreaming:latest
```

### docker-compose.yml
```yaml
services:
  mpdstreaming:
    # 使用Docker Hub镜像
    image: your-dockerhub-username/mpdstreaming:latest
    # 或者使用GitHub Container Registry
    # image: ghcr.io/g1deonchan/mpdstreaming:latest
```

## 🔍 验证发布

### 检查GitHub Actions

1. 进入仓库的 **Actions** 标签页
2. 查看最新的工作流运行
3. 确认所有步骤都成功完成
4. 检查是否有错误或警告

### 检查Docker Hub

1. 登录Docker Hub
2. 访问您的仓库页面
3. 确认新标签已上传
4. 检查支持的架构（应显示 amd64, arm64）

### 测试拉取镜像

```bash
# 测试从Docker Hub拉取
docker pull your-dockerhub-username/mpdstreaming:latest

# 测试运行
docker run --rm -p 8080:8080 your-dockerhub-username/mpdstreaming:latest
```

## 🚨 故障排除

### 常见问题

#### 1. Authentication failed
```
Error: denied: authentication required
```
**解决方案**：
- 检查 `DOCKERHUB_USERNAME` 和 `DOCKERHUB_TOKEN` secrets是否正确设置
- 确认Docker Hub访问令牌有效且有写权限

#### 2. Repository does not exist
```
Error: repository does not exist or may require authentication
```
**解决方案**：
- 在Docker Hub上创建仓库 `your-username/mpdstreaming`
- 或者设置仓库为public

#### 3. Rate limit exceeded
```
Error: toomanyrequests: Too Many Requests
```
**解决方案**：
- 等待一段时间后重试
- 考虑升级Docker Hub计划

### 调试步骤

1. **检查Secrets配置**：
   - 在仓库Settings中确认secrets已正确设置
   - 重新生成Docker Hub访问令牌

2. **查看工作流日志**：
   - 在Actions页面查看详细的构建日志
   - 查找具体的错误信息

3. **本地测试**：
   ```bash
   # 本地构建测试
   docker build -t test-image .
   
   # 本地登录测试
   docker login
   docker tag test-image your-username/mpdstreaming:test
   docker push your-username/mpdstreaming:test
   ```

## 🎉 成功指标

发布成功后，您应该看到：

- ✅ GitHub Actions工作流完成无错误
- ✅ Docker Hub显示新的镜像标签
- ✅ 支持多架构（amd64, arm64）
- ✅ 镜像可以成功拉取和运行
- ✅ 安全扫描通过（如果启用）

## 🔄 定期维护

### 访问令牌管理
- 定期轮换Docker Hub访问令牌（建议每6个月）
- 监控令牌使用情况
- 及时撤销不需要的令牌

### 镜像管理
- 定期清理旧的镜像标签
- 监控镜像大小和拉取统计
- 保持镜像的安全性更新

---

完成这些配置后，您的项目将具备自动化的Docker镜像发布能力！🚀
