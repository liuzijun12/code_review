"""
Django项目初始化文件
确保Celery在Django启动时被正确加载
"""

# 导入Celery应用，确保在Django启动时加载
from .celery import app as celery_app

__all__ = ('celery_app',)
