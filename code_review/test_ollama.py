#!/usr/bin/env python3
"""
Ollama连接测试脚本
测试本地Docker中的Ollama服务连接
"""

import os
import sys
import requests
import json
from datetime import datetime

# 设置Django环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code_review.settings')

import django
django.setup()

from app_ai.ollama_client import OllamaClient


def print_section(title):
    """打印分节标题"""
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")


def print_result(result, title="结果"):
    """格式化打印结果"""
    print(f"\n{title}:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def test_ollama_connection():
    """测试Ollama连接"""
    print_section("Ollama连接测试")
    
    # 创建客户端实例
    client = OllamaClient()
    print(f"Ollama服务地址: {client.base_url}")
    
    # 1. 测试连接状态
    print("\n1. 检查连接状态...")
    connection_result = client.check_connection()
    print_result(connection_result, "连接状态")
    
    if connection_result['status'] != 'connected':
        print("\n❌ Ollama服务未连接，请检查Docker容器是否运行")
        print("\n🔧 故障排除步骤:")
        for step in connection_result.get('troubleshooting', []):
            print(f"   • {step}")
        return False
    
    print("✅ Ollama服务连接成功!")
    
    # 2. 测试模型列表
    print("\n2. 获取可用模型...")
    models_result = client.list_models()
    print_result(models_result, "模型列表")
    
    if models_result['status'] == 'success':
        models = models_result.get('models', [])
        print(f"\n📋 找到 {len(models)} 个可用模型:")
        for model in models:
            name = model.get('name', 'Unknown')
            size = model.get('size', 0)
            size_mb = size / (1024 * 1024) if size > 0 else 0
            print(f"   • {name} ({size_mb:.1f} MB)")
    
    return True


def test_ollama_api_endpoints():
    """测试Ollama API接口"""
    print_section("API接口测试")
    
    base_url = "http://localhost:8000"
    endpoints = [
        {
            'name': 'Ollama状态检查',
            'url': f'{base_url}/ai/github-data/?type=ollama_status',
            'method': 'GET'
        },
        {
            'name': '获取模型列表',
            'url': f'{base_url}/ai/github-data/?type=ollama_models',
            'method': 'GET'
        }
    ]
    
    for endpoint in endpoints:
        print(f"\n🔍 测试: {endpoint['name']}")
        print(f"URL: {endpoint['url']}")
        
        try:
            response = requests.get(endpoint['url'], timeout=10)
            
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ 请求成功")
                print_result(data, "响应数据")
            else:
                print(f"❌ 请求失败: {response.status_code}")
                print(f"错误信息: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ 无法连接到Django服务器")
            print("请确保Django开发服务器正在运行: python manage.py runserver")
        except requests.exceptions.Timeout:
            print("❌ 请求超时")
        except Exception as e:
            print(f"❌ 请求异常: {str(e)}")


def test_code_review():
    """测试代码审查功能"""
    print_section("代码审查功能测试")
    
    # 创建客户端实例
    client = OllamaClient()
    
    # 检查连接
    if client.check_connection()['status'] != 'connected':
        print("❌ Ollama服务未连接，跳过代码审查测试")
        return
    
    # 测试代码
    test_code = '''
def calculate_total(items):
    total = 0
    for item in items:
        if item['price'] > 0:
            total += item['price'] * item['quantity']
    return total
'''
    
    print("📝 测试代码:")
    print(test_code)
    
    print("\n🔍 正在进行代码审查...")
    
    # 进行代码审查
    review_result = client.code_review(test_code, 'llama2')
    print_result(review_result, "代码审查结果")
    
    if review_result['status'] == 'success':
        print("✅ 代码审查完成")
        print(f"📊 统计信息:")
        print(f"   • 代码长度: {review_result.get('code_length', 0)} 字符")
        print(f"   • 使用模型: {review_result.get('model_used', 'Unknown')}")
        print(f"   • 处理时间: {review_result.get('total_duration', 0) / 1000000:.2f} ms")
    else:
        print("❌ 代码审查失败")


def main():
    """主函数"""
    print("🚀 Ollama服务测试开始")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 测试连接
    connection_ok = test_ollama_connection()
    
    # 2. 测试API接口
    test_ollama_api_endpoints()
    
    # 3. 测试代码审查功能
    if connection_ok:
        test_code_review()
    
    print_section("测试完成")
    print("🎉 所有测试已完成!")
    
    if not connection_ok:
        print("\n💡 提示: 如果Ollama服务未运行，请使用以下命令启动:")
        print("   docker-compose up -d ollama")
        print("   或者")
        print("   docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama")


if __name__ == "__main__":
    main()
