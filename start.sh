#!/bin/bash

# Code Review System 智能启动脚本
# 自动检测系统环境并选择合适的启动方式

echo "🚀 Code Review System 启动脚本"
echo "================================="
echo ""
echo "📋 可用的启动模式:"
echo "   1. GPU 模式 (默认): docker-compose.yml"
echo "   2. CPU 模式: docker-compose.cpu.yml"
echo "   3. 自动检测: 让脚本自动选择"
echo ""

# 检查命令行参数
if [[ "$1" == "cpu" ]]; then
    FORCE_CPU=true
    echo "🖥️  强制使用 CPU 模式"
elif [[ "$1" == "gpu" ]]; then
    FORCE_GPU=true
    echo "🎯 强制使用 GPU 模式"
elif [[ "$1" == "help" ]] || [[ "$1" == "-h" ]]; then
    echo "使用方法:"
    echo "  ./start.sh        # 自动检测模式"
    echo "  ./start.sh cpu    # 强制 CPU 模式"
    echo "  ./start.sh gpu    # 强制 GPU 模式"
    echo "  ./start.sh help   # 显示帮助"
    exit 0
else
    echo "🔍 自动检测模式"
fi
echo ""

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "mac"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# 检测是否有 NVIDIA GPU
detect_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null; then
            echo "true"
        else
            echo "false"
        fi
    else
        echo "false"
    fi
}

# 检测 Docker 是否支持 GPU
detect_docker_gpu() {
    if docker info 2>/dev/null | grep -q "nvidia"; then
        echo "true"
    else
        echo "false"
    fi
}

OS=$(detect_os)
HAS_GPU=$(detect_gpu)
DOCKER_GPU=$(detect_docker_gpu)

echo "📋 系统信息:"
echo "   操作系统: $OS"
echo "   NVIDIA GPU: $HAS_GPU"
echo "   Docker GPU 支持: $DOCKER_GPU"
echo ""

# 决定使用哪个配置文件
if [[ "$FORCE_CPU" == "true" ]]; then
    COMPOSE_FILE="docker-compose.cpu.yml"
    GPU_MODE="CPU (强制)"
elif [[ "$FORCE_GPU" == "true" ]]; then
    COMPOSE_FILE="docker-compose.yml"
    GPU_MODE="GPU (强制)"
elif [[ "$OS" == "linux" ]] && [[ "$HAS_GPU" == "true" ]] && [[ "$DOCKER_GPU" == "true" ]]; then
    COMPOSE_FILE="docker-compose.yml"
    GPU_MODE="GPU (自动检测)"
else
    COMPOSE_FILE="docker-compose.cpu.yml"
    GPU_MODE="CPU (自动检测: $OS 系统或无 GPU 支持)"
fi

echo ""
echo "🔧 启动配置:"
echo "   使用配置文件: $COMPOSE_FILE"
echo "   运行模式: $GPU_MODE"
echo ""

# 检查必要文件
if [[ ! -f ".env" ]]; then
    echo "⚠️  警告: .env 文件不存在"
    if [[ -f "example.env" ]]; then
        echo "📋 复制 example.env 为 .env..."
        cp example.env .env
        echo "✅ 已创建 .env 文件，请编辑其中的配置"
    else
        echo "❌ example.env 文件也不存在，请手动创建 .env 文件"
        exit 1
    fi
fi

# 检查 Docker 是否运行
if ! docker version &> /dev/null; then
    echo "❌ Docker 未运行或未安装"
    echo "请先启动 Docker"
    exit 1
fi

# 启动服务
echo "🚀 启动 Docker Compose 服务..."
echo "================================="

# 先拉取基础镜像（避免网络超时）
echo "📦 拉取基础镜像..."
docker pull python:3.11-slim &
docker pull mysql:8.0 &
docker pull redis:7-alpine &
docker pull ollama/ollama:latest &
docker pull ghcr.io/open-webui/open-webui:main &
wait

echo "🔨 构建并启动服务..."
echo "🏗️  Step 1: 构建镜像..."
docker-compose -f $COMPOSE_FILE build
echo "🚀 Step 2: 启动服务..."
docker-compose -f $COMPOSE_FILE up -d

# 检查启动状态
echo ""
echo "⏳ 等待服务启动..."
sleep 10

echo ""
echo "📊 服务状态:"
docker-compose -f $COMPOSE_FILE ps

echo ""
echo "🎉 启动完成!"
echo ""
echo "📱 访问地址:"
echo "   🌐 主应用: http://localhost:8000"
echo "   📊 监控面板: http://localhost:5555"
echo "   🤖 AI 管理: http://localhost:3000"
echo ""
echo "📝 查看日志: docker-compose -f $COMPOSE_FILE logs -f [service_name]"
echo "🛑 停止服务: docker-compose -f $COMPOSE_FILE down"
