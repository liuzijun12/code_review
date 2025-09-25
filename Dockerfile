# 使用官方 Python 3.11 镜像作为基础镜像
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 设置工作目录
WORKDIR /app

# 更换为国内镜像源并安装系统依赖（优化版本）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
        curl \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# 复制依赖文件
COPY requirement.txt /app/

# 使用国内 PyPI 镜像安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip install --no-cache-dir -r requirement.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制项目代码
COPY . /app/

# 创建必要的目录
RUN mkdir -p /app/logs /app/staticfiles

# 设置权限
RUN chmod +x /app/manage.py && \
    if [ -f /app/scripts/init-env.sh ]; then chmod +x /app/scripts/init-env.sh; fi

# 收集静态文件（在构建时进行）
RUN python manage.py collectstatic --noinput --settings=code_review.settings || true

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ai/health/ || exit 1

# 默认命令
CMD ["gunicorn", "code_review.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"] 