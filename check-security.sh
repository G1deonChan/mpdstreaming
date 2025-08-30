#!/bin/bash

# 本地安全检查脚本
# 在提交前检查是否有敏感信息

echo "🔍 本地安全检查..."

# 检查API密钥或令牌
echo "检查API密钥和令牌..."
if grep -r "dckr_pat_\|ghp_\|sk-\|xoxb-" . --exclude-dir=.git --exclude-dir=node_modules --exclude="*.sh" --exclude="*.md" --exclude="*.yml" 2>/dev/null | grep -v "example\|sample\|xxxxx\|your_token"; then
  echo "❌ 发现API密钥或令牌，请检查配置文件"
  exit 1
fi

# 检查配置文件中的实际许可证密钥
echo "检查配置文件中的许可证密钥..."
if [ -f "config.yaml" ]; then
  if grep -E "[a-fA-F0-9]{32,}" config.yaml 2>/dev/null | grep -v "example\|sample\|your_key\|1234567890abcdef\|fedcba0987654321"; then
    echo "❌ 发现可能的真实许可证密钥，请使用示例值"
    exit 1
  fi
fi

# 检查是否有真实的URL
echo "检查配置文件中的URL..."
if [ -f "config.yaml" ]; then
  if grep -E "https://[^[:space:]]+\.(com|net|org)" config.yaml 2>/dev/null | grep -vE "example\.com|sample\.com|demo\.|your-domain\.com"; then
    echo "❌ 发现可能的真实URL，请使用示例URL"
    exit 1
  fi
fi

# 检查Docker secrets
echo "检查Docker Compose文件..."
if grep -r "DOCKERHUB_TOKEN\|DOCKERHUB_USERNAME" . --include="*.yml" 2>/dev/null | grep -v "secrets\."; then
  echo "⚠️  发现Docker Hub配置，确保使用secrets而不是明文"
fi

echo "✅ 本地安全检查通过"
echo "💡 提示：如果需要使用真实配置，请确保:"
echo "   1. 真实配置文件不要提交到Git"
echo "   2. 使用.gitignore忽略敏感文件"
echo "   3. 在生产环境中通过环境变量或secrets注入配置"
