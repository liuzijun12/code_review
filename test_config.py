#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试GitHub配置系统
"""

import os
import django
import json

# 设置Django环境
os.environ['DJANGO_SETTINGS_MODULE'] = 'code_review.settings'
django.setup()

from app_ai.config import github_config
from app_ai.git_client import GitHubDataClient

def test_config():
    """测试配置系统"""
    print("🧪 测试GitHub配置系统")
    print("=" * 60)
    
    # 1. 测试配置加载
    print("📋 1. 配置加载测试")
    print("-" * 40)
    
    api_config = github_config.get_api_config()
    rate_config = github_config.get_rate_limit_config()
    
    print(f"✅ API配置加载成功")
    print(f"   仓库: {api_config.repo_owner}/{api_config.repo_name}")
    print(f"   Token: {'已配置' if api_config.token else '未配置'}")
    print(f"   最大提交数: {api_config.max_commits_per_request}")
    print(f"   最小间隔: {api_config.min_request_interval}s")
    print(f"   超时时间: {api_config.timeout_seconds}s")
    print(f"   最大重试: {api_config.max_retries}")
    print(f"   调试模式: {api_config.debug_mode}")
    
    print(f"\n✅ 速率限制配置加载成功")
    print(f"   每小时请求: {rate_config.requests_per_hour}")
    print(f"   每分钟请求: {rate_config.requests_per_minute}")
    print(f"   并发请求: {rate_config.concurrent_requests}")
    
    # 2. 测试配置验证
    print(f"\n📋 2. 配置验证测试")
    print("-" * 40)
    
    is_configured = github_config.is_configured()
    print(f"配置完整性: {'✅ 完整' if is_configured else '❌ 不完整'}")
    
    full_name = github_config.get_repository_full_name()
    print(f"完整仓库名: {full_name}")
    
    # 3. 测试客户端配置应用
    print(f"\n📋 3. 客户端配置应用测试")
    print("-" * 40)
    
    client = GitHubDataClient()
    print(f"✅ 客户端创建成功")
    print(f"   使用配置: {type(client.config).__name__}")
    print(f"   请求计数: {client.request_count}")
    print(f"   最大提交数: {client.config.max_commits_per_request}")
    print(f"   最大文件数: {client.config.max_files_per_commit}")
    
    # 4. 测试配置字典转换
    print(f"\n📋 4. 配置序列化测试")
    print("-" * 40)
    
    config_dict = github_config.to_dict()
    print(f"✅ 配置转换为字典成功")
    print(f"配置内容:")
    print(json.dumps(config_dict, indent=2, ensure_ascii=False))
    
    # 5. 测试配置更新
    print(f"\n📋 5. 配置更新测试")
    print("-" * 40)
    
    original_debug = api_config.debug_mode
    print(f"原始调试模式: {original_debug}")
    
    try:
        github_config.update_config(debug_mode=True)
        print(f"✅ 配置更新成功")
        print(f"更新后调试模式: {api_config.debug_mode}")
        
        # 恢复原始值
        github_config.update_config(debug_mode=original_debug)
        print(f"✅ 配置恢复成功")
        
    except Exception as e:
        print(f"❌ 配置更新失败: {e}")
    
    # 6. 测试环境变量覆盖
    print(f"\n📋 6. 环境变量测试")
    print("-" * 40)
    
    env_vars = [
        'GITHUB_MAX_COMMITS',
        'GITHUB_MIN_INTERVAL', 
        'GITHUB_TIMEOUT',
        'GITHUB_DEBUG',
        'GITHUB_DEFAULT_BRANCH'
    ]
    
    for var in env_vars:
        value = os.getenv(var, '未设置')
        print(f"   {var}: {value}")
    
    print(f"\n🎉 配置系统测试完成!")

if __name__ == "__main__":
    test_config() 