from django.urls import path
from . import views

app_name = 'app_ai'

urlpatterns = [
    # POST请求 - Webhook处理
    path('git-webhook/', views.git_webhook, name='github_webhook'),

    # GET请求 - 统一数据接口（自动保存到数据库）
    path('github-data/', views.get_github_data, name='github_data'),
    
    # 数据库查询接口已移除 - 对应的 DatabaseClient 方法不存在
    
    # 异步接口
    path('github-data-async/', views.get_github_data_async, name='github_data_async'),  # POST - 异步获取GitHub数据
    path('task-status/<str:task_id>/', views.get_task_status, name='get_task_status'),  # GET - 获取任务状态
    path('recent-commits-async/', views.get_recent_commits_async_start, name='recent_commits_async'), # GET - 异步获取最近提交
    path('commit-details-async/', views.get_commit_details_async_start, name='commit_details_async'), # GET - 异步获取提交详情
    
    # Ollama分析接口
    path('ollama-analysis/', views.start_ollama_analysis_api, name='start_ollama_analysis'),  # POST - 启动Ollama分析
    path('analyze-commit/', views.analyze_single_commit_api, name='analyze_single_commit'),   # POST - 分析单个提交
    path('unanalyzed-commits/', views.get_unanalyzed_commits_api, name='get_unanalyzed_commits'), # GET - 获取未分析提交
    
    # 推送接口
    path('push-results/', views.start_push_task_api, name='start_push_task'),  # POST - 启动推送任务
    path('unpushed-commits/', views.get_unpushed_commits_api, name='get_unpushed_commits'), # GET - 获取未推送提交
    
    # 健康检查接口
    path('health/', views.health_check, name='health_check'),  # GET - 完整健康检查
    path('health/simple/', views.health_simple, name='health_simple'),  # GET - 简单健康检查
]
