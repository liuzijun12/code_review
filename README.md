# �� Code Review System

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.2+-green.svg)](https://djangoproject.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)

**智能代码审查系统 - 让 AI 为你的代码把关**

</div>

---

## 🎯 项目简介

Code Review System 是一个智能代码审查平台，通过 GitHub Webhook 自动接收代码推送事件，使用 Ollama AI 进行代码分析，并将审查结果推送到企业微信群。

## ✨ 功能特性

- 🔗 **GitHub 集成** - 自动接收 Webhook 推送事件
- 🤖 **AI 代码审查** - 基于 Ollama 的智能代码分析
- 💬 **企业微信推送** - 自动推送审查结果到微信群
- ⚡ **异步处理** - Celery + Redis 异步任务队列
- 🐳 **容器化部署** - Docker Compose 一键部署
- 🎯 **GPU/CPU 双模式** - 自动检测并选择最佳运行模式

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/liuzijun12/code_review.git
cd code_review
```

### 2. 配置环境变量
```bash
# 复制配置文件
cp example.env .env

# 编辑配置（必须设置以下项目）
vim .env
```

**基础环境变量：**
```bash
# Django 基础配置
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# 数据库配置（Docker环境）
DB_HOST=mysql
DB_NAME=code_review
DB_USER=root
DB_PASSWORD=123456

# AI 服务配置
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_DEFAULT_CHAT_MODEL=llama3.1:8b

# 消息队列配置
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

**⚠️ 重要：GitHub和企业微信配置现在通过数据库管理**

启动服务后，访问 http://localhost:8000/admin/ 在 `Repository Config` 中配置：
- GitHub Token
- Webhook Secret  
- 仓库信息
- 企业微信 Webhook URL

### 3. 启动服务

**Linux/Mac 系统：**
```bash
./start.sh        # 自动检测模式
./start.sh cpu     # 强制 CPU 模式
./start.sh gpu     # 强制 GPU 模式
```

**Windows 系统：**
```cmd
start.bat         # 自动检测模式
start.bat cpu     # 强制 CPU 模式
start.bat gpu     # 强制 GPU 模式
```

**手动启动：**
```bash
# GPU 模式（Linux + NVIDIA GPU）
docker-compose build
docker-compose up -d

# CPU 模式（Mac/Windows/无GPU）
docker-compose -f docker-compose.cpu.yml build
docker-compose -f docker-compose.cpu.yml up -d

# 查看启动状态
docker-compose ps
```

### 4. 初始化 AI 模型
```bash
# 下载 AI 模型（首次使用）
docker exec -it code_review_ollama ollama pull llama3.1:8b

# 验证安装
docker exec -it code_review_ollama ollama list
```

### 5. 访问服务
- 🌐 **主应用**: http://localhost:8000
- 📊 **任务监控**: http://localhost:5555 (Flower)
- 🤖 **AI 管理**: http://localhost:3000 (Open WebUI)

## 🛠️ 本地开发测试

### 环境要求
- Python 3.11+
- MySQL 8.0+ / Redis 6.0+
- Ollama (可选，用于AI功能)

### 安装步骤
```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirement.txt

# 3. 配置环境变量
cp example.env .env
# 编辑 .env 文件，设置本地数据库连接
vim .env
```

### 启动服务

**需要4个终端窗口：**

**终端1 - Django主应用：**
```bash
# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 运行数据库迁移
python manage.py migrate
python manage.py createsuperuser  # 创建管理员账户

# 启动Django开发服务器
python manage.py runserver
```

**终端2 - Celery Worker：**
```bash
# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 启动Celery Worker
# Linux/Mac:
celery -A code_review worker --loglevel=info

# Windows:
celery -A code_review worker --loglevel=info --pool=solo
```

**终端3 - Redis：**
```bash
# 启动Redis服务器
redis-server

# 或使用Docker运行Redis
docker run -d -p 6379:6379 redis:7-alpine
```

**终端4 - Ollama (可选)：**
```bash
# 启动Ollama服务
ollama serve

# 下载AI模型
ollama pull llama3.1:8b
```

### 本地环境配置 (.env)
```bash
# 本地开发配置示例
DEBUG=True
SECRET_KEY=your-local-secret-key

# 本地数据库
DB_HOST=localhost
DB_NAME=code_review
DB_USER=root
DB_PASSWORD=your_password

# 本地服务
OLLAMA_BASE_URL=http://localhost:11434
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 数据库配置管理

启动服务后，访问 Django Admin 界面进行仓库配置：

1. **访问管理界面**: http://localhost:8000/admin/
2. **登录管理员账户** (之前创建的superuser)
3. **添加 Repository Config**:
   - **仓库所有者**: your_github_username
   - **仓库名称**: your_repository_name  
   - **GitHub Token**: your_github_personal_access_token
   - **Webhook Secret**: your_webhook_secret
   - **企业微信 Webhook URL**: your_wechat_webhook_url
   - **AI模型选择**: 选择合适的AI模型
   - **启用状态**: 勾选启用

## 🔧 GitHub Webhook 配置

1. 进入 GitHub 仓库设置 → Webhooks → Add webhook
2. 配置：
   - **Payload URL**: `http://your-domain.com:8000/ai/git-webhook/`
   - **Content type**: `application/json`
   - **Events**: 选择 "Push events"

## 📡 主要 API 接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/ai/git-webhook/` | POST | GitHub Webhook 接收 |
| `/ai/github-data/` | GET | 查询提交数据 |
| `/ai/health/` | GET | 系统健康检查 |

## 🔍 监控与管理

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f django

# 重启服务
docker-compose restart django

# 进入容器调试
docker exec -it code_review_django bash
```

## 🛠️ 常见问题

<details>
<summary><strong>Windows Docker 构建失败</strong></summary>

```cmd
# 使用修复后的启动脚本
start.bat

# 或手动分步构建
docker build -t code_review_django:latest .
docker-compose up -d
```
</details>

<details>
<summary><strong>GPU 配置错误</strong></summary>

```bash
# 使用 CPU 模式
./start.sh cpu

# 或手动启动 CPU 模式
docker-compose -f docker-compose.cpu.yml up -d
```
</details>

<details>
<summary><strong>.env 文件缺失</strong></summary>

```bash
# 创建配置文件
cp example.env .env

# 编辑必要配置
vim .env
```
</details>

<details>
<summary><strong>AI 分析失败</strong></summary>

```bash
# 检查 Ollama 状态
curl http://localhost:11434/api/tags

# 重新拉取模型
docker exec -it code_review_ollama ollama pull llama3.1:8b
```
</details>

## 📁 项目结构

```
code_review/
├── docker-compose.yml          # GPU 模式配置
├── docker-compose.cpu.yml      # CPU 模式配置
├── start.sh / start.bat         # 智能启动脚本
├── Dockerfile                   # 应用镜像
├── requirement.txt              # Python 依赖
├── example.env                  # 环境变量模板
├── code_review/                 # Django 项目配置
├── app_ai/                      # AI 功能核心模块
└── logs/                        # 应用日志
```

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

Made with ❤️ by [liuzijun12](https://github.com/liuzijun12)

</div>
