#!/bin/bash

# MPD流媒体服务启动脚本
# 支持不同的部署模式

set -e

# 默认配置
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="mpdstreaming"
MONITORING=false
BUILD=false
PULL=false
LOGS=false

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 帮助信息
show_help() {
    echo -e "${BLUE}MPD流媒体服务启动脚本${NC}"
    echo ""
    echo "用法: $0 [选项] [命令]"
    echo ""
    echo "命令:"
    echo "  start      启动服务 (默认)"
    echo "  stop       停止服务"
    echo "  restart    重启服务"
    echo "  logs       查看日志"
    echo "  status     查看服务状态"
    echo "  build      构建镜像"
    echo "  pull       拉取最新镜像"
    echo "  clean      清理容器和镜像"
    echo ""
    echo "选项:"
    echo "  -m, --monitoring    启用监控服务"
    echo "  -b, --build         构建镜像后启动"
    echo "  -p, --pull          拉取镜像后启动"
    echo "  -f, --follow        跟随日志输出"
    echo "  -h, --help          显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                  # 启动基础服务"
    echo "  $0 -m               # 启动服务并启用监控"
    echo "  $0 -b start         # 构建镜像并启动服务"
    echo "  $0 logs -f          # 查看并跟随日志"
}

# 检查依赖
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker未安装或不在PATH中${NC}"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker Compose未安装或不在PATH中${NC}"
        exit 1
    fi
}

# 获取Docker Compose命令
get_compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    else
        echo "docker compose"
    fi
}

# 构建服务
build_service() {
    echo -e "${BLUE}构建服务镜像...${NC}"
    local compose_cmd=$(get_compose_cmd)
    $compose_cmd -p $PROJECT_NAME build
    echo -e "${GREEN}构建完成${NC}"
}

# 拉取镜像
pull_images() {
    echo -e "${BLUE}拉取最新镜像...${NC}"
    local compose_cmd=$(get_compose_cmd)
    $compose_cmd -p $PROJECT_NAME pull
    echo -e "${GREEN}拉取完成${NC}"
}

# 启动服务
start_service() {
    echo -e "${BLUE}启动MPD流媒体服务...${NC}"
    
    local compose_cmd=$(get_compose_cmd)
    local profiles=""
    
    if [ "$MONITORING" = true ]; then
        profiles="--profile monitoring"
        echo -e "${YELLOW}启用监控服务${NC}"
    fi
    
    if [ "$BUILD" = true ]; then
        build_service
    fi
    
    if [ "$PULL" = true ]; then
        pull_images
    fi
    
    $compose_cmd -p $PROJECT_NAME $profiles up -d
    
    echo -e "${GREEN}服务启动成功${NC}"
    echo ""
    echo "Web界面: http://localhost:8080"
    echo "API文档: http://localhost:8080/api"
    
    if [ "$MONITORING" = true ]; then
        echo "监控服务: docker logs -f ${PROJECT_NAME}-monitor-1"
    fi
}

# 停止服务
stop_service() {
    echo -e "${YELLOW}停止服务...${NC}"
    local compose_cmd=$(get_compose_cmd)
    $compose_cmd -p $PROJECT_NAME down
    echo -e "${GREEN}服务已停止${NC}"
}

# 重启服务
restart_service() {
    stop_service
    sleep 2
    start_service
}

# 查看日志
show_logs() {
    local compose_cmd=$(get_compose_cmd)
    local follow_flag=""
    
    if [ "$LOGS" = true ]; then
        follow_flag="-f"
    fi
    
    $compose_cmd -p $PROJECT_NAME logs $follow_flag
}

# 查看服务状态
show_status() {
    local compose_cmd=$(get_compose_cmd)
    echo -e "${BLUE}服务状态:${NC}"
    $compose_cmd -p $PROJECT_NAME ps
    
    echo -e "\n${BLUE}容器健康状态:${NC}"
    docker ps --filter "label=com.docker.compose.project=$PROJECT_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # 检查服务是否响应
    if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
        echo -e "\n${GREEN}✅ API服务响应正常${NC}"
    else
        echo -e "\n${RED}❌ API服务无响应${NC}"
    fi
}

# 清理资源
clean_resources() {
    echo -e "${YELLOW}清理Docker资源...${NC}"
    local compose_cmd=$(get_compose_cmd)
    
    # 停止并删除容器
    $compose_cmd -p $PROJECT_NAME down --remove-orphans
    
    # 删除镜像（可选）
    read -p "是否删除项目镜像? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker images --filter "label=com.docker.compose.project=$PROJECT_NAME" -q | xargs -r docker rmi
        echo -e "${GREEN}镜像已删除${NC}"
    fi
    
    # 清理未使用的资源
    docker system prune -f
    echo -e "${GREEN}清理完成${NC}"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--monitoring)
            MONITORING=true
            shift
            ;;
        -b|--build)
            BUILD=true
            shift
            ;;
        -p|--pull)
            PULL=true
            shift
            ;;
        -f|--follow)
            LOGS=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        start|stop|restart|logs|status|build|pull|clean)
            COMMAND=$1
            shift
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 默认命令
if [ -z "$COMMAND" ]; then
    COMMAND="start"
fi

# 检查依赖
check_dependencies

# 执行命令
case $COMMAND in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    build)
        build_service
        ;;
    pull)
        pull_images
        ;;
    clean)
        clean_resources
        ;;
    *)
        echo -e "${RED}未知命令: $COMMAND${NC}"
        show_help
        exit 1
        ;;
esac
