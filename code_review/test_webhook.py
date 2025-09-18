#!/usr/bin/env python3
"""
GitHub Webhook 接口测试脚本
测试 /ai/git-webhook/ 接口的功能
"""

import requests
import json
import hashlib
import hmac
import os
from datetime import datetime

# 测试配置
WEBHOOK_URL = "http://localhost:8000/ai/git-webhook/"
STATUS_URL = "http://localhost:8000/ai/webhook-status/"
WEBHOOK_SECRET = "test-secret-key"  # 测试用的密钥

def generate_github_signature(payload_body, secret):
    """
    生成GitHub风格的签名
    """
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"

def create_test_push_payload():
    """
    创建测试用的GitHub push payload
    """
    return {
        "ref": "refs/heads/main",
        "before": "0000000000000000000000000000000000000000",
        "after": "1234567890abcdef1234567890abcdef12345678",
        "repository": {
            "id": 123456789,
            "name": "code_review",
            "full_name": "liuzijun12/code_review",
            "owner": {
                "login": "liuzijun12",
                "id": 12345,
                "type": "User"
            },
            "private": False,
            "html_url": "https://github.com/liuzijun12/code_review",
            "clone_url": "https://github.com/liuzijun12/code_review.git",
            "ssh_url": "git@github.com:liuzijun12/code_review.git"
        },
        "pusher": {
            "name": "liuzijun12",
            "email": "test@example.com"
        },
        "commits": [
            {
                "id": "1234567890abcdef1234567890abcdef12345678",
                "message": "测试提交：添加新功能",
                "timestamp": datetime.now().isoformat(),
                "url": "https://github.com/liuzijun12/code_review/commit/1234567890abcdef1234567890abcdef12345678",
                "author": {
                    "name": "liuzijun12",
                    "email": "test@example.com",
                    "username": "liuzijun12"
                },
                "modified": ["app_ai/views.py", "app_ai/models.py"],
                "added": ["app_ai/new_feature.py"],
                "removed": []
            }
        ]
    }

def create_test_ping_payload():
    """
    创建测试用的GitHub ping payload
    """
    return {
        "zen": "Responsive is better than fast.",
        "hook_id": 12345678,
        "hook": {
            "type": "Repository",
            "id": 12345678,
            "events": ["push"]
        },
        "repository": {
            "id": 123456789,
            "name": "code_review",
            "full_name": "liuzijun12/code_review",
            "owner": {
                "login": "liuzijun12",
                "id": 12345,
                "type": "User"
            }
        }
    }

def test_webhook_status():
    """
    测试webhook状态接口
    """
    print("🔍 测试 Webhook 状态接口...")
    try:
        response = requests.get(STATUS_URL)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("✅ 状态接口正常")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ 状态接口异常: {response.text}")
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保Django服务器正在运行")
        print("启动命令: python manage.py runserver")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False
    
    print("-" * 50)
    return True

def test_push_webhook():
    """
    测试push webhook
    """
    print("🚀 测试 Push Webhook...")
    
    # 创建测试数据
    payload = create_test_push_payload()
    payload_json = json.dumps(payload, ensure_ascii=False)
    
    # 生成签名
    signature = generate_github_signature(payload_json, WEBHOOK_SECRET)
    
    # 设置请求头
    headers = {
        'Content-Type': 'application/json',
        'X-Hub-Signature-256': signature,
        'X-GitHub-Event': 'push',
        'User-Agent': 'GitHub-Hookshot/test'
    }
    
    try:
        response = requests.post(WEBHOOK_URL, data=payload_json, headers=headers)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Push webhook 测试成功")
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        elif response.status_code == 403:
            print("❌ 签名验证失败或仓库不被允许")
            print("请检查环境变量配置:")
            print("- GITHUB_WEBHOOK_SECRET")
            print("- REPO_OWNER")
            print("- REPO_NAME")
            print(f"响应: {response.text}")
        else:
            print(f"❌ Push webhook 测试失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print("-" * 50)

def test_ping_webhook():
    """
    测试ping webhook
    """
    print("🏓 测试 Ping Webhook...")
    
    # 创建测试数据
    payload = create_test_ping_payload()
    payload_json = json.dumps(payload, ensure_ascii=False)
    
    # 生成签名
    signature = generate_github_signature(payload_json, WEBHOOK_SECRET)
    
    # 设置请求头
    headers = {
        'Content-Type': 'application/json',
        'X-Hub-Signature-256': signature,
        'X-GitHub-Event': 'ping',
        'User-Agent': 'GitHub-Hookshot/test'
    }
    
    try:
        response = requests.post(WEBHOOK_URL, data=payload_json, headers=headers)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Ping webhook 测试成功")
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Ping webhook 测试失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print("-" * 50)

def test_invalid_signature():
    """
    测试无效签名
    """
    print("🔐 测试无效签名...")
    
    payload = create_test_push_payload()
    payload_json = json.dumps(payload, ensure_ascii=False)
    
    # 故意使用错误的签名
    headers = {
        'Content-Type': 'application/json',
        'X-Hub-Signature-256': 'sha256=invalid_signature',
        'X-GitHub-Event': 'push',
        'User-Agent': 'GitHub-Hookshot/test'
    }
    
    try:
        response = requests.post(WEBHOOK_URL, data=payload_json, headers=headers)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 403:
            print("✅ 签名验证正常工作 - 正确拒绝了无效签名")
        else:
            print(f"❌ 签名验证可能有问题: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print("-" * 50)

def main():
    """
    主测试函数
    """
    print("=" * 60)
    print("🧪 GitHub Webhook 接口测试")
    print("=" * 60)
    
    print("\n📋 测试说明:")
    print("1. 请确保Django服务器正在运行: python manage.py runserver")
    print("2. 请设置环境变量:")
    print("   - GITHUB_WEBHOOK_SECRET=test-secret-key")
    print("   - REPO_OWNER=liuzijun12")
    print("   - REPO_NAME=code_review")
    print("\n" + "=" * 60)
    
    # 运行测试
    if not test_webhook_status():
        return
    
    test_push_webhook()
    test_ping_webhook()
    test_invalid_signature()
    
    print("🎉 测试完成!")
    print("\n💡 提示:")
    print("- 如果测试失败，请检查环境变量配置")
    print("- 确保Django服务器在localhost:8000运行")
    print("- 检查防火墙设置")

if __name__ == "__main__":
    main()
