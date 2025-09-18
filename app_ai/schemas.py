"""
统一数据格式定义模块
包含API响应格式和数据库模型对应的数据结构
"""

from typing import Dict, List, Optional, Any
from datetime import datetime


def success_response(data: Any, message: str = "success") -> Dict:
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


class DataSchemas:
    """核心数据结构定义 - 对应数据库和API的完整数据格式"""
    
    @staticmethod
    def complete_commit_data() -> Dict:
        """
        完整的提交数据结构 - 包含所有GitHub API返回的信息和数据库存储字段
        对应 GitCommitAnalysis 模型和 GitHub API 的完整数据
        """
        return {
            "commit_sha": str,              # 提交标识码 (40字符)
            "author_name": str,             # 提交人姓名
            "commit_timestamp": str,        # 提交时间 (ISO格式)
            "code_diff": str,               # 代码变更内容 (完整diff)
            "commit_message": str,          # 提交注释
            "analysis_suggestion": Optional[str],  # AI分析建议
            "created_at": str,              # 记录创建时间
            "updated_at": str,              # 记录更新时间
            "short_sha": str,               # 短SHA (8字符)
            "author_email": str,            # 作者邮箱
            "author_username": str,         # GitHub用户名
            "author_avatar_url": Optional[str],  # 头像链接
            
            # 提交者信息 (可能与作者不同)
            "committer_name": str,
            "committer_email": str,
            "committer_date": str,
            
            # 提交统计
            "stats": {
                "total_changes": int,       # 总变更行数
                "additions": int,           # 新增行数
                "deletions": int,           # 删除行数
                "files_changed": int        # 变更文件数
            },
            
            # 文件变更详情
            "files": List[{
                "filename": str,            # 文件名
                "status": str,              # added, modified, deleted, renamed
                "additions": int,           # 该文件新增行数
                "deletions": int,           # 该文件删除行数
                "changes": int,             # 该文件总变更行数
                "patch": Optional[str],     # 该文件的diff内容
                "blob_url": str,           # 文件在GitHub的链接
            }],
            
            # 链接信息
            "urls": {
                "html_url": str,           # GitHub页面链接
                "api_url": str,            # API链接
                "compare_url": str         # 对比链接
            },
            
            # 分支和仓库信息
            "repository": {
                "owner": str,              # 仓库所有者
                "name": str,               # 仓库名称
                "full_name": str,          # 完整仓库名
                "branch": str              # 分支名
            },
            
            # 父提交
            "parents": List[str],          # 父提交SHA列表
        }
    
    @staticmethod
    def webhook_push_data() -> Dict:
        """
        Webhook推送事件的数据结构
        用于接收和处理GitHub推送事件
        """
        return {
            # 推送基本信息
            "ref": str,                    # refs/heads/main
            "before": str,                 # 推送前的SHA
            "after": str,                  # 推送后的SHA
            "repository": {
                "full_name": str,          # 仓库全名
                "name": str,               # 仓库名
                "owner": {
                    "login": str,          # 所有者用户名
                    "name": str            # 所有者姓名
                },
                "clone_url": str,          # 克隆链接
                "ssh_url": str             # SSH链接
            },
            
            # 推送者信息
            "pusher": {
                "name": str,               # 推送者姓名
                "email": str               # 推送者邮箱
            },
            
            # 提交列表
            "commits": List[{
                "id": str,                 # 提交SHA
                "message": str,            # 提交消息
                "timestamp": str,          # 提交时间
                "author": {
                    "name": str,           # 作者姓名
                    "email": str,          # 作者邮箱
                    "username": str        # GitHub用户名
                },
                "added": List[str],        # 新增文件列表
                "modified": List[str],     # 修改文件列表
                "removed": List[str],      # 删除文件列表
                "url": str                 # 提交链接
            }],
            
            # 对比链接
            "compare": str,                # 对比链接
            "head_commit": Optional[Dict], # 头部提交详情
        }

# API参数验证规则
PARAM_RULES = {
    'limit': {'type': 'int', 'min': 1, 'max': 100, 'default': 10},
    'page': {'type': 'int', 'min': 1, 'default': 1},
    'include_diff': {'type': 'bool', 'default': False},
    'sha': {'type': 'str', 'min_len': 7, 'max_len': 40},
    'branch': {'type': 'str', 'min_len': 1, 'max_len': 255, 'default': 'main'},
    'state': {'type': 'choice', 'choices': ['open', 'closed', 'all'], 'default': 'open'},
    'query': {'type': 'str', 'min_len': 1, 'max_len': 1000},
}

# 支持的数据类型
DATA_TYPES = [
    'repository_info',      # 仓库信息
    'recent_commits',       # 最近提交
    'commit_details',       # 提交详情
    'pull_requests',        # 拉取请求
    'repository_stats',     # 仓库统计
    'search_code',          # 代码搜索
    'client_status',        # 客户端状态
    'webhook_status'        # Webhook状态
]

def get_param_rule(param_name: str) -> Optional[Dict]:
    """获取参数验证规则"""
    return PARAM_RULES.get(param_name)


def is_valid_data_type(data_type: str) -> bool:
    """检查数据类型是否有效"""
    return data_type in DATA_TYPES


def format_commit_for_database(github_commit_data: Dict) -> Dict:
    """
    将GitHub API返回的提交数据格式化为数据库存储格式
    对应 GitCommitAnalysis 模型的字段
    """
    return {
        'commit_sha': github_commit_data['sha'],
        'author_name': github_commit_data['commit']['author']['name'],
        'commit_timestamp': github_commit_data['commit']['author']['date'],
        'code_diff': github_commit_data.get('patch', ''),  # 完整的diff内容
        'commit_message': github_commit_data['commit']['message'],
        'analysis_suggestion': None,  # 初始为空，后续AI分析后填入
    }


def format_commit_for_api(db_commit_data: Dict, github_data: Dict = None) -> Dict:
    """
    将数据库中的提交数据格式化为API响应格式
    结合数据库数据和GitHub API数据
    """
    result = {
        # 数据库字段
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
    
    # 如果有GitHub数据，添加扩展信息
    if github_data:
        # 安全地获取作者信息
        commit_author = github_data.get('commit', {}).get('author', {})
        github_author = github_data.get('author', {})
        
        result.update({
            'author_email': commit_author.get('email', 'N/A'),
            'author_username': github_author.get('login', 'Unknown') if github_author else 'Unknown',
            'author_avatar_url': github_author.get('avatar_url') if github_author else None,
            'stats': github_data.get('stats', {}),
            'files': github_data.get('files', []),
            'urls': {
                'html_url': github_data.get('html_url', ''),
                'api_url': github_data.get('url', ''),
            },
            'parents': [
                parent['sha'] if isinstance(parent, dict) and 'sha' in parent else str(parent)
                for parent in github_data.get('parents', [])
            ]
        })
    
    return result


COMMON_RESPONSES = {
    "INVALID_PARAM": lambda param, error: error_response(f"Invalid parameter '{param}': {error}", 400),
    "MISSING_PARAM": lambda param: error_response(f"Missing required parameter: {param}", 400),
    "UNAUTHORIZED": error_response("Unauthorized: Invalid or missing authentication", 401),
    "FORBIDDEN": error_response("Forbidden: Access denied", 403),
    "NOT_FOUND": lambda resource: error_response(f"{resource} not found", 404),
    "SERVER_ERROR": lambda error: error_response(f"Internal server error: {error}", 500)
}


__all__ = [
    'success_response',
    'error_response', 
    'DataSchemas',
    'PARAM_RULES',
    'DATA_TYPES',
    'get_param_rule',
    'is_valid_data_type',
    'format_commit_for_database',
    'format_commit_for_api',
    'COMMON_RESPONSES'
]