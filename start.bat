@echo off
REM MPD流媒体服务启动脚本 (Windows版本)
REM 支持不同的部署模式

setlocal enabledelayedexpansion

REM 默认配置
set PROJECT_NAME=mpdstreaming
set MONITORING=false
set BUILD=false
set PULL=false
set LOGS=false
set COMMAND=start
set PRODUCTION=false

REM 解析命令行参数
:parse_args
if "%~1"=="" goto :after_parse
if "%~1"=="-m" (
    set MONITORING=true
    goto :next_arg
)
if "%~1"=="--monitoring" (
    set MONITORING=true
    goto :next_arg
)
if "%~1"=="-b" (
    set BUILD=true
    goto :next_arg
)
if "%~1"=="--build" (
    set BUILD=true
    goto :next_arg
)
if "%~1"=="-p" (
    set PULL=true
    goto :next_arg
)
if "%~1"=="--pull" (
    set PULL=true
    goto :next_arg
)
if "%~1"=="-f" (
    set LOGS=true
    goto :next_arg
)
if "%~1"=="--follow" (
    set LOGS=true
    goto :next_arg
)
if "%~1"=="--production" (
    set PRODUCTION=true
    goto :next_arg
)
if "%~1"=="-h" goto :show_help
if "%~1"=="--help" goto :show_help
if "%~1"=="start" (
    set COMMAND=start
    goto :next_arg
)
if "%~1"=="stop" (
    set COMMAND=stop
    goto :next_arg
)
if "%~1"=="restart" (
    set COMMAND=restart
    goto :next_arg
)
if "%~1"=="logs" (
    set COMMAND=logs
    goto :next_arg
)
if "%~1"=="status" (
    set COMMAND=status
    goto :next_arg
)
if "%~1"=="build" (
    set COMMAND=build
    goto :next_arg
)
if "%~1"=="pull" (
    set COMMAND=pull
    goto :next_arg
)
if "%~1"=="clean" (
    set COMMAND=clean
    goto :next_arg
)
echo 未知选项: %~1
goto :show_help

:next_arg
shift
goto :parse_args

:after_parse

REM 检查Docker是否安装
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: Docker未安装或不在PATH中
    exit /b 1
)

REM 检查Docker Compose
where docker-compose >nul 2>nul
if %errorlevel% equ 0 (
    set COMPOSE_CMD=docker-compose
) else (
    set COMPOSE_CMD=docker compose
)

REM 执行命令
if "%COMMAND%"=="start" goto :start_service
if "%COMMAND%"=="stop" goto :stop_service
if "%COMMAND%"=="restart" goto :restart_service
if "%COMMAND%"=="logs" goto :show_logs
if "%COMMAND%"=="status" goto :show_status
if "%COMMAND%"=="build" goto :build_service
if "%COMMAND%"=="pull" goto :pull_images
if "%COMMAND%"=="clean" goto :clean_resources

echo 未知命令: %COMMAND%
goto :show_help

:show_help
echo MPD流媒体服务启动脚本
echo.
echo 用法: %~nx0 [选项] [命令]
echo.
echo 命令:
echo   start      启动服务 (默认)
echo   stop       停止服务
echo   restart    重启服务
echo   logs       查看日志
echo   status     查看服务状态
echo   build      构建镜像
echo   pull       拉取最新镜像
echo   clean      清理容器和镜像
echo.
echo 选项:
echo   -m, --monitoring    启用监控服务
echo   -b, --build         构建镜像后启动
echo   -p, --pull          拉取镜像后启动
echo   -f, --follow        跟随日志输出
echo   -h, --help          显示此帮助信息
echo.
echo 示例:
echo   %~nx0                  # 启动基础服务
echo   %~nx0 -m               # 启动服务并启用监控
echo   %~nx0 -b start         # 构建镜像并启动服务
echo   %~nx0 logs -f          # 查看并跟随日志
exit /b 0

:build_service
echo 构建服务镜像...
%COMPOSE_CMD% -p %PROJECT_NAME% build
echo 构建完成
goto :eof

:pull_images
echo 拉取最新镜像...
%COMPOSE_CMD% -p %PROJECT_NAME% pull
echo 拉取完成
goto :eof

:start_service
echo 启动MPD流媒体服务...

set PROFILES=
if "%MONITORING%"=="true" (
    set PROFILES=--profile monitoring
    echo 启用监控服务
)

if "%BUILD%"=="true" (
    call :build_service
)

if "%PULL%"=="true" (
    call :pull_images
)

%COMPOSE_CMD% -p %PROJECT_NAME% %PROFILES% up -d

echo 服务启动成功
echo.
echo Web界面: http://localhost:8080
echo API文档: http://localhost:8080/api

if "%MONITORING%"=="true" (
    echo 监控服务: docker logs -f %PROJECT_NAME%-monitor-1
)
goto :eof

:stop_service
echo 停止服务...
%COMPOSE_CMD% -p %PROJECT_NAME% down
echo 服务已停止
goto :eof

:restart_service
call :stop_service
timeout /t 2 /nobreak >nul
call :start_service
goto :eof

:show_logs
set FOLLOW_FLAG=
if "%LOGS%"=="true" (
    set FOLLOW_FLAG=-f
)
%COMPOSE_CMD% -p %PROJECT_NAME% logs %FOLLOW_FLAG%
goto :eof

:show_status
echo 服务状态:
%COMPOSE_CMD% -p %PROJECT_NAME% ps
echo.
echo 容器健康状态:
docker ps --filter "label=com.docker.compose.project=%PROJECT_NAME%" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

REM 检查服务是否响应
curl -s http://localhost:8080/api/status >nul 2>nul
if %errorlevel% equ 0 (
    echo.
    echo ✅ API服务响应正常
) else (
    echo.
    echo ❌ API服务无响应
)
goto :eof

:clean_resources
echo 清理Docker资源...

REM 停止并删除容器
%COMPOSE_CMD% -p %PROJECT_NAME% down --remove-orphans

REM 删除镜像（需要用户确认）
set /p "DELETE_IMAGES=是否删除项目镜像? [y/N]: "
if /i "%DELETE_IMAGES%"=="y" (
    for /f %%i in ('docker images --filter "label=com.docker.compose.project=%PROJECT_NAME%" -q') do docker rmi %%i
    echo 镜像已删除
)

REM 清理未使用的资源
docker system prune -f
echo 清理完成
goto :eof
