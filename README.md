# Code Review System

一个基于Django的代码审查系统，集成了AI辅助功能来提升代码审查效率。

## 🚀 功能特性

- 📝 代码审查管理
- 🤖 AI辅助代码分析
- 💬 协作讨论功能
- 📊 审查统计和报告

## 🛠️ 技术栈

- **后端**: Django 5.2.6
- **数据库**: MySQL
- **AI服务**: Ollama + Open WebUI
- **容器化**: Docker Compose

## 📋 系统要求

- Python 3.8+
- MySQL 5.7+
- Docker & Docker Compose (可选)

## ⚡ 快速开始

### 1. 克隆项目
```bash
git clone <repository-url>
cd code_review
```

### 2. 安装依赖
```bash
pip install -r requirement.txt
```

### 3. 环境配置
复制环境配置文件：
```bash
cp example.env .env
```

编辑 `.env` 文件，配置您的数据库和其他设置：
```env
# 数据库配置
DB_NAME=code_review
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306

# Django配置
SECRET_KEY=your-secret-key
DEBUG=True
```

### 4. 数据库设置
创建MySQL数据库：
```sql
CREATE DATABASE code_review;
```

运行数据库迁移：
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. 创建超级用户
```bash
python manage.py createsuperuser
```

### 6. 启动开发服务器
```bash
python manage.py runserver
```

访问 http://localhost:8000 查看应用。

## 🐳 使用Docker

### 启动AI服务
项目包含了Ollama和Open WebUI的Docker配置：

```bash
# 启动AI服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

服务地址：
- Ollama API: http://localhost:11434
- Open WebUI: http://localhost:3000

### 下载AI模型
```bash
# 进入ollama容器
docker exec -it ollama bash

# 下载模型（例如llama2）
ollama pull llama2
```

## 📁 项目结构

```
code_review/
├── code_review/          # Django项目配置
│   ├── settings.py       # 项目设置
│   ├── urls.py          # 主URL配置
│   └── ...
├── app_ai/              # AI功能应用
│   ├── models.py        # 数据模型
│   ├── views.py         # 视图函数
│   ├── urls.py          # URL配置
│   └── ...
├── docker-compose.yml    # Docker服务配置
├── manage.py            # Django管理脚本
├── requirement.txt      # Python依赖
├── example.env          # 环境变量示例
└── README.md           # 项目说明
```

## 🔧 配置说明

### 数据库配置
项目支持MySQL数据库，配置在 `settings.py` 中：

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'code_review',
        'USER': 'root',
        'PASSWORD': '123456',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### AI服务配置
- **Ollama**: 本地AI模型服务
- **Open WebUI**: Web界面，便于与AI模型交互

## 📝 开发指南

### 添加新功能
1. 在相应的Django应用中添加模型、视图和URL
2. 运行数据库迁移（如有模型更改）
3. 编写测试
4. 更新文档

### 代码风格
- 遵循PEP 8规范
- 使用有意义的变量和函数名
- 添加适当的注释和文档字符串

## 🧪 测试

运行测试：
```bash
python manage.py test
```

## 🚀 部署

### 生产环境注意事项
1. 设置 `DEBUG=False`
2. 配置安全的 `SECRET_KEY`
3. 设置正确的 `ALLOWED_HOSTS`
4. 配置静态文件服务
5. 使用生产级数据库配置
6. 配置HTTPS

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

如果您有任何问题或建议，请：
- 创建 [Issue](issues)
- 发送邮件至: [your-email@example.com]

## 🔗 相关链接

- [Django 文档](https://docs.djangoproject.com/)
- [Ollama 文档](https://ollama.ai/)
- [Open WebUI](https://github.com/open-webui/open-webui)

---

⭐ 如果这个项目对您有帮助，请给它一个星标！
