@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: Code Review System Windows 启动脚本
:: 自动检测系统环境并选择合适的启动方式

echo 🚀 Code Review System 启动脚本
echo =================================
echo.
echo 📋 可用的启动模式:
echo    1. GPU 模式 (默认): docker-compose.yml
echo    2. CPU 模式: docker-compose.cpu.yml
echo    3. 自动检测: 让脚本自动选择
echo.

:: 检查命令行参数
if "%1"=="cpu" (
    set FORCE_CPU=true
    echo 🖥️  强制使用 CPU 模式
    goto :continue
)
if "%1"=="gpu" (
    set FORCE_GPU=true
    echo 🎯 强制使用 GPU 模式
    goto :continue
)
if "%1"=="help" goto :help
if "%1"=="-h" goto :help
if "%1"=="/?" goto :help

echo 🔍 自动检测模式
goto :continue

:help
echo 使用方法:
echo   start.bat        # 自动检测模式
echo   start.bat cpu    # 强制 CPU 模式
echo   start.bat gpu    # 强制 GPU 模式
echo   start.bat help   # 显示帮助
exit /b 0

:continue
echo.

:: 检测是否有 NVIDIA GPU
set HAS_GPU=false
nvidia-smi >nul 2>&1
if !errorlevel! equ 0 (
    set HAS_GPU=true
)

:: 检测 Docker 是否支持 GPU
set DOCKER_GPU=false
docker info 2>nul | findstr /i "nvidia" >nul
if !errorlevel! equ 0 (
    set DOCKER_GPU=true
)

echo 📋 系统信息:
echo    操作系统: Windows
echo    NVIDIA GPU: !HAS_GPU!
echo    Docker GPU 支持: !DOCKER_GPU!
echo.

:: 决定使用哪个配置文件
if "!FORCE_CPU!"=="true" (
    set COMPOSE_FILE=docker-compose.cpu.yml
    set GPU_MODE=CPU ^(强制^)
) else if "!FORCE_GPU!"=="true" (
    set COMPOSE_FILE=docker-compose.yml
    set GPU_MODE=GPU ^(强制^)
) else if "!HAS_GPU!"=="true" (
    if "!DOCKER_GPU!"=="true" (
        set COMPOSE_FILE=docker-compose.yml
        set GPU_MODE=GPU ^(自动检测^)
    ) else (
        set COMPOSE_FILE=docker-compose.cpu.yml
        set GPU_MODE=CPU ^(无 Docker GPU 支持^)
    )
) else (
    set COMPOSE_FILE=docker-compose.cpu.yml
    set GPU_MODE=CPU ^(无 GPU 硬件^)
)

echo.
echo 🔧 启动配置:
echo    使用配置文件: !COMPOSE_FILE!
echo    运行模式: !GPU_MODE!
echo.

:: 检查必要文件
if not exist ".env" (
    echo ⚠️  警告: .env 文件不存在
    if exist "example.env" (
        echo 📋 复制 example.env 为 .env...
        copy example.env .env >nul
        echo ✅ 已创建 .env 文件，请编辑其中的配置
    ) else (
        echo ❌ example.env 文件也不存在，请手动创建 .env 文件
        pause
        exit /b 1
    )
)

:: 检查 Docker 是否运行
docker version >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ Docker 未运行或未安装
    echo 请先启动 Docker Desktop
    pause
    exit /b 1
)

:: 启动服务
echo 🚀 启动 Docker Compose 服务...
echo =================================

:: 先拉取基础镜像（避免网络超时）
echo 📦 拉取基础镜像...
start /b docker pull python:3.11-slim
start /b docker pull mysql:8.0
start /b docker pull redis:7-alpine
start /b docker pull ollama/ollama:latest
start /b docker pull ghcr.io/open-webui/open-webui:main

:: 等待拉取完成
timeout /t 5 /nobreak >nul

echo 🔨 构建并启动服务...
echo 🏗️  Step 1: 构建镜像...
docker-compose -f !COMPOSE_FILE! build
echo 🚀 Step 2: 启动服务...
docker-compose -f !COMPOSE_FILE! up -d

:: 检查启动状态
echo.
echo ⏳ 等待服务启动...
timeout /t 10 /nobreak >nul

echo.
echo 📊 服务状态:
docker-compose -f !COMPOSE_FILE! ps

echo.
echo 🎉 启动完成!
echo.
echo 📱 访问地址:
echo    🌐 主应用: http://localhost:8000
echo    📊 监控面板: http://localhost:5555
echo    🤖 AI 管理: http://localhost:3000
echo.
echo 📝 查看日志: docker-compose -f !COMPOSE_FILE! logs -f [service_name]
echo 🛑 停止服务: docker-compose -f !COMPOSE_FILE! down
echo.

pause 