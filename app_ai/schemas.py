"""
数据格式定义模块 - 异步任务专用
只保留异步任务需要的核心数据结构和格式化函数
"""

from typing import Dict, Optional
from datetime import datetime


def success_response(data, message: str = "success") -> Dict:
    """统一成功响应格式"""
    return {
        "status": "success",
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }


def error_response(error: str, status_code: int = 400) -> Dict:
    """统一错误响应格式"""
    return {
        "status": "error",
        "error": error,
        "status_code": status_code,
        "timestamp": datetime.now().isoformat()
    }


def format_commit_for_database(github_commit_data: Dict) -> Dict:
    """
    将GitHub API返回的提交数据格式化为数据库存储格式
    异步任务专用 - 简化版本
    """
    # 处理raw_patch字段
    raw_patch = github_commit_data.get('raw_patch', '')
    if not raw_patch and 'files' in github_commit_data:
        # 如果没有raw_patch但有files，尝试从files中提取
        patches = []
        for file_data in github_commit_data['files']:
            if isinstance(file_data, dict) and 'patch' in file_data:
                patches.append(file_data['patch'])
        raw_patch = '\n'.join(patches)
    
    return {
        'commit_sha': github_commit_data['sha'],
        'author_name': github_commit_data['commit']['author']['name'],
        'commit_timestamp': github_commit_data['commit']['author']['date'],
        'code_diff': raw_patch,
        'commit_message': github_commit_data['commit']['message'],
        'analysis_suggestion': None,  # 初始为空，后续AI分析后填入
    }


def format_commit_for_api(db_commit_data: Dict, github_data: Dict = None) -> Dict:
    """
    将数据库中的提交数据格式化为API响应格式
    异步任务专用 - 简化版本
    """
    result = {
        'commit_sha': db_commit_data['commit_sha'],
        'short_sha': db_commit_data['commit_sha'][:8],
        'author_name': db_commit_data['author_name'],
        'commit_message': db_commit_data['commit_message'],
        'commit_timestamp': db_commit_data['commit_timestamp'],
        'code_diff': db_commit_data['code_diff'],
        'analysis_suggestion': db_commit_data.get('analysis_suggestion'),
        'created_at': db_commit_data.get('created_at'),
        'updated_at': db_commit_data.get('updated_at'),
    }
    
    # 如果有GitHub数据，添加基本扩展信息
    if github_data:
        commit_author = github_data.get('commit', {}).get('author', {})
        github_author = github_data.get('author', {})
        
        result.update({
            'author_email': commit_author.get('email', 'N/A'),
            'author_username': github_author.get('login', 'Unknown') if github_author else 'Unknown',
            'urls': {
                'html_url': github_data.get('html_url', ''),
                'api_url': github_data.get('url', ''),
            }
        })
    
    return result


# 异步任务支持的数据类型 - 只支持单个提交处理
ASYNC_DATA_TYPES = [
    'commit_details',       # 单个提交详情（唯一支持的类型）
]


def is_valid_async_data_type(data_type: str) -> bool:
    """检查异步数据类型是否有效"""
    return data_type in ASYNC_DATA_TYPES


__all__ = [
    'success_response',
    'error_response', 
    'format_commit_for_database',
    'format_commit_for_api',
    'ASYNC_DATA_TYPES',
    'is_valid_async_data_type'
]