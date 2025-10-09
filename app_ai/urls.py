from django.urls import path
from . import views

app_name = 'app_ai'

urlpatterns = [
    # GitHub Webhook 处理（核心接口）
    path('git-webhook/', views.git_webhook, name='github_webhook'),
    
    # 任务状态查询
    path('task-status/<str:task_id>/', views.get_task_status, name='get_task_status'),
    
    # 健康检查接口
    path('health/', views.health_check, name='health_check'),
    path('health/simple/', views.health_simple, name='health_simple'),
]
