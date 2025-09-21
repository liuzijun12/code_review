# Code Review System

一个基于Django的智能代码审查系统，集成GitHub Webhook、AI代码分析和企业微信推送功能。

## 🚀 主要功能

- 📝 **GitHub Webhook集成**: 自动接收GitHub推送事件
- 🤖 **AI代码分析**: 使用Ollama进行智能代码审查和提交分析
- 💬 **企业微信推送**: 自动推送分析结果到企业微信群
- ⚡ **异步任务处理**: 基于Celery的异步任务队列
- 📊 **数据存储**: MySQL数据库存储提交记录和分析结果

## 🛠️ 技术栈

- **后端**: Django 5.2.2 (修正版本)
- **数据库**: MySQL 8.0+
- **AI服务**: Ollama
- **异步任务**: Celery + Redis
- **消息推送**: 企业微信 Webhook
- **容器化**: Docker Compose

## 📋 系统要求

- Python 3.10+
- MySQL 8.0+
- Redis 6.0+
- Docker & Docker Compose (可选)

## ⚡ 快速启动

### 1. 克隆项目
```bash
git clone https://github.com/liuzijun12/code_review.git
cd code_review
```

### 2. 安装依赖
```bash
# 推荐使用虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

pip install -r requirement.txt
```

### 3. 环境配置
```bash
cp example.env .env
```

编辑 `.env` 文件：
```env
# Django配置
DEBUG=True
SECRET_KEY=your-secret-key-here

# 数据库配置
DB_NAME=code_review
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306

# Redis配置 (Celery需要)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Ollama配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_CHAT_MODEL=llama3.1:8b

# 企业微信配置
WX_WEBHOOK_URL=your-wechat-webhook-url
```

### 4. 数据库设置
```bash
# 创建数据库
mysql -u root -p
CREATE DATABASE code_review CHARACTER SET utf8mb4;
exit

# 运行迁移
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 5. 启动服务

#### 🔥 重要：按顺序启动以下服务

**1) 启动Redis (Celery消息代理)**
```bash
# 使用Docker启动Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 或使用系统安装的Redis
redis-server
```

**2) 启动Ollama AI服务**
```bash
# 使用Docker启动Ollama
docker run -d --name ollama -p 11434:11434 ollama/ollama

# 下载AI模型
docker exec -it ollama ollama pull llama3.1:8b
```

**3) 启动Celery Worker (异步任务处理器)**
```bash
# Windows用户
celery -A code_review worker --loglevel=info --pool=solo

# Linux/Mac用户
celery -A code_review worker --loglevel=info
```

**4) 启动Celery Beat (定时任务调度器)**
```bash
celery -A code_review beat --loglevel=info
```

**5) 启动Flower (可选，任务监控界面)**
```bash
celery -A code_review flower --port=5555
```

**6) 启动Django开发服务器**
```bash
python manage.py runserver
```

### 6. 验证服务状态
```bash
# 检查系统状态
python manage.py system_status --verbose

# 访问服务
# Django应用: http://localhost:8000
# Flower监控: http://localhost:5555
# Ollama API: http://localhost:11434
```

## 🔧 API接口

### GitHub Webhook
```bash
POST /ai/git-webhook/
# GitHub推送事件自动触发代码分析
```

### 数据查询
```bash
GET /ai/github-data/?type=recent_commits&branch=main&limit=10
GET /ai/github-data/?type=commit_details&sha=abc123&include_diff=true
```

### 异步任务
```bash
POST /ai/github-data-async/
GET /ai/task-status/{task_id}/
```

## 🐳 Docker一键启动

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

## 🔍 故障排除

### Celery任务不执行
```bash
# 检查Redis连接
redis-cli ping

# 重启Celery Worker
pkill -f "celery worker"
celery -A code_review worker --loglevel=info --pool=solo
```

### Windows兼容性问题
```bash
# 使用PyMySQL替代mysqlclient
pip uninstall mysqlclient
pip install PyMySQL==1.1.1

# 在settings.py中添加
import pymysql
pymysql.install_as_MySQLdb()
```

### AI分析不工作
```bash
# 检查Ollama服务
curl http://localhost:11434/api/tags

# 重新拉取模型
docker exec -it ollama ollama pull llama3.1:8b
```

## 📁 项目结构

```
code_review/
├── code_review/              # Django项目配置
│   ├── settings.py           # 项目设置
│   ├── celery.py            # Celery配置
│   └── urls.py              # 主URL配置
├── app_ai/                  # AI功能应用
│   ├── models.py            # 数据模型
│   ├── views.py             # API视图
│   ├── git_client.py        # GitHub API客户端
│   ├── ollama_client.py     # Ollama AI客户端
│   ├── info_push.py         # 企业微信推送
│   ├── tasks/               # Celery异步任务
│   │   ├── async_get.py     # 异步数据获取
│   │   ├── async_ollama.py  # 异步AI分析
│   │   └── async_push.py    # 异步消息推送
│   └── management/commands/
│       └── system_status.py # 系统状态检查
├── docker-compose.yml       # Docker服务配置
├── requirement.txt          # Python依赖
└── example.env             # 环境变量示例
```

## 🚀 工作流程

1. **GitHub推送** → Webhook触发 → 异步获取提交数据
2. **数据获取** → 保存到MySQL → 触发AI分析任务
3. **AI分析** → Ollama代码审查 → 保存分析结果
4. **消息推送** → 企业微信通知 → 标记推送状态

## 📞 支持

- 创建 [Issue](https://github.com/liuzijun12/code_review/issues)
- 查看日志: `docker-compose logs -f`
- 系统检查: `python manage.py system_status --verbose`
