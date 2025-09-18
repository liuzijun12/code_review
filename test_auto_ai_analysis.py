#!/usr/bin/env python3
"""
测试自动AI分析流程
验证完整的流程：POST请求 → GET请求 → AI分析 → 数据库存储
"""

import os
import sys
import django
import requests
import json
import time
from pathlib import Path
from datetime import datetime

# 设置Django环境
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code_review.settings')
django.setup()

from app_ai.models import GitCommitAnalysis


def print_separator(title="", width=70):
    """打印分隔线"""
    if title:
        padding = (width - len(title) - 2) // 2
        print("=" * padding + f" {title} " + "=" * padding)
    else:
        print("=" * width)


def check_database_status():
    """检查数据库状态"""
    try:
        total_commits = GitCommitAnalysis.objects.count()
        analyzed_commits = GitCommitAnalysis.objects.filter(
            analysis_suggestion__isnull=False
        ).count()
        unanalyzed_commits = total_commits - analyzed_commits
        
        print(f"📊 数据库状态:")
        print(f"   总提交数: {total_commits}")
        print(f"   已分析: {analyzed_commits}")
        print(f"   未分析: {unanalyzed_commits}")
        
        if total_commits > 0:
            # 显示最近的提交
            recent_commits = GitCommitAnalysis.objects.all()[:3]
            print(f"\n📄 最近的提交:")
            for commit in recent_commits:
                has_ai = "🤖" if commit.analysis_suggestion else "⭕"
                print(f"   {has_ai} {commit.commit_sha[:8]} - {commit.author_name} - {commit.commit_message[:50]}...")
                if commit.analysis_suggestion:
                    print(f"      AI分析预览: {commit.analysis_suggestion[:100]}...")
        
        return {
            'total': total_commits,
            'analyzed': analyzed_commits,
            'unanalyzed': unanalyzed_commits
        }
        
    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")
        return None


def test_webhook_with_auto_ai():
    """测试webhook自动AI分析流程"""
    print_separator("Webhook自动AI分析测试")
    
    webhook_url = "http://127.0.0.1:8000/ai/git-webhook/"
    
    # 模拟真实的GitHub webhook payload
    payload = {
        "ref": "refs/heads/main",
        "before": "0000000000000000000000000000000000000000",
        "after": "abc123def456789012345678901234567890abcd",
        "repository": {
            "id": 123456789,
            "name": "ai-detection",
            "full_name": "liuzijun12/ai-detection",
            "private": False,
            "owner": {
                "login": "liuzijun12",
                "id": 186311701
            },
            "html_url": "https://github.com/liuzijun12/ai-detection",
            "default_branch": "main"
        },
        "pusher": {
            "name": "liuzijun12",
            "email": "test@example.com"
        },
        "sender": {
            "login": "liuzijun12",
            "id": 186311701
        },
        "commits": [
            {
                "id": "abc123def456789012345678901234567890abcd",
                "message": "修复用户认证安全漏洞和性能优化",
                "timestamp": datetime.now().isoformat(),
                "author": {
                    "name": "liuzijun",
                    "email": "test@example.com",
                    "username": "liuzijun12"
                },
                "added": ["security_fix.py"],
                "removed": [],
                "modified": ["auth.py", "performance.js"]
            }
        ],
        "head_commit": {
            "id": "abc123def456789012345678901234567890abcd",
            "message": "修复用户认证安全漏洞和性能优化",
            "timestamp": datetime.now().isoformat(),
            "author": {
                "name": "liuzijun",
                "email": "test@example.com",
                "username": "liuzijun12"
            },
            "added": ["security_fix.py"],
            "removed": [],
            "modified": ["auth.py", "performance.js"]
        }
    }
    
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'GitHub-Hookshot/test',
        'X-GitHub-Delivery': f'auto-ai-test-{int(time.time())}',
        'X-GitHub-Event': 'push',
        'X-GitHub-Hook-ID': '123456789',
        'X-Debug-Skip-Signature': 'true'  # 调试模式
    }
    
    print("🚀 发送Webhook请求，触发自动AI分析流程...")
    print(f"📍 URL: {webhook_url}")
    print(f"📋 事件: push")
    print(f"📄 仓库: {payload['repository']['full_name']}")
    print(f"📝 提交: {payload['head_commit']['message']}")
    
    try:
        # 记录开始时间
        start_time = time.time()
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=180  # 3分钟超时，AI分析需要时间
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n📊 响应状态码: {response.status_code}")
        print(f"⏱️ 总耗时: {total_time:.1f}秒")
        
        if response.status_code == 200:
            print("✅ Webhook请求成功！")
            
            try:
                response_data = response.json()
                
                # 检查POST处理结果
                print(f"\n📄 POST处理结果:")
                print(f"   状态: {response_data.get('status', 'unknown')}")
                print(f"   消息: {response_data.get('message', 'N/A')}")
                
                # 重点检查GET请求触发和AI分析
                if 'triggered_get_request' in response_data:
                    get_info = response_data['triggered_get_request']
                    print(f"\n🔄 GET请求触发:")
                    print(f"   状态: {get_info.get('status')}")
                    print(f"   消息: {get_info.get('message')}")
                    
                    # 检查GET请求结果
                    get_result = get_info.get('get_data_result', {})
                    if get_result.get('status') == 'success':
                        print(f"\n📊 GET请求执行成功:")
                        
                        commits_data = get_result.get('commits_data', {})
                        commits_count = commits_data.get('commits_count', 0)
                        print(f"   获取提交数: {commits_count}")
                        
                        # 🎯 重点检查数据库保存和AI分析结果
                        if 'database_save' in get_result:
                            db_save = get_result['database_save']
                            print(f"\n🗄️ 数据库保存和AI分析结果:")
                            print(f"   状态: {'✅ 成功' if db_save.get('success') else '❌ 失败'}")
                            print(f"   消息: {db_save.get('message')}")
                            print(f"   保存数量: {db_save.get('saved_count', 0)}/{db_save.get('total_count', 0)}")
                            print(f"   AI分析数量: {db_save.get('analyzed_count', 0)}")
                            print(f"   AI分析启用: {'✅' if db_save.get('ai_analysis_enabled') else '❌'}")
                            
                            if db_save.get('success') and db_save.get('analyzed_count', 0) > 0:
                                print("🎉 AI自动分析流程成功！")
                                return True
                            elif db_save.get('success'):
                                print("⚠️ 数据保存成功，但AI分析可能失败")
                                return False
                            else:
                                print("❌ 数据库保存失败")
                                return False
                        else:
                            print("⚠️ 响应中没有数据库保存信息")
                            return False
                    else:
                        print(f"❌ GET请求失败: {get_result.get('error')}")
                        return False
                else:
                    print("❌ 没有检测到GET请求触发")
                    return False
                
            except json.JSONDecodeError:
                print("❌ 响应JSON解析失败")
                print(f"原始响应: {response.text}")
                return False
        else:
            print(f"❌ Webhook请求失败！状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时！AI分析可能需要更长时间")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败！请确保Django服务器正在运行")
        return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False


def verify_database_changes(initial_stats):
    """验证数据库变化"""
    print_separator("数据库变化验证")
    
    final_stats = check_database_status()
    
    if initial_stats and final_stats:
        total_change = final_stats['total'] - initial_stats['total']
        analyzed_change = final_stats['analyzed'] - initial_stats['analyzed']
        
        print(f"\n📈 数据库变化:")
        print(f"   新增提交: {total_change}")
        print(f"   新增AI分析: {analyzed_change}")
        
        if total_change > 0:
            print("✅ 成功添加了新的提交记录")
            
            if analyzed_change > 0:
                print("🤖 成功添加了AI分析结果")
                
                # 显示最新的AI分析
                try:
                    latest_analyzed = GitCommitAnalysis.objects.filter(
                        analysis_suggestion__isnull=False
                    ).order_by('-created_at').first()
                    
                    if latest_analyzed:
                        print(f"\n📝 最新AI分析预览:")
                        print(f"   提交: {latest_analyzed.commit_sha[:8]}")
                        print(f"   作者: {latest_analyzed.author_name}")
                        print(f"   消息: {latest_analyzed.commit_message}")
                        print(f"   AI分析: {latest_analyzed.analysis_suggestion[:200]}...")
                        
                except Exception as e:
                    print(f"⚠️ 无法显示AI分析详情: {e}")
                    
                return True
            else:
                print("⚠️ 添加了提交但没有AI分析")
                return False
        else:
            print("⚠️ 没有添加新的提交记录")
            return False
    else:
        print("❌ 无法获取数据库统计信息")
        return False


def test_direct_database_query():
    """测试直接数据库查询"""
    print_separator("直接数据库查询测试")
    
    try:
        from app_ai.sql_client import DatabaseClient
        
        # 获取最近的提交记录
        success, data, error = DatabaseClient.get_saved_commits(limit=3, offset=0)
        
        if success and data:
            print("✅ 数据库查询成功")
            
            commits = data.get('commits', [])
            stats = data.get('analysis_stats', {})
            
            print(f"\n📊 分析统计:")
            print(f"   总提交数: {stats.get('total_commits', 0)}")
            print(f"   已分析: {stats.get('analyzed_commits', 0)}")
            print(f"   未分析: {stats.get('unanalyzed_commits', 0)}")
            
            if commits:
                print(f"\n📄 最近的提交记录:")
                for i, commit in enumerate(commits, 1):
                    has_ai = "🤖" if commit.get('has_analysis') else "⭕"
                    print(f"   {i}. {has_ai} {commit.get('short_sha')} - {commit.get('author_name')}")
                    print(f"      消息: {commit.get('commit_message')}")
                    if commit.get('has_analysis') and commit.get('analysis_preview'):
                        print(f"      AI分析: {commit.get('analysis_preview')}")
            
            return True
        else:
            print(f"❌ 数据库查询失败: {error}")
            return False
            
    except Exception as e:
        print(f"❌ 数据库查询异常: {e}")
        return False


def main():
    """主测试函数"""
    print("🤖 自动AI分析流程测试")
    print("验证完整流程：POST → GET → AI分析 → 数据库存储")
    print_separator()
    
    # 显示测试开始时间
    start_time = datetime.now()
    print(f"⏰ 测试开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 检查初始数据库状态
    print_separator("初始状态检查")
    initial_stats = check_database_status()
    
    # 2. 测试webhook自动AI分析流程
    webhook_success = test_webhook_with_auto_ai()
    
    # 等待一下，确保数据库操作完成
    print("\n⏳ 等待数据库操作完成...")
    time.sleep(3)
    
    # 3. 验证数据库变化
    database_success = verify_database_changes(initial_stats)
    
    # 4. 测试直接数据库查询
    query_success = test_direct_database_query()
    
    # 显示测试结束时间
    end_time = datetime.now()
    duration = end_time - start_time
    
    print_separator("测试完成")
    print(f"⏰ 测试结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️ 总耗时: {duration.total_seconds():.1f}秒")
    
    # 测试结果总结
    print(f"\n📊 测试结果总结:")
    print(f"   Webhook流程: {'✅ 成功' if webhook_success else '❌ 失败'}")
    print(f"   数据库变化: {'✅ 成功' if database_success else '❌ 失败'}")
    print(f"   数据库查询: {'✅ 成功' if query_success else '❌ 失败'}")
    
    if webhook_success and database_success:
        print("\n🎉 自动AI分析流程测试成功！")
        print("💡 流程说明:")
        print("   1. POST请求触发webhook处理")
        print("   2. 自动触发GET请求获取提交数据")
        print("   3. 获取详细提交信息（包含diff）")
        print("   4. 使用Ollama进行AI分析")
        print("   5. 将分析结果保存到数据库")
        print("   6. 返回完整的处理结果")
    else:
        print("\n❌ 自动AI分析流程测试失败")
        print("💡 可能的问题:")
        print("   1. Django服务器未启动")
        print("   2. Ollama服务未启动")
        print("   3. GitHub Token配置问题")
        print("   4. 数据库连接问题")
        print("   5. 网络连接问题")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试脚本异常: {e}")
        import traceback
        traceback.print_exc() 