from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import RepositoryConfig

@admin.register(RepositoryConfig)
class RepositoryConfigAdmin(admin.ModelAdmin):
    """仓库配置管理"""
    
    list_display = [
        'full_name', 
        'is_enabled_display', 
        'has_webhook_url', 
        'created_at', 
        'updated_at'
    ]
    
    list_filter = [
        'is_enabled', 
        'created_at', 
        'repo_owner'
    ]
    
    search_fields = [
        'repo_owner', 
        'repo_name'
    ]
    
    readonly_fields = [
        'created_at', 
        'updated_at'
    ]
    
    fieldsets = (
        ('基本信息', {
            'fields': ('repo_owner', 'repo_name', 'is_enabled')
        }),
        ('认证配置', {
            'fields': ('webhook_secret', 'github_token'),
            'classes': ('collapse',)
        }),
        ('通知配置', {
            'fields': ('wechat_webhook_url',),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_enabled_display(self, obj):
        """显示启用状态"""
        if obj.is_enabled:
            return format_html(
                '<span style="color: green;">✅ 启用</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">❌ 禁用</span>'
            )
    is_enabled_display.short_description = '状态'
    
    def has_webhook_url(self, obj):
        """显示是否配置了微信webhook"""
        if obj.wechat_webhook_url:
            return format_html(
                '<span style="color: green;">✅</span>'
            )
        else:
            return format_html(
                '<span style="color: orange;">❌</span>'
            )
    has_webhook_url.short_description = '微信通知'
    
    def get_queryset(self, request):
        """优化查询"""
        return super().get_queryset(request).order_by('-created_at')


# 自定义Admin站点配置
admin.site.site_header = "代码审查系统管理"
admin.site.site_title = "代码审查管理"
admin.site.index_title = "欢迎使用代码审查系统管理界面"

# 添加自定义的管理链接
class AdminConfig:
    """
    管理界面配置类
    """
    @staticmethod
    def get_celery_status():
        """获取Celery状态"""
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            if stats:
                return "运行中"
            else:
                return "未运行"
        except Exception:
            return "未知"
