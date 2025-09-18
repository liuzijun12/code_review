from django.urls import path
from . import views

app_name = 'app_ai'

urlpatterns = [
    # POST请求 - Webhook处理
    path('git-webhook/', views.git_webhook, name='github_webhook'),

    # GET请求 - 统一数据接口（自动保存到数据库）
    path('github-data/', views.get_github_data, name='github_data'),
    
    # 数据库查询接口
    path('saved-commits/', views.get_saved_commits, name='get_saved_commits'),           # GET - 获取保存的提交列表
    path('commit-detail/<str:commit_sha>/', views.get_commit_detail, name='get_commit_detail'), # GET - 获取单个提交详情
    path('database-stats/', views.get_database_stats, name='get_database_stats'),       # GET - 获取数据库统计
    path('search-commits/', views.search_commits, name='search_commits'),               # GET - 搜索提交记录
]
