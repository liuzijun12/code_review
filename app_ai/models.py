from django.db import models
from django.utils import timezone


class GitRepository(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    local_path = models.CharField(max_length=512)
    last_checked = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CommitAnalysis(models.Model):
    repository = models.ForeignKey(GitRepository, on_delete=models.CASCADE, related_name='analyses')
    commit_hash = models.CharField(max_length=40)
    author = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField()
    commit_date = models.DateTimeField()
    analysis = models.TextField()
    suggestions = models.TextField()
    model_used = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('repository', 'commit_hash')


