from django.db import models
from django.utils import timezone

class GitCommitAnalysis(models.Model):
    """
    用于存储GitHub Commit分析数据的模型，对应数据库中的 git_data 表。
    """
    
    commit_sha = models.CharField(
        max_length=40, 
        unique=True, 
        db_index=True,
        verbose_name="提交标识码 (SHA)"
    )

    author_name = models.CharField(
        max_length=255,
        verbose_name="提交人"
    )


    commit_timestamp = models.DateTimeField(
        verbose_name="提交时间"
    )


    code_diff = models.TextField(
        verbose_name="提交的代码变更 (Diff)"
    )


    commit_message = models.TextField(
        verbose_name="提交注释"
    )


    analysis_suggestion = models.TextField(
        blank=True, 
        null=True,
        verbose_name="AI修改意见"
    )


    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="记录创建时间"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="记录更新时间"
    )

    class Meta:
        # 定义数据库中的表名
        db_table = 'git_data'
        verbose_name = "Git提交分析记录"
        verbose_name_plural = verbose_name
        ordering = ['-commit_timestamp']

    def __str__(self):
        return f"{self.author_name} - {str(self.commit_sha)[:7]}"