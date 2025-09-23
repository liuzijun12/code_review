"""
Celery异步任务模块
包含所有异步任务的定义
"""

# 导入所有任务模块，确保Celery可以发现它们
from . import async_get
# from . import async_ollama  # 已删除，Ollama分析现在在async_get中直接处理
from . import async_push

__all__ = [
    'async_get',
    # 'async_ollama',  # 已删除
    'async_push',
]
