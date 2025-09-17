#!/usr/bin/env python3
"""
测试运行脚本
设置环境变量并运行webhook测试
"""

import os
import sys
import subprocess
import time

def set_test_env():
    """
    设置测试环境变量
    """
    test_env = {
        'DEBUG': 'True',
        'SECRET_KEY': 'django-insecure-test-key-for-webhook-testing',
        'GITHUB_WEBHOOK_SECRET': 'test-secret-key',
        'REPO_OWNER': 'liuzijun12',
        'REPO_NAME': 'code_review',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1'
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
        print(f"✅ 设置环境变量: {key}={value}")

def check_django_server():
    """
    检查Django服务器是否运行
    """
    import requests
    try:
        response = requests.get("http://localhost:8000/ai/webhook-status/", timeout=2)
        return True
    except:
        return False

def main():
    """
    主函数
    """
    print("🚀 启动Webhook测试")
    print("=" * 50)
    
    # 设置环境变量
    set_test_env()
    print()
    
    # 检查Django服务器
    if not check_django_server():
        print("⚠️  Django服务器未运行，正在启动...")
        print("请在另一个终端运行: python manage.py runserver")
        print("然后再运行测试脚本")
        print()
        
        # 询问是否继续
        choice = input("是否继续运行测试? (y/n): ")
        if choice.lower() != 'y':
            return
    
    # 运行测试
    print("🧪 开始运行webhook测试...")
    try:
        subprocess.run([sys.executable, "test_webhook.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 测试运行失败: {e}")
    except FileNotFoundError:
        print("❌ 找不到test_webhook.py文件")

if __name__ == "__main__":
    main()
