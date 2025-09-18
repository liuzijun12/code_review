#!/usr/bin/env python3
"""
测试Ollama服务脚本
生成模拟的代码提交，使用Ollama进行代码分析和提交解释
"""

import os
import sys
import django
import json
import time
from pathlib import Path
from datetime import datetime

# 设置Django环境
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code_review.settings')
django.setup()

from app_ai.ollama_client import ollama_client


# 模拟代码示例
SAMPLE_CODES = {
    "python_bug": {
        "filename": "user_auth.py",
        "language": "Python",
        "code": '''
def authenticate_user(username, password):
    # 存在安全问题的代码
    if username == "admin" and password == "123456":
        return True
    
    # SQL注入漏洞
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    result = execute_query(query)
    
    if result:
        # 密码明文存储
        return result[0]['password'] == password
    return False

def get_user_data(user_id):
    # 没有输入验证
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return execute_query(query)
''',
        "issues": ["硬编码密码", "SQL注入", "明文密码", "输入验证缺失"]
    },
    
    "javascript_performance": {
        "filename": "data_processor.js",
        "language": "JavaScript",
        "code": '''
// 性能问题的JavaScript代码
function processLargeDataSet(data) {
    let result = [];
    
    // 低效的嵌套循环
    for (let i = 0; i < data.length; i++) {
        for (let j = 0; j < data.length; j++) {
            if (data[i].id === data[j].parentId) {
                // 频繁的DOM操作
                document.getElementById('status').innerHTML = `Processing ${i}/${data.length}`;
                result.push({
                    parent: data[i],
                    child: data[j]
                });
            }
        }
    }
    
    // 内存泄漏风险
    window.globalData = result;
    
    return result;
}

// 没有错误处理
async function fetchUserData(userId) {
    const response = await fetch(`/api/users/${userId}`);
    const userData = await response.json();
    return userData;
}
''',
        "issues": ["O(n²)复杂度", "频繁DOM操作", "内存泄漏", "错误处理缺失"]
    },
    
    "java_clean": {
        "filename": "OrderService.java",
        "language": "Java",
        "code": '''
public class OrderService {
    private final OrderRepository orderRepository;
    private final PaymentService paymentService;
    private final NotificationService notificationService;
    
    public OrderService(OrderRepository orderRepository, 
                       PaymentService paymentService,
                       NotificationService notificationService) {
        this.orderRepository = orderRepository;
        this.paymentService = paymentService;
        this.notificationService = notificationService;
    }
    
    @Transactional
    public OrderResult processOrder(OrderRequest request) {
        try {
            // 验证订单
            validateOrder(request);
            
            // 创建订单
            Order order = createOrder(request);
            order = orderRepository.save(order);
            
            // 处理支付
            PaymentResult paymentResult = paymentService.processPayment(
                order.getId(), request.getPaymentInfo()
            );
            
            if (paymentResult.isSuccessful()) {
                order.setStatus(OrderStatus.PAID);
                orderRepository.save(order);
                
                // 发送通知
                notificationService.sendOrderConfirmation(order);
                
                return OrderResult.success(order);
            } else {
                order.setStatus(OrderStatus.PAYMENT_FAILED);
                orderRepository.save(order);
                return OrderResult.failure("Payment failed: " + paymentResult.getErrorMessage());
            }
            
        } catch (ValidationException e) {
            return OrderResult.failure("Validation failed: " + e.getMessage());
        } catch (Exception e) {
            log.error("Order processing failed", e);
            return OrderResult.failure("Internal error occurred");
        }
    }
    
    private void validateOrder(OrderRequest request) {
        if (request == null) {
            throw new ValidationException("Order request cannot be null");
        }
        if (request.getItems() == null || request.getItems().isEmpty()) {
            throw new ValidationException("Order must contain at least one item");
        }
        // 更多验证逻辑...
    }
}
''',
        "issues": ["较好的代码结构", "适当的错误处理", "事务管理"]
    }
}

# 模拟提交数据
SAMPLE_COMMITS = [
    {
        "sha": "abc123def456789",
        "message": "修复用户认证安全漏洞",
        "author": "张开发",
        "timestamp": "2025-01-15T10:30:00Z",
        "files": [
            {
                "filename": "user_auth.py",
                "status": "modified",
                "additions": 15,
                "deletions": 8,
                "patch": '''@@ -1,10 +1,15 @@
 def authenticate_user(username, password):
-    if username == "admin" and password == "123456":
-        return True
+    # 移除硬编码密码
+    if not username or not password:
+        return False
     
-    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
+    # 使用参数化查询防止SQL注入
+    query = "SELECT * FROM users WHERE username = ? AND password_hash = ?"
+    password_hash = hash_password(password)
     result = execute_query(query, [username, password_hash])
     
-    return result[0]['password'] == password if result else False
+    return bool(result)'''
            }
        ]
    },
    {
        "sha": "def456ghi789abc",
        "message": "优化数据处理性能，添加错误处理",
        "author": "李前端",
        "timestamp": "2025-01-15T14:20:00Z",
        "files": [
            {
                "filename": "data_processor.js",
                "status": "modified",
                "additions": 25,
                "deletions": 12,
                "patch": '''@@ -1,20 +1,30 @@
 function processLargeDataSet(data) {
+    if (!data || !Array.isArray(data)) {
+        throw new Error('Invalid data input');
+    }
+    
-    let result = [];
-    for (let i = 0; i < data.length; i++) {
-        for (let j = 0; j < data.length; j++) {
+    // 使用Map优化查找性能 O(n) instead of O(n²)
+    const parentMap = new Map();
+    data.forEach(item => {
+        if (!parentMap.has(item.parentId)) {
+            parentMap.set(item.parentId, []);
+        }
+        parentMap.get(item.parentId).push(item);
+    });
+    
+    const result = [];
+    data.forEach(item => {
+        const children = parentMap.get(item.id) || [];
+        children.forEach(child => {
             result.push({
-                parent: data[i],
-                child: data[j]
+                parent: item,
+                child: child
             });
+        });
+    });
-    }
-    
-    window.globalData = result;
     return result;
 }'''
            }
        ]
    },
    {
        "sha": "ghi789jkl012mno",
        "message": "重构订单服务，改进架构设计",
        "author": "王架构",
        "timestamp": "2025-01-15T16:45:00Z",
        "files": [
            {
                "filename": "OrderService.java",
                "status": "added",
                "additions": 65,
                "deletions": 0,
                "patch": '''@@ -0,0 +1,65 @@
+public class OrderService {
+    private final OrderRepository orderRepository;
+    private final PaymentService paymentService;
+    private final NotificationService notificationService;
+    
+    // 构造函数注入，支持依赖反转
+    public OrderService(OrderRepository orderRepository, 
+                       PaymentService paymentService,
+                       NotificationService notificationService) {
+        this.orderRepository = orderRepository;
+        this.paymentService = paymentService;
+        this.notificationService = notificationService;
+    }
+    
+    @Transactional
+    public OrderResult processOrder(OrderRequest request) {
+        try {
+            validateOrder(request);
+            Order order = createOrder(request);
+            order = orderRepository.save(order);
+            
+            PaymentResult paymentResult = paymentService.processPayment(
+                order.getId(), request.getPaymentInfo()
+            );
+            
+            if (paymentResult.isSuccessful()) {
+                order.setStatus(OrderStatus.PAID);
+                orderRepository.save(order);
+                notificationService.sendOrderConfirmation(order);
+                return OrderResult.success(order);
+            } else {
+                order.setStatus(OrderStatus.PAYMENT_FAILED);
+                orderRepository.save(order);
+                return OrderResult.failure("Payment failed: " + paymentResult.getErrorMessage());
+            }
+        } catch (ValidationException e) {
+            return OrderResult.failure("Validation failed: " + e.getMessage());
+        } catch (Exception e) {
+            log.error("Order processing failed", e);
+            return OrderResult.failure("Internal error occurred");
+        }
+    }
+}'''
            }
        ]
    }
]


def print_separator(title="", width=70):
    """打印分隔线"""
    if title:
        padding = (width - len(title) - 2) // 2
        print("=" * padding + f" {title} " + "=" * padding)
    else:
        print("=" * width)


def test_ollama_connection():
    """测试Ollama连接"""
    print_separator("Ollama连接测试")
    
    try:
        print("🔄 正在检查Ollama服务连接...")
        connection_result = ollama_client.check_connection()
        
        print(f"📊 连接状态: {connection_result.get('status')}")
        print(f"📍 服务地址: {connection_result.get('base_url')}")
        
        if connection_result['status'] == 'connected':
            print("✅ Ollama服务连接成功!")
            models = connection_result.get('available_models', [])
            print(f"🤖 可用模型: {', '.join(models)}")
            return True
        else:
            print(f"❌ 连接失败: {connection_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ 连接测试异常: {e}")
        return False


def test_code_review():
    """测试代码审查功能"""
    print_separator("代码审查测试")
    
    for code_name, code_info in SAMPLE_CODES.items():
        print(f"\n🔍 正在分析 {code_info['filename']} ({code_info['language']})")
        print(f"📋 已知问题: {', '.join(code_info['issues'])}")
        
        try:
            print("⏳ Ollama分析中...")
            start_time = time.time()
            
            result = ollama_client.code_review(
                code_content=code_info['code'],
                model_name=None  # 使用默认模型
            )
            
            end_time = time.time()
            analysis_time = end_time - start_time
            
            if result['status'] == 'success':
                print(f"✅ 分析完成 (耗时: {analysis_time:.1f}秒)")
                print(f"🤖 使用模型: {result.get('model_used', 'Unknown')}")
                print(f"📝 代码长度: {result.get('code_length', 0)} 字符")
                
                print("\n📄 AI分析结果:")
                print("-" * 50)
                response = result.get('response', '').strip()
                # 限制显示长度
                if len(response) > 1000:
                    print(response[:1000] + "\n\n[... 内容过长，已截断 ...]")
                else:
                    print(response)
                print("-" * 50)
                
                # 显示性能统计
                if 'total_duration' in result:
                    total_ms = result['total_duration'] / 1000000  # 纳秒转毫秒
                    print(f"⚡ 模型推理时间: {total_ms:.0f}ms")
                
            else:
                print(f"❌ 分析失败: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ 代码审查异常: {e}")
        
        print("\n" + "="*50)
        time.sleep(1)  # 避免请求过快


def test_commit_explanation():
    """测试提交解释功能"""
    print_separator("提交解释测试")
    
    for i, commit_data in enumerate(SAMPLE_COMMITS, 1):
        print(f"\n📝 正在分析提交 {i}/{len(SAMPLE_COMMITS)}")
        print(f"🔸 SHA: {commit_data['sha'][:12]}...")
        print(f"🔸 作者: {commit_data['author']}")
        print(f"🔸 消息: {commit_data['message']}")
        print(f"🔸 文件数: {len(commit_data['files'])}")
        
        try:
            print("⏳ Ollama分析中...")
            start_time = time.time()
            
            result = ollama_client.explain_commit(
                commit_data=commit_data,
                model_name=None  # 使用默认模型
            )
            
            end_time = time.time()
            analysis_time = end_time - start_time
            
            if result['status'] == 'success':
                print(f"✅ 分析完成 (耗时: {analysis_time:.1f}秒)")
                print(f"🤖 使用模型: {result.get('model_used', 'Unknown')}")
                print(f"📁 分析文件数: {result.get('files_count', 0)}")
                
                print("\n📄 AI提交解释:")
                print("-" * 50)
                response = result.get('response', '').strip()
                # 限制显示长度
                if len(response) > 800:
                    print(response[:800] + "\n\n[... 内容过长，已截断 ...]")
                else:
                    print(response)
                print("-" * 50)
                
                # 显示性能统计
                if 'total_duration' in result:
                    total_ms = result['total_duration'] / 1000000
                    print(f"⚡ 模型推理时间: {total_ms:.0f}ms")
                
            else:
                print(f"❌ 分析失败: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ 提交解释异常: {e}")
        
        print("\n" + "="*50)
        time.sleep(1)  # 避免请求过快


def test_chat_functionality():
    """测试聊天功能"""
    print_separator("聊天功能测试")
    
    test_questions = [
        "请简单介绍一下代码审查的最佳实践",
        "什么是技术债务？如何管理？",
        "解释一下SOLID原则"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n💬 测试问题 {i}: {question}")
        
        try:
            print("⏳ Ollama思考中...")
            start_time = time.time()
            
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的软件开发顾问，请提供简洁而有用的建议。"
                },
                {
                    "role": "user", 
                    "content": question
                }
            ]
            
            result = ollama_client.chat(
                messages=messages,
                model_name=None  # 使用默认模型
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            if result['status'] == 'success':
                print(f"✅ 回答完成 (耗时: {response_time:.1f}秒)")
                print(f"🤖 使用模型: {result.get('model', 'Unknown')}")
                
                print("\n📄 AI回答:")
                print("-" * 40)
                response = result.get('response', '').strip()
                # 限制显示长度
                if len(response) > 600:
                    print(response[:600] + "\n\n[... 内容过长，已截断 ...]")
                else:
                    print(response)
                print("-" * 40)
                
            else:
                print(f"❌ 聊天失败: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ 聊天功能异常: {e}")
        
        time.sleep(1)


def show_client_status():
    """显示客户端状态"""
    print_separator("客户端状态")
    
    try:
        status = ollama_client.get_client_status()
        
        # 显示连接信息
        client_info = status.get('ollama_client', {})
        print(f"📍 服务地址: {client_info.get('base_url')}")
        print(f"🔗 连接状态: {client_info.get('connection_status')}")
        print(f"🤖 模型数量: {client_info.get('models_count')}")
        print(f"⏱️ 请求超时: {client_info.get('request_timeout')}秒")
        print(f"🔄 最大重试: {client_info.get('max_retries')}次")
        
        # 显示配置信息
        config = status.get('configuration', {})
        print(f"\n⚙️ 配置信息:")
        print(f"  📏 最大代码长度: {config.get('max_code_length', 'N/A')}")
        print(f"  🐛 调试模式: {config.get('debug_mode', 'N/A')}")
        print(f"  🚀 流式响应: {config.get('enable_streaming', 'N/A')}")
        
        # 显示功能列表
        capabilities = status.get('capabilities', [])
        print(f"\n🛠️ 支持功能: {', '.join(capabilities)}")
        
    except Exception as e:
        print(f"❌ 获取状态失败: {e}")


def main():
    """主函数"""
    print("🧪 Ollama服务测试脚本")
    print("生成模拟代码提交，测试AI分析功能")
    print_separator()
    
    # 显示测试开始时间
    start_time = datetime.now()
    print(f"⏰ 测试开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 测试连接
    if not test_ollama_connection():
        print("\n❌ Ollama服务连接失败，请检查服务是否启动")
        print("💡 启动命令: docker-compose up -d ollama")
        return
    
    # 2. 显示客户端状态
    show_client_status()
    
    # 3. 测试代码审查
    test_code_review()
    
    # 4. 测试提交解释
    test_commit_explanation()
    
    # 5. 测试聊天功能
    test_chat_functionality()
    
    # 显示测试结束时间
    end_time = datetime.now()
    duration = end_time - start_time
    
    print_separator("测试完成")
    print(f"⏰ 测试结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️ 总耗时: {duration.total_seconds():.1f}秒")
    print("🎉 Ollama服务测试完成！")
    
    print("\n💡 测试总结:")
    print("• 代码审查: 检测安全漏洞、性能问题、代码质量")
    print("• 提交解释: 分析代码变更的目的和影响")
    print("• 聊天问答: 回答开发相关问题")
    print("• 配置管理: 自动加载配置，支持重试机制")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试脚本异常: {e}")
        import traceback
        traceback.print_exc() 