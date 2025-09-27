from django.urls import path
from . import views

app_name = 'app_ai'

urlpatterns = [
    # Webhook处理
    path('git-webhook/', views.git_webhook, name='github_webhook'),

    # 数据接口
    path('github-data/', views.get_github_data, name='github_data'),
    path('github-data-async/', views.get_github_data_async, name='github_data_async'),
    path('task-status/<str:task_id>/', views.get_task_status, name='get_task_status'),
    path('commit-details-async/', views.get_commit_details_async_start, name='commit_details_async'),
    
    # 推送接口
    path('push-results/', views.start_push_task_api, name='start_push_task'),
    
    # 健康检查接口
    path('health/', views.health_check, name='health_check'),
    path('health/simple/', views.health_simple, name='health_simple'),
]
