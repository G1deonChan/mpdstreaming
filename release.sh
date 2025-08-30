#!/bin/bash

# MPD流媒体服务发布脚本
# 自动化版本发布和Docker镜像推送

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
CURRENT_VERSION=""
NEW_VERSION=""
RELEASE_NOTES=""
DRY_RUN=false

# 帮助信息
show_help() {
    echo -e "${BLUE}MPD流媒体服务发布脚本${NC}"
    echo ""
    echo "用法: $0 [选项] <新版本号>"
    echo ""
    echo "参数:"
    echo "  新版本号           版本号 (格式: v1.0.0)"
    echo ""
    echo "选项:"
    echo "  --dry-run          模拟运行，不实际发布"
    echo "  --notes <文件>     从文件读取发布说明"
    echo "  -h, --help         显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 v1.0.0                    # 发布版本 v1.0.0"
    echo "  $0 v1.1.0 --notes notes.md  # 发布并指定发布说明"
    echo "  $0 v1.2.0 --dry-run         # 模拟发布过程"
}

# 获取当前版本
get_current_version() {
    local latest_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    if [ -n "$latest_tag" ]; then
        echo "$latest_tag"
    else
        echo "v0.0.0"
    fi
}

# 验证版本格式
validate_version() {
    local version=$1
    if [[ ! $version =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$ ]]; then
        echo -e "${RED}错误: 版本格式无效。请使用格式: v1.0.0${NC}"
        exit 1
    fi
}

# 检查工作目录状态
check_git_status() {
    if [ -n "$(git status --porcelain)" ]; then
        echo -e "${RED}错误: 工作目录有未提交的更改${NC}"
        echo "请先提交或暂存所有更改"
        exit 1
    fi
    
    local current_branch=$(git rev-parse --abbrev-ref HEAD)
    if [ "$current_branch" != "main" ] && [ "$current_branch" != "master" ]; then
        echo -e "${YELLOW}警告: 当前不在主分支 ($current_branch)${NC}"
        read -p "继续发布? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 生成发布说明
generate_release_notes() {
    local prev_version=$1
    local new_version=$2
    
    echo -e "${BLUE}生成发布说明...${NC}"
    
    # 如果指定了发布说明文件
    if [ -n "$RELEASE_NOTES" ] && [ -f "$RELEASE_NOTES" ]; then
        cat "$RELEASE_NOTES"
        return
    fi
    
    # 自动生成发布说明
    echo "## 🚀 ${new_version} 发布"
    echo ""
    echo "### ✨ 新功能"
    echo ""
    
    if [ "$prev_version" != "v0.0.0" ]; then
        echo "### 📝 更改日志"
        echo ""
        echo "完整更改日志: [\`${prev_version}...${new_version}\`](https://github.com/G1deonChan/mpdstreaming/compare/${prev_version}...${new_version})"
        echo ""
        
        # 获取提交日志
        echo "### 📋 提交历史"
        git log --pretty=format:"- %s (%an)" "${prev_version}..HEAD" | head -20
    else
        echo "- 初始版本发布"
        echo "- MPD到HLS流媒体转换功能"
        echo "- Web管理界面"
        echo "- Docker多架构支持"
        echo "- GitHub Actions CI/CD"
    fi
    
    echo ""
    echo ""
    echo "### 🐳 Docker镜像"
    echo ""
    echo "```bash"
    echo "# Docker Hub"
    echo "docker pull your-dockerhub-username/mpdstreaming:${new_version#v}"
    echo "docker pull your-dockerhub-username/mpdstreaming:latest"
    echo ""
    echo "# GitHub Container Registry"
    echo "docker pull ghcr.io/g1deonchan/mpdstreaming:${new_version#v}"
    echo "docker pull ghcr.io/g1deonchan/mpdstreaming:latest"
    echo "```"
}

# 执行发布
perform_release() {
    local version=$1
    
    echo -e "${BLUE}开始发布 $version...${NC}"
    
    # 1. 创建标签
    echo -e "${YELLOW}创建Git标签...${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] git tag -a $version -m \"Release $version\""
    else
        git tag -a "$version" -m "Release $version"
    fi
    
    # 2. 推送标签
    echo -e "${YELLOW}推送标签到远程仓库...${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] git push origin $version"
    else
        git push origin "$version"
    fi
    
    # 3. 生成发布说明
    local notes_content=$(generate_release_notes "$CURRENT_VERSION" "$version")
    
    # 4. 创建GitHub Release (需要gh CLI)
    if command -v gh &> /dev/null; then
        echo -e "${YELLOW}创建GitHub Release...${NC}"
        if [ "$DRY_RUN" = true ]; then
            echo "[DRY RUN] gh release create $version --title \"$version\" --notes \"...\""
        else
            echo "$notes_content" | gh release create "$version" --title "$version" --notes-file -
        fi
    else
        echo -e "${YELLOW}未找到GitHub CLI，请手动创建Release${NC}"
        echo -e "${BLUE}发布说明:${NC}"
        echo "$notes_content"
    fi
    
    echo -e "${GREEN}发布完成！${NC}"
    echo ""
    echo "📋 发布信息:"
    echo "   版本: $version"
    echo "   前版本: $CURRENT_VERSION"
    echo "   标签已推送到远程仓库"
    echo ""
    echo "🔄 GitHub Actions将自动:"
    echo "   1. 构建多架构Docker镜像"
    echo "   2. 推送到GitHub Container Registry"
    echo "   3. 推送到Docker Hub (如果配置了secrets)"
    echo "   4. 运行安全扫描"
    echo ""
    echo "🔍 监控构建状态:"
    echo "   GitHub Actions: https://github.com/G1deonChan/mpdstreaming/actions"
    echo "   Docker Hub: https://hub.docker.com/r/your-dockerhub-username/mpdstreaming"
}

# 主函数
main() {
    # 获取当前版本
    CURRENT_VERSION=$(get_current_version)
    
    echo -e "${BLUE}MPD流媒体服务发布脚本${NC}"
    echo "当前版本: $CURRENT_VERSION"
    echo ""
    
    # 检查Git状态
    check_git_status
    
    # 验证新版本
    if [ -z "$NEW_VERSION" ]; then
        echo -e "${RED}错误: 请指定新版本号${NC}"
        show_help
        exit 1
    fi
    
    validate_version "$NEW_VERSION"
    
    # 检查版本是否已存在
    if git tag -l | grep -q "^$NEW_VERSION$"; then
        echo -e "${RED}错误: 版本 $NEW_VERSION 已存在${NC}"
        exit 1
    fi
    
    # 确认发布
    echo -e "${YELLOW}准备发布:${NC}"
    echo "  从版本: $CURRENT_VERSION"
    echo "  到版本: $NEW_VERSION"
    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${YELLOW}模式: 模拟运行${NC}"
    fi
    echo ""
    
    if [ "$DRY_RUN" = false ]; then
        read -p "确认发布? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "发布已取消"
            exit 0
        fi
    fi
    
    # 执行发布
    perform_release "$NEW_VERSION"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --notes)
            RELEASE_NOTES="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        v*.*)
            NEW_VERSION=$1
            shift
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 运行主函数
main
