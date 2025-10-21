"""code_review URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

def redirect_to_admin(request):
    return redirect('/admin/')

urlpatterns = [
    path('', redirect_to_admin),  # 根路径重定向到admin
    path('admin/', admin.site.urls),  # admin路径
    path('ai/', include('app_ai.urls')),
]

# 静态文件服务配置
if settings.DEBUG:
    # 开发环境：Django 直接提供静态文件服务
    # 使用 Django 的内置静态文件处理，会自动从 STATICFILES_DIRS 和 app 中查找
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
else:
    # 生产环境：静态文件由 Nginx/Apache 等 Web 服务器提供
    # 使用收集后的静态文件
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
