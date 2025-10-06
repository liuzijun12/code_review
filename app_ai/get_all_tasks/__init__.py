"""
Code Analysis Tasks Module

Provides:
1. GitHub repository content fetching (get_all_content)
2. Ollama AI code analysis (ollama_all_setting)
3. WeChat Work notification (wechat_notifier)
4. Celery task for repository analysis (tasks)
"""

# GitHub content functions
from .get_all_content import (
    collect_files_info,
    fetch_files_content,
    format_content_with_structure,
    get_repo_config_from_db,
)

# Ollama configuration
from .ollama_all_setting import (
    OllamaConfig,
    OllamaAnalysisClient,
    get_ollama_client,
    test_connection,
    ollama_config
)

# WeChat Work notification
from .wechat_notifier import (
    WeChatNotifier,
    send_analysis_to_wechat,
    get_wechat_webhook_from_db,
)

# Main Celery task
from .tasks import analyze_repository_summary_from_db

__all__ = [
    # GitHub
    'collect_files_info',
    'fetch_files_content',
    'format_content_with_structure',
    'get_repo_config_from_db',
    
    # Ollama
    'OllamaConfig',
    'OllamaAnalysisClient',
    'get_ollama_client',
    'test_connection',
    'ollama_config',
    
    # WeChat Work
    'WeChatNotifier',
    'send_analysis_to_wechat',
    'get_wechat_webhook_from_db',
    
    # Celery task
    'analyze_repository_summary_from_db',
]
