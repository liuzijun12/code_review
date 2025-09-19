from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import GitCommitAnalysis

@admin.register(GitCommitAnalysis)
class GitCommitAnalysisAdmin(admin.ModelAdmin):
    """
    Git提交分析记录的Admin配置
    """
    # 列表页显示的字段
    list_display = [
        'commit_sha_short',
        'author_name', 
        'commit_timestamp',
        'has_analysis',
        'created_at',
        'updated_at'
    ]
    
    # 列表页过滤器
    list_filter = [
        'author_name',
        'commit_timestamp',
        'created_at',
        ('analysis_suggestion', admin.EmptyFieldListFilter),  # 按是否有AI分析过滤
    ]
    
    # 搜索字段
    search_fields = [
        'commit_sha',
        'author_name',
        'commit_message',
        'analysis_suggestion'
    ]
    
    # 详情页字段分组
    fieldsets = (
        ('基本信息', {
            'fields': ('commit_sha', 'author_name', 'commit_timestamp')
        }),
        ('提交内容', {
            'fields': ('commit_message', 'code_diff'),
            'classes': ('collapse',)  # 默认折叠
        }),
        ('AI分析', {
            'fields': ('analysis_suggestion',),
            'classes': ('collapse',)
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # 只读字段
    readonly_fields = ['created_at', 'updated_at']
    
    # 每页显示数量
    list_per_page = 25
    
    # 排序
    ordering = ['-commit_timestamp']
    
    # 详情页链接字段
    list_display_links = ['commit_sha_short', 'author_name']
    
    def commit_sha_short(self, obj):
        """显示短SHA"""
        return obj.commit_sha[:8] if obj.commit_sha else '-'
    commit_sha_short.short_description = 'SHA'
    commit_sha_short.admin_order_field = 'commit_sha'
    
    def has_analysis(self, obj):
        """显示是否有AI分析"""
        if obj.analysis_suggestion:
            return format_html(
                '<span style="color: green;">✓ 已分析</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ 未分析</span>'
            )
    has_analysis.short_description = 'AI分析状态'
    has_analysis.admin_order_field = 'analysis_suggestion'
    
    # 批量操作
    actions = ['mark_for_reanalysis', 'clear_analysis']
    
    def mark_for_reanalysis(self, request, queryset):
        """标记为需要重新分析"""
        count = queryset.update(analysis_suggestion=None)
        self.message_user(request, f'已标记 {count} 条记录需要重新分析')
    mark_for_reanalysis.short_description = '清除AI分析结果（标记重新分析）'
    
    def clear_analysis(self, request, queryset):
        """清除分析结果"""
        count = queryset.update(analysis_suggestion='')
        self.message_user(request, f'已清除 {count} 条记录的分析结果')
    clear_analysis.short_description = '清除AI分析结果'


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
