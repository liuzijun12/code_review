# Code Review System PowerShell 启动脚本
# 自动检测系统环境并选择合适的启动方式

param(
    [string]$Mode = "auto",
    [switch]$Help
)

# 设置控制台编码
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Show-Help {
    Write-Host "Code Review System PowerShell 启动脚本" -ForegroundColor Green
    Write-Host "=======================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "使用方法:" -ForegroundColor Yellow
    Write-Host "  .\start.ps1           # 自动检测模式" -ForegroundColor White
    Write-Host "  .\start.ps1 -Mode cpu # 强制 CPU 模式" -ForegroundColor White
    Write-Host "  .\start.ps1 -Mode gpu # 强制 GPU 模式" -ForegroundColor White
    Write-Host "  .\start.ps1 -Help     # 显示帮助" -ForegroundColor White
    Write-Host ""
    Write-Host "注意事项:" -ForegroundColor Yellow
    Write-Host "- 首次运行可能需要执行: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Gray
    Write-Host "- 确保 Docker Desktop 已启动" -ForegroundColor Gray
    exit 0
}

if ($Help) {
    Show-Help
}

Write-Host "🚀 Code Review System 启动脚本" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green
Write-Host ""
Write-Host "📋 可用的启动模式:" -ForegroundColor Yellow
Write-Host "   1. GPU 模式 (默认): docker-compose.yml" -ForegroundColor White
Write-Host "   2. CPU 模式: docker-compose.cpu.yml" -ForegroundColor White  
Write-Host "   3. 自动检测: 让脚本自动选择" -ForegroundColor White
Write-Host ""

# 检查参数
switch ($Mode.ToLower()) {
    "cpu" { 
        $ForceMode = "CPU"
        Write-Host "🖥️  强制使用 CPU 模式" -ForegroundColor Blue
    }
    "gpu" { 
        $ForceMode = "GPU"
        Write-Host "🎯 强制使用 GPU 模式" -ForegroundColor Blue
    }
    default { 
        $ForceMode = "AUTO"
        Write-Host "🔍 自动检测模式" -ForegroundColor Blue
    }
}
Write-Host ""

# 检测 NVIDIA GPU
$HasGPU = $false
try {
    $null = & nvidia-smi 2>$null
    if ($LASTEXITCODE -eq 0) {
        $HasGPU = $true
    }
} catch {
    $HasGPU = $false
}

# 检测 Docker GPU 支持
$DockerGPU = $false
try {
    $dockerInfo = & docker info 2>$null
    if ($dockerInfo -match "nvidia") {
        $DockerGPU = $true
    }
} catch {
    $DockerGPU = $false
}

Write-Host "📋 系统信息:" -ForegroundColor Yellow
Write-Host "   操作系统: Windows PowerShell" -ForegroundColor White
Write-Host "   NVIDIA GPU: $HasGPU" -ForegroundColor White
Write-Host "   Docker GPU 支持: $DockerGPU" -ForegroundColor White
Write-Host ""

# 决定使用哪个配置文件
switch ($ForceMode) {
    "CPU" {
        $ComposeFile = "docker-compose.cpu.yml"
        $GPUMode = "CPU (强制)"
    }
    "GPU" {
        $ComposeFile = "docker-compose.yml"
        $GPUMode = "GPU (强制)"
    }
    "AUTO" {
        if ($HasGPU -and $DockerGPU) {
            $ComposeFile = "docker-compose.yml"
            $GPUMode = "GPU (自动检测)"
        } else {
            $ComposeFile = "docker-compose.cpu.yml"
            if (-not $HasGPU) {
                $GPUMode = "CPU (无 GPU 硬件)"
            } else {
                $GPUMode = "CPU (无 Docker GPU 支持)"
            }
        }
    }
}

Write-Host "🔧 启动配置:" -ForegroundColor Yellow
Write-Host "   使用配置文件: $ComposeFile" -ForegroundColor White
Write-Host "   运行模式: $GPUMode" -ForegroundColor White
Write-Host ""

# 检查必要文件
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  警告: .env 文件不存在" -ForegroundColor Yellow
    if (Test-Path "example.env") {
        Write-Host "📋 复制 example.env 为 .env..." -ForegroundColor Blue
        Copy-Item "example.env" ".env"
        Write-Host "✅ 已创建 .env 文件，请编辑其中的配置" -ForegroundColor Green
    } else {
        Write-Host "❌ example.env 文件也不存在，请手动创建 .env 文件" -ForegroundColor Red
        Read-Host "按任意键退出"
        exit 1
    }
}

# 检查 Docker 是否运行
try {
    $null = & docker version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not running"
    }
} catch {
    Write-Host "❌ Docker 未运行或未安装" -ForegroundColor Red
    Write-Host "请先启动 Docker Desktop" -ForegroundColor Yellow
    Read-Host "按任意键退出"
    exit 1
}

# 启动服务
Write-Host "🚀 启动 Docker Compose 服务..." -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

# 先拉取基础镜像（并行）
Write-Host "📦 拉取基础镜像..." -ForegroundColor Blue
$jobs = @()
$images = @(
    "python:3.11-slim",
    "mysql:8.0", 
    "redis:7-alpine",
    "ollama/ollama:latest",
    "ghcr.io/open-webui/open-webui:main"
)

foreach ($image in $images) {
    $jobs += Start-Job -ScriptBlock {
        param($img)
        & docker pull $img 2>$null
    } -ArgumentList $image
}

# 等待所有拉取任务完成
$jobs | Wait-Job | Remove-Job

Write-Host "🔨 构建并启动服务..." -ForegroundColor Blue
& docker-compose -f $ComposeFile up --build -d

# 检查启动状态
Write-Host ""
Write-Host "⏳ 等待服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "📊 服务状态:" -ForegroundColor Yellow
& docker-compose -f $ComposeFile ps

Write-Host ""
Write-Host "🎉 启动完成!" -ForegroundColor Green
Write-Host ""
Write-Host "📱 访问地址:" -ForegroundColor Yellow
Write-Host "   🌐 主应用: http://localhost:8000" -ForegroundColor White
Write-Host "   📊 监控面板: http://localhost:5555" -ForegroundColor White
Write-Host "   🤖 AI 管理: http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "📝 查看日志: docker-compose -f $ComposeFile logs -f [service_name]" -ForegroundColor Gray
Write-Host "🛑 停止服务: docker-compose -f $ComposeFile down" -ForegroundColor Gray
Write-Host ""

Read-Host "按任意键退出" 