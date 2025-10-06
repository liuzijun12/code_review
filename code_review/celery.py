"""
Celery配置文件
用于配置异步任务队列系统
"""
import os
from celery import Celery
from django.conf import settings

# 设置Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code_review.settings')

# 创建Celery应用
app = Celery('code_review')

# 从Django settings加载配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现任务
app.autodiscover_tasks()

# 手动导入子目录中的任务
app.autodiscover_tasks(['app_ai.get_all_tasks'])

# 调试信息
@app.task(bind=True)
def debug_task(self):
    """调试任务"""
    print(f'Request: {self.request!r}')
