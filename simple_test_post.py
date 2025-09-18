#!/usr/bin/env python3
"""
简化版本的POST测试脚本
快速测试webhook接口是否返回200状态码
"""

import requests
import json


def test_webhook_post():
    """简单测试webhook POST请求"""
    
    # 配置
    webhook_url = "http://127.0.0.1:8000/ai/git-webhook/"
    
    # 简单的测试payload
    test_payload = {
        "repository": {
            "name": "test-repo",
            "full_name": "testowner/test-repo",
            "owner": {
                "login": "testowner"
            }
        },
        "pusher": {
            "name": "testowner",
            "email": "test@example.com"
        }
    }
    
    # 请求头
    headers = {
        'Content-Type': 'application/json',
        'X-GitHub-Event': 'push',
        'X-GitHub-Delivery': 'test-delivery-123',
        'User-Agent': 'GitHub-Hookshot/test'
    }
    
    try:
        print("🚀 发送POST请求到webhook...")
        print(f"URL: {webhook_url}")
        
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers=headers,
            timeout=10
        )
        
        print(f"📊 状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 测试通过！返回200状态码")
            
            try:
                response_data = response.json()
                print("📄 响应内容:")
                print(json.dumps(response_data, indent=2, ensure_ascii=False))
                
                # 检查是否有GET请求触发信息
                if 'triggered_get_request' in response_data:
                    print("✅ 检测到GET请求触发功能")
                else:
                    print("⚠️ 未检测到GET请求触发信息")
                    
            except json.JSONDecodeError:
                print("⚠️ 响应不是有效的JSON格式")
                print(f"响应内容: {response.text}")
        else:
            print(f"❌ 测试失败！状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败！请确保Django服务器正在运行:")
        print("   python manage.py runserver")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


if __name__ == "__main__":
    print("🧪 简单POST测试")
    print("="*30)
    
    success = test_webhook_post()
    
    print("\n" + "="*30)
    if success:
        print("🎉 测试成功！")
    else:
        print("💥 测试失败！") 