from django.urls import path
from . import views

app_name = 'app_ai'

urlpatterns = [
    # POST请求 - Webhook处理
    path('git-webhook/', views.git_webhook, name='github_webhook'),
    
    # GET请求 - 统一数据接口
    path('github-data/', views.get_github_data, name='github_data'),
]
