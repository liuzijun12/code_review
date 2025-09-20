#!/usr/bin/env python3
"""
测试完整的异步流程：Git数据获取 → 自动触发Ollama分析
"""
import os
import sys
import django
import time
import requests
import json

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code_review.settings')
django.setup()

from app_ai.async_get import fetch_github_data_async
from app_ai.async_ollama import start_ollama_analysis
from app_ai.sql_client import DatabaseClient
from celery.result import AsyncResult

def test_async_flow():
    """测试完整的异步流程"""
    print("🧪 测试完整异步流程：Git数据获取 → 自动触发Ollama分析")
    print("=" * 60)
    
    # 1. 检查未分析的提交数量
    print("📊 检查当前未分析提交数量:")
    unanalyzed_before = DatabaseClient.get_unanalyzed_commits(limit=100)
    print(f"  未分析提交数量: {len(unanalyzed_before)}")
    
    # 2. 启动异步Git数据获取任务
    print("\n🚀 启动异步Git数据获取任务:")
    git_task = fetch_github_data_async.delay(
        data_type='recent_commits',
        params={
            'branch': 'main',
            'limit': 5,
            'include_diff': True
        }
    )
    print(f"  Git任务ID: {git_task.id}")
    print(f"  初始状态: {git_task.state}")
    
    # 3. 等待Git任务完成
    print("\n⏳ 等待Git任务完成...")
    timeout = 60  # 60秒超时
    start_time = time.time()
    
    while not git_task.ready() and (time.time() - start_time) < timeout:
        print(f"  Git任务状态: {git_task.state}")
        time.sleep(2)
    
    if git_task.ready():
        git_result = git_task.result
        print(f"✅ Git任务完成!")
        print(f"  状态: {git_result.get('status', 'unknown')}")
        
        # 检查是否自动触发了Ollama分析
        if 'ollama_analysis' in git_result:
            ollama_info = git_result['ollama_analysis']
            print(f"\n🤖 Ollama分析自动触发:")
            print(f"  触发状态: {ollama_info.get('triggered', False)}")
            
            if ollama_info.get('triggered'):
                ollama_task_id = ollama_info.get('task_id')
                print(f"  Ollama任务ID: {ollama_task_id}")
                
                # 等待Ollama任务完成
                print("\n⏳ 等待Ollama分析完成...")
                ollama_task = AsyncResult(ollama_task_id)
                
                ollama_timeout = 120  # 2分钟超时
                ollama_start = time.time()
                
                while not ollama_task.ready() and (time.time() - ollama_start) < ollama_timeout:
                    print(f"  Ollama任务状态: {ollama_task.state}")
                    time.sleep(3)
                
                if ollama_task.ready():
                    ollama_result = ollama_task.result
                    print(f"✅ Ollama分析完成!")
                    print(f"  分析状态: {ollama_result.get('status', 'unknown')}")
                    print(f"  成功分析: {ollama_result.get('analyzed_count', 0)} 个提交")
                    print(f"  失败数量: {ollama_result.get('failed_count', 0)} 个提交")
                    print(f"  执行时间: {ollama_result.get('execution_time', 0):.2f} 秒")
                else:
                    print(f"⏰ Ollama分析超时，当前状态: {ollama_task.state}")
            else:
                print(f"  触发失败: {ollama_info.get('message', 'Unknown error')}")
        else:
            print("\n❌ 没有找到Ollama分析触发信息")
            
    else:
        print(f"⏰ Git任务超时，当前状态: {git_task.state}")
    
    # 4. 检查最终结果
    print("\n📊 检查最终结果:")
    unanalyzed_after = DatabaseClient.get_unanalyzed_commits(limit=100)
    print(f"  分析前未分析提交: {len(unanalyzed_before)}")
    print(f"  分析后未分析提交: {len(unanalyzed_after)}")
    
    if len(unanalyzed_after) < len(unanalyzed_before):
        print(f"✅ 成功分析了 {len(unanalyzed_before) - len(unanalyzed_after)} 个提交!")
    elif len(unanalyzed_after) > len(unanalyzed_before):
        print(f"📈 新增了 {len(unanalyzed_after) - len(unanalyzed_before)} 个未分析提交")
    else:
        print("📊 未分析提交数量没有变化")

def test_webhook_simulation():
    """模拟webhook请求测试"""
    print("\n🌐 测试webhook异步处理:")
    print("=" * 40)
    
    # 模拟webhook请求
    webhook_url = "http://localhost:8000/ai/git-webhook/"
    
    # 简单的测试payload
    test_payload = {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "liuzijun12/ai-detection"
        },
        "commits": [
            {"id": "test123", "message": "Test commit"}
        ]
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers={
                'Content-Type': 'application/json',
                'X-GitHub-Event': 'push'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Webhook请求成功!")
            print(f"  响应: {result.get('message', 'No message')}")
            if 'async_task_id' in result:
                print(f"  异步任务ID: {result['async_task_id']}")
        else:
            print(f"❌ Webhook请求失败: {response.status_code}")
            print(f"  响应: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")

if __name__ == "__main__":
    print("🎯 异步流程完整测试")
    print("请确保以下服务正在运行:")
    print("  1. Django开发服务器 (python manage.py runserver)")
    print("  2. Celery Worker (celery -A code_review worker)")
    print("  3. Redis服务器")
    print("  4. Ollama服务")
    print()
    
    # 等待用户确认
    input("按Enter键开始测试...")
    
    # 执行测试
    test_async_flow()
    test_webhook_simulation()
    
    print("\n🎉 测试完成!")
