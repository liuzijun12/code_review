from django.db import models
from django.utils import timezone

class RepositoryConfig(models.Model):
    """
    仓库配置模型，用于管理GitHub仓库的配置信息
    """
    
    repo_owner = models.CharField(
        max_length=255,
        verbose_name="仓库作者/所有者",
        help_text="GitHub仓库的所有者用户名"
    )
    
    repo_name = models.CharField(
        max_length=255,
        verbose_name="仓库名称",
        help_text="GitHub仓库名称"
    )
    
    webhook_secret = models.CharField(
        max_length=255,
        verbose_name="Webhook密钥",
        help_text="GitHub Webhook的密钥，用于验证请求来源"
    )
    
    github_token = models.CharField(
        max_length=255,
        verbose_name="GitHub个人访问令牌",
        help_text="用于访问GitHub API的个人访问令牌"
    )
    
    is_enabled = models.BooleanField(
        default=True,
        verbose_name="是否启用",
        help_text="是否启用此仓库的代码审查功能"
    )
    
    wechat_webhook_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="企业微信Webhook URL",
        help_text="用于推送代码审查结果的企业微信群机器人Webhook地址"
    )
    
    ollama_prompt_template = models.TextField(
        blank=True,
        null=True,
        verbose_name="Ollama模型提示词模板",
        help_text="用于代码审查的自定义提示词模板，支持变量替换。如果为空则使用系统默认提示词"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )
    
    class Meta:
        db_table = 'repository_config'
        verbose_name = "仓库配置"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        # 确保同一个仓库只有一个配置记录
        unique_together = [['repo_owner', 'repo_name']]
    
    def __str__(self):
        status = "启用" if self.is_enabled else "禁用"
        return f"{self.repo_owner}/{self.repo_name} ({status})"
    
    @property
    def full_name(self):
        """返回完整的仓库名称"""
        return f"{self.repo_owner}/{self.repo_name}"
    
    def get_webhook_url(self):
        """获取微信webhook URL，如果为空则返回None"""
        return self.wechat_webhook_url if self.wechat_webhook_url else None