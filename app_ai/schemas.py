"""
数据格式定义模块 - 异步任务专用
只保留异步任务需要的核心数据结构和格式化函数
"""

from typing import Dict
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
    'ASYNC_DATA_TYPES',
    'is_valid_async_data_type'
]