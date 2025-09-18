#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub数据获取配置
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

# 创建logger实例
logger = logging.getLogger(__name__)

@dataclass
class GitHubApiConfig:
    """GitHub API配置"""
    
    # 基础配置
    token: str = ""
    repo_owner: str = ""
    repo_name: str = ""
    base_url: str = "https://api.github.com"
    
    # 请求限制配置
    max_commits_per_request: int = 10  # 单次请求最大提交数
    max_files_per_commit: int = 50     # 单个提交最大文件数
    max_pull_requests: int = 20        # 最大PR数量
    max_search_results: int = 30       # 搜索结果最大数量
    
    # 时间间隔配置 (秒)
    min_request_interval: float = 1.0   # 最小请求间隔
    get_request_interval: float = 2.0   # GET请求间隔
    webhook_trigger_delay: float = 1.0  # webhook触发延迟
    rate_limit_interval: float = 3600.0 # 速率限制重置间隔
    timeout_seconds: int = 30           # 请求超时时间
    
    # 时间限制配置
    max_commit_age_days: int = 30       # 最大提交年龄（天）
    data_retention_days: int = 90       # 数据保留时间（天）
    cache_cleanup_interval: int = 3600  # 缓存清理间隔（秒）
    
    # 缓存配置
    enable_cache: bool = True           # 是否启用缓存
    cache_ttl_seconds: int = 300        # 缓存生存时间 (5分钟)
    cache_max_size: int = 100           # 最大缓存条目数
    
    # 重试配置
    max_retries: int = 3                # 最大重试次数
    retry_delay: float = 2.0            # 重试延迟 (秒)
    retry_backoff_factor: float = 2.0   # 重试延迟倍数
    
    # 请求频率控制
    daily_request_limit: int = 1000     # 每日请求限制
    hourly_request_limit: int = 100     # 每小时请求限制
    burst_request_limit: int = 20       # 突发请求限制
    cooldown_period: int = 300          # 冷却期（秒）
    
    # 内容过滤配置
    include_merge_commits: bool = True   # 是否包含合并提交
    include_bot_commits: bool = False    # 是否包含机器人提交
    max_commit_message_length: int = 200 # 提交消息最大长度
    max_file_patch_size: int = 10000     # 文件补丁最大大小 (字符)
    
    # 分支配置
    default_branch: str = "main"         # 默认分支
    allowed_branches: Optional[list] = None  # 允许的分支列表 (None表示所有分支)
    
    # 安全配置
    webhook_secret: str = ""             # Webhook密钥
    allowed_webhook_events: list = None  # 允许的webhook事件
    
    # 调试配置
    debug_mode: bool = False             # 调试模式
    log_api_calls: bool = False          # 记录API调用
    verbose_errors: bool = False         # 详细错误信息

    def __post_init__(self):
        """初始化后处理"""
        # 设置默认的允许webhook事件
        if self.allowed_webhook_events is None:
            self.allowed_webhook_events = ['push', 'ping', 'pull_request']
        
        # 验证配置
        self._validate_config()
    
    def _validate_config(self):
        """验证配置参数"""
        # 验证数量限制
        if self.max_commits_per_request <= 0:
            raise ValueError("max_commits_per_request must be positive")
        if self.max_commits_per_request > 100:  # GitHub API限制
            raise ValueError("max_commits_per_request cannot exceed 100")
        
        # 验证时间间隔
        if self.min_request_interval < 0:
            raise ValueError("min_request_interval cannot be negative")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        
        # 验证重试配置
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.retry_delay < 0:
            raise ValueError("retry_delay cannot be negative")
        
        # 验证时间限制配置
        if self.max_commit_age_days <= 0:
            raise ValueError("max_commit_age_days must be positive")
        if self.data_retention_days <= 0:
            raise ValueError("data_retention_days must be positive")
        if self.data_retention_days < self.max_commit_age_days:
            raise ValueError("data_retention_days should be >= max_commit_age_days")
        
        # 验证GET请求间隔（推荐至少1秒）
        if self.get_request_interval < 0.5:
            logger.warning(f"GET请求间隔过短 ({self.get_request_interval}s)，可能触发GitHub速率限制")
        
        # 验证请求频率控制
        if self.daily_request_limit <= 0:
            raise ValueError("daily_request_limit must be positive")
        if self.hourly_request_limit <= 0:
            raise ValueError("hourly_request_limit must be positive")
        if self.hourly_request_limit * 24 > self.daily_request_limit:
            logger.warning("hourly_request_limit * 24 > daily_request_limit，可能导致每日限制过早触发")

@dataclass
class RateLimitConfig:
    """速率限制配置"""
    
    # GitHub API速率限制
    requests_per_hour: int = 5000        # 每小时请求数 (认证用户)
    requests_per_minute: int = 100       # 每分钟请求数
    search_requests_per_minute: int = 30 # 搜索API每分钟请求数
    
    # 自定义限制
    burst_limit: int = 10               # 突发请求限制
    concurrent_requests: int = 3        # 并发请求数
    
    # 限流策略
    enable_adaptive_delay: bool = True   # 自适应延迟
    backoff_on_rate_limit: bool = True  # 触发限制时退避
    respect_retry_after: bool = True    # 遵守Retry-After头

class GitHubConfig:
    """GitHub配置管理器"""
    
    def __init__(self):
        logger.info("初始化GitHub配置管理器")
        self.api_config = self._load_api_config()
        self.rate_limit_config = self._load_rate_limit_config()
        logger.info(f"配置加载完成，仓库: {self.get_repository_full_name() if self.is_configured() else '未配置'}")
    
    def _load_api_config(self) -> GitHubApiConfig:
        """加载API配置"""
        logger.debug("加载GitHub API配置")
        return GitHubApiConfig(
            # 从环境变量加载基础配置
            token=os.getenv('GITHUB_TOKEN', ''),
            repo_owner=os.getenv('REPO_OWNER', ''),
            repo_name=os.getenv('REPO_NAME', ''),
            webhook_secret=os.getenv('GITHUB_WEBHOOK_SECRET', ''),
            
            # 从环境变量加载限制配置
            max_commits_per_request=int(os.getenv('GITHUB_MAX_COMMITS', '10')),
            max_files_per_commit=int(os.getenv('GITHUB_MAX_FILES', '50')),
            max_pull_requests=int(os.getenv('GITHUB_MAX_PRS', '20')),
            max_search_results=int(os.getenv('GITHUB_MAX_SEARCH', '30')),
            
            # 时间配置
            min_request_interval=float(os.getenv('GITHUB_MIN_INTERVAL', '1.0')),
            get_request_interval=float(os.getenv('GITHUB_GET_INTERVAL', '2.0')),
            webhook_trigger_delay=float(os.getenv('GITHUB_WEBHOOK_DELAY', '1.0')),
            timeout_seconds=int(os.getenv('GITHUB_TIMEOUT', '30')),
            
            # 时间限制配置
            max_commit_age_days=int(os.getenv('GITHUB_MAX_COMMIT_AGE', '30')),
            data_retention_days=int(os.getenv('GITHUB_DATA_RETENTION', '90')),
            cache_cleanup_interval=int(os.getenv('GITHUB_CACHE_CLEANUP', '3600')),
            
            # 缓存配置
            enable_cache=os.getenv('GITHUB_ENABLE_CACHE', 'true').lower() == 'true',
            cache_ttl_seconds=int(os.getenv('GITHUB_CACHE_TTL', '300')),
            
            # 重试配置
            max_retries=int(os.getenv('GITHUB_MAX_RETRIES', '3')),
            retry_delay=float(os.getenv('GITHUB_RETRY_DELAY', '2.0')),
            
            # 请求频率控制
            daily_request_limit=int(os.getenv('GITHUB_DAILY_LIMIT', '1000')),
            hourly_request_limit=int(os.getenv('GITHUB_HOURLY_LIMIT', '100')),
            burst_request_limit=int(os.getenv('GITHUB_BURST_LIMIT', '20')),
            cooldown_period=int(os.getenv('GITHUB_COOLDOWN', '300')),
            
            # 内容过滤
            include_merge_commits=os.getenv('GITHUB_INCLUDE_MERGES', 'true').lower() == 'true',
            include_bot_commits=os.getenv('GITHUB_INCLUDE_BOTS', 'false').lower() == 'true',
            max_commit_message_length=int(os.getenv('GITHUB_MAX_MESSAGE_LEN', '200')),
            max_file_patch_size=int(os.getenv('GITHUB_MAX_PATCH_SIZE', '10000')),
            
            # 分支配置
            default_branch=os.getenv('GITHUB_DEFAULT_BRANCH', 'main'),
            
            # 调试配置
            debug_mode=os.getenv('GITHUB_DEBUG', 'false').lower() == 'true',
            log_api_calls=os.getenv('GITHUB_LOG_API', 'false').lower() == 'true',
            verbose_errors=os.getenv('GITHUB_VERBOSE_ERRORS', 'false').lower() == 'true',
        )
    
    def _load_rate_limit_config(self) -> RateLimitConfig:
        """加载速率限制配置"""
        logger.debug("加载GitHub速率限制配置")
        return RateLimitConfig(
            requests_per_hour=int(os.getenv('GITHUB_RATE_HOUR', '5000')),
            requests_per_minute=int(os.getenv('GITHUB_RATE_MINUTE', '100')),
            search_requests_per_minute=int(os.getenv('GITHUB_SEARCH_RATE', '30')),
            
            burst_limit=int(os.getenv('GITHUB_BURST_LIMIT', '10')),
            concurrent_requests=int(os.getenv('GITHUB_CONCURRENT', '3')),
            
            enable_adaptive_delay=os.getenv('GITHUB_ADAPTIVE_DELAY', 'true').lower() == 'true',
            backoff_on_rate_limit=os.getenv('GITHUB_BACKOFF', 'true').lower() == 'true',
            respect_retry_after=os.getenv('GITHUB_RESPECT_RETRY', 'true').lower() == 'true',
        )
    
    def get_api_config(self) -> GitHubApiConfig:
        """获取API配置"""
        return self.api_config
    
    def get_rate_limit_config(self) -> RateLimitConfig:
        """获取速率限制配置"""
        return self.rate_limit_config
    
    def is_configured(self) -> bool:
        """检查是否已正确配置"""
        return (bool(self.api_config.token) and 
                bool(self.api_config.repo_owner) and 
                bool(self.api_config.repo_name))
    
    def get_repository_full_name(self) -> str:
        """获取完整仓库名称"""
        return f"{self.api_config.repo_owner}/{self.api_config.repo_name}"
    
    def get_recommended_request_interval(self) -> float:
        """获取推荐的请求间隔（基于速率限制配置）"""
        # 基于每分钟请求数计算推荐间隔
        if self.rate_limit_config.requests_per_minute > 0:
            min_interval = 60.0 / self.rate_limit_config.requests_per_minute
            # 添加20%的安全边际
            recommended = min_interval * 1.2
            return max(recommended, self.api_config.get_request_interval)
        return self.api_config.get_request_interval
    
    def is_rate_limit_safe(self) -> bool:
        """检查当前配置是否在安全的速率限制范围内"""
        recommended = self.get_recommended_request_interval()
        current = self.api_config.get_request_interval
        return current >= recommended * 0.8  # 允许20%的偏差
    
    def update_config(self, **kwargs):
        """更新配置"""
        logger.info(f"更新配置项: {list(kwargs.keys())}")
        for key, value in kwargs.items():
            if hasattr(self.api_config, key):
                old_value = getattr(self.api_config, key)
                setattr(self.api_config, key, value)
                logger.debug(f"更新API配置 {key}: {old_value} -> {value}")
            elif hasattr(self.rate_limit_config, key):
                old_value = getattr(self.rate_limit_config, key)
                setattr(self.rate_limit_config, key, value)
                logger.debug(f"更新速率限制配置 {key}: {old_value} -> {value}")
            else:
                logger.error(f"未知的配置项: {key}")
                raise ValueError(f"Unknown config key: {key}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'api_config': {
                'repo_owner': self.api_config.repo_owner,
                'repo_name': self.api_config.repo_name,
                'base_url': self.api_config.base_url,
                'max_commits_per_request': self.api_config.max_commits_per_request,
                'max_files_per_commit': self.api_config.max_files_per_commit,
                'min_request_interval': self.api_config.min_request_interval,
                'timeout_seconds': self.api_config.timeout_seconds,
                'enable_cache': self.api_config.enable_cache,
                'cache_ttl_seconds': self.api_config.cache_ttl_seconds,
                'max_retries': self.api_config.max_retries,
                'default_branch': self.api_config.default_branch,
                'debug_mode': self.api_config.debug_mode,
            },
            'rate_limit_config': {
                'requests_per_hour': self.rate_limit_config.requests_per_hour,
                'requests_per_minute': self.rate_limit_config.requests_per_minute,
                'burst_limit': self.rate_limit_config.burst_limit,
                'concurrent_requests': self.rate_limit_config.concurrent_requests,
            }
        }

# 全局配置实例
github_config = GitHubConfig()
