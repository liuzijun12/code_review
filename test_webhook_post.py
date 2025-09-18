#!/usr/bin/env python3
"""
测试webhook POST请求的脚本
确保POST请求能够返回200状态码，并验证GET请求触发功能
"""

import requests
import json
import hashlib
import hmac
import time
from datetime import datetime


class WebhookTester:
    """Webhook测试器"""
    
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url
        self.webhook_url = f"{base_url}/ai/git-webhook/"
        self.webhook_secret = "your_webhook_secret_here"  # 从配置中获取
        
    def generate_signature(self, payload_body):
        """生成GitHub webhook签名"""
        if not self.webhook_secret:
            return None
        
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def create_test_push_payload(self):
        """创建测试用的push事件payload"""
        return {
            "ref": "refs/heads/main",
            "before": "0000000000000000000000000000000000000000",
            "after": "1234567890abcdef1234567890abcdef12345678",
            "repository": {
                "id": 123456789,
                "name": "test-repo",
                "full_name": "testowner/test-repo",
                "owner": {
                    "login": "testowner",
                    "id": 12345,
                    "avatar_url": "https://github.com/images/error/testowner_happy.gif"
                },
                "private": False,
                "html_url": "https://github.com/testowner/test-repo",
                "description": "Test repository for webhook testing",
                "default_branch": "main"
            },
            "pusher": {
                "name": "testowner",
                "email": "test@example.com"
            },
            "sender": {
                "login": "testowner",
                "id": 12345,
                "avatar_url": "https://github.com/images/error/testowner_happy.gif"
            },
            "commits": [
                {
                    "id": "1234567890abcdef1234567890abcdef12345678",
                    "tree_id": "abcdef1234567890abcdef1234567890abcdef12",
                    "distinct": True,
                    "message": "Test commit message",
                    "timestamp": datetime.now().isoformat(),
                    "url": "https://github.com/testowner/test-repo/commit/1234567890abcdef1234567890abcdef12345678",
                    "author": {
                        "name": "Test Author",
                        "email": "test@example.com",
                        "username": "testowner"
                    },
                    "committer": {
                        "name": "Test Author",
                        "email": "test@example.com",
                        "username": "testowner"
                    },
                    "added": ["new_file.py"],
                    "removed": [],
                    "modified": ["existing_file.py"]
                }
            ],
            "head_commit": {
                "id": "1234567890abcdef1234567890abcdef12345678",
                "tree_id": "abcdef1234567890abcdef1234567890abcdef12",
                "distinct": True,
                "message": "Test commit message",
                "timestamp": datetime.now().isoformat(),
                "url": "https://github.com/testowner/test-repo/commit/1234567890abcdef1234567890abcdef12345678",
                "author": {
                    "name": "Test Author",
                    "email": "test@example.com",
                    "username": "testowner"
                },
                "committer": {
                    "name": "Test Author",
                    "email": "test@example.com",
                    "username": "testowner"
                },
                "added": ["new_file.py"],
                "removed": [],
                "modified": ["existing_file.py"]
            }
        }
    
    def create_test_ping_payload(self):
        """创建测试用的ping事件payload"""
        return {
            "zen": "Non-blocking is better than blocking.",
            "hook_id": 123456789,
            "hook": {
                "type": "Repository",
                "id": 123456789,
                "name": "web",
                "active": True,
                "events": ["push", "pull_request"],
                "config": {
                    "content_type": "json",
                    "insecure_ssl": "0",
                    "url": self.webhook_url
                }
            },
            "repository": {
                "id": 123456789,
                "name": "test-repo",
                "full_name": "testowner/test-repo",
                "owner": {
                    "login": "testowner",
                    "id": 12345
                },
                "private": False,
                "html_url": "https://github.com/testowner/test-repo"
            },
            "sender": {
                "login": "testowner",
                "id": 12345,
                "avatar_url": "https://github.com/images/error/testowner_happy.gif"
            }
        }
    
    def send_webhook_request(self, event_type, payload):
        """发送webhook请求"""
        payload_json = json.dumps(payload, separators=(',', ':'))
        payload_body = payload_json.encode('utf-8')
        
        headers = {
            'Content-Type': 'application/json',
            'X-GitHub-Event': event_type,
            'X-GitHub-Delivery': f'test-delivery-{int(time.time())}',
            'User-Agent': 'GitHub-Hookshot/test'
        }
        
        # 生成签名（如果配置了secret）
        signature = self.generate_signature(payload_body)
        if signature:
            headers['X-Hub-Signature-256'] = signature
        
        try:
            print(f"🚀 发送 {event_type} 事件到 {self.webhook_url}")
            print(f"📦 Payload: {json.dumps(payload, indent=2)[:200]}...")
            
            response = requests.post(
                self.webhook_url,
                data=payload_body,
                headers=headers,
                timeout=30
            )
            
            return response
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求失败: {e}")
            return None
    
    def test_push_event(self):
        """测试push事件"""
        print("\n" + "="*50)
        print("🧪 测试 PUSH 事件")
        print("="*50)
        
        payload = self.create_test_push_payload()
        response = self.send_webhook_request('push', payload)
        
        return self.analyze_response(response, 'push')
    
    def test_ping_event(self):
        """测试ping事件"""
        print("\n" + "="*50)
        print("🧪 测试 PING 事件")
        print("="*50)
        
        payload = self.create_test_ping_payload()
        response = self.send_webhook_request('ping', payload)
        
        return self.analyze_response(response, 'ping')
    
    def test_unsupported_event(self):
        """测试不支持的事件类型"""
        print("\n" + "="*50)
        print("🧪 测试不支持的事件类型")
        print("="*50)
        
        payload = {"test": "data"}
        response = self.send_webhook_request('pull_request', payload)
        
        return self.analyze_response(response, 'pull_request')
    
    def analyze_response(self, response, event_type):
        """分析响应结果"""
        if not response:
            print("❌ 无响应")
            return False
        
        print(f"📊 状态码: {response.status_code}")
        print(f"📋 响应头: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"📄 响应内容:")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
            
            # 检查状态码
            if response.status_code == 200:
                print("✅ 状态码检查: PASS (200)")
                
                # 检查是否触发了GET请求
                if 'triggered_get_request' in response_data:
                    get_status = response_data['triggered_get_request'].get('status')
                    if get_status == 'success':
                        print("✅ GET请求触发: PASS")
                    else:
                        print(f"⚠️ GET请求触发: FAIL ({get_status})")
                        print(f"   错误信息: {response_data['triggered_get_request'].get('message')}")
                else:
                    print("⚠️ GET请求触发: 未检测到触发信息")
                
                return True
            else:
                print(f"❌ 状态码检查: FAIL ({response.status_code})")
                return False
                
        except json.JSONDecodeError:
            print(f"❌ 响应解析失败: {response.text}")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🎯 开始Webhook POST测试")
        print(f"🌐 目标URL: {self.webhook_url}")
        print(f"🔐 使用签名: {'是' if self.webhook_secret else '否'}")
        
        results = {
            'push': self.test_push_event(),
            'ping': self.test_ping_event(),
            'unsupported': self.test_unsupported_event()
        }
        
        print("\n" + "="*50)
        print("📊 测试结果汇总")
        print("="*50)
        
        total_tests = len(results)
        passed_tests = sum(results.values())
        
        for event_type, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{event_type.upper():15} {status}")
        
        print(f"\n🎯 总体结果: {passed_tests}/{total_tests} 通过")
        
        if passed_tests == total_tests:
            print("🎉 所有测试通过！POST请求能够正常返回200状态码")
        else:
            print("⚠️ 部分测试失败，请检查服务器配置")
        
        return results


def main():
    """主函数"""
    print("🚀 Webhook POST 测试工具")
    print("确保Django服务器正在运行: python manage.py runserver")
    
    # 等待用户确认
    input("\n按Enter键开始测试...")
    
    tester = WebhookTester()
    results = tester.run_all_tests()
    
    return results


if __name__ == "__main__":
    main() 