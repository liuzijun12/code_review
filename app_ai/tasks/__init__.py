"""
Celery任务模块
包含所有异步任务的定义
"""

# 导入所有任务模块，确保Celery可以发现它们
from . import ai_analysis
from . import github_data  
from . import database
from . import wx_push

__all__ = [
    'ai_analysis',
    'github_data', 
    'database',
    'wx_push',
]
