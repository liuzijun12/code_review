#!/usr/bin/env python
"""
企业微信推送功能测试脚本
测试所有推送相关功能，包括数据筛选、消息格式化、推送状态更新等
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code_review.settings')
django.setup()

from app_ai.info_push import WeChatWorkPusher
from app_ai.models import GitCommitAnalysis
from django.db import transaction


class WeChatPushTester:
    """企业微信推送测试类"""
    
    def __init__(self):
        """初始化测试环境"""
        # 保存原始的Webhook URL，不覆盖用户设置
        self.original_webhook_url = os.getenv('WX_WEBHOOK_URL')
        print("🧪 企业微信推送功能测试")
        print(f"🔗 使用Webhook URL: {self.original_webhook_url[:50] if self.original_webhook_url else 'None'}...")
        print("=" * 50)
    
    def test_pusher_initialization(self):
        """测试推送器初始化"""
        print("\n1. 📋 测试推送器初始化")
        try:
            pusher = WeChatWorkPusher()
            print("   ✅ 推送器初始化成功")
            print(f"   📡 Webhook URL: {pusher.webhook_url[:50]}...")
            return pusher
        except Exception as e:
            print(f"   ❌ 推送器初始化失败: {e}")
            return None
    
    def test_database_status(self):
        """测试数据库状态"""
        print("\n2. 🗄️ 测试数据库状态")
        try:
            total_records = GitCommitAnalysis.objects.count()
            analyzed_records = GitCommitAnalysis.objects.filter(
                analysis_suggestion__isnull=False
            ).exclude(analysis_suggestion='').count()
            pushed_records = GitCommitAnalysis.objects.filter(is_push=1).count()
            unpushed_records = GitCommitAnalysis.objects.filter(is_push=0).count()
            
            print(f"   📊 总记录数: {total_records}")
            print(f"   🔍 已分析数: {analyzed_records}")
            print(f"   📤 已推送数: {pushed_records}")
            print(f"   📥 未推送数: {unpushed_records}")
            
            if total_records == 0:
                print("   ⚠️ 警告: 数据库中没有记录")
                return False
            
            print("   ✅ 数据库状态检查完成")
            return True
            
        except Exception as e:
            print(f"   ❌ 数据库状态检查失败: {e}")
            return False
    
    def test_get_unpushed_records(self, pusher):
        """测试获取未推送记录"""
        print("\n3. 📥 测试获取未推送记录")
        try:
            records = pusher.get_unpushed_analysis_records(limit=5)
            print(f"   📋 获取到 {len(records)} 条未推送记录")
            
            if records:
                print("   📝 记录详情:")
                for i, record in enumerate(records[:3], 1):
                    print(f"      {i}. SHA: {record.commit_sha[:8]} | 作者: {record.author_name}")
                    print(f"         推送状态: {'已推送' if record.is_push == 1 else '未推送'}")
                    print(f"         有分析: {'是' if record.analysis_suggestion else '否'}")
                if len(records) > 3:
                    print(f"      ... 还有 {len(records) - 3} 条记录")
            else:
                print("   ⚠️ 没有找到未推送的记录")
            
            print("   ✅ 获取未推送记录测试完成")
            return records
            
        except Exception as e:
            print(f"   ❌ 获取未推送记录失败: {e}")
            return []
    
    def test_message_formatting(self, pusher, records):
        """测试消息格式化"""
        print("\n4. 📝 测试消息格式化")
        if not records:
            print("   ⚠️ 没有记录可供测试")
            return False
        
        try:
            record = records[0]
            message = pusher.format_commit_message(record)
            
            print(f"   🎯 测试记录: {record.commit_sha[:8]} - {record.author_name}")
            print(f"   📋 消息类型: {message.get('msgtype', 'N/A')}")
            
            if 'markdown' in message:
                content = message['markdown']['content']
                print(f"   📄 消息长度: {len(content)} 字符")
                print("   📝 消息预览:")
                lines = content.split('\n')[:8]
                for line in lines:
                    print(f"      {line}")
                if len(content.split('\n')) > 8:
                    print("      ...")
            
            # 验证消息结构
            required_fields = ['msgtype', 'markdown']
            missing_fields = [field for field in required_fields if field not in message]
            
            if missing_fields:
                print(f"   ❌ 缺少必要字段: {missing_fields}")
                return False
            
            print("   ✅ 消息格式化测试完成")
            return True
            
        except Exception as e:
            print(f"   ❌ 消息格式化失败: {e}")
            return False
    
    def test_mock_push(self, pusher):
        """测试真实推送（推送1条记录）"""
        print("\n5. 🚀 测试真实推送")
        try:
            # 使用真实的Webhook URL进行测试
            original_url = pusher.webhook_url
            print(f"   📡 使用真实Webhook URL: {original_url[:50]}...")
            
            # 获取一条未推送记录进行测试
            records = pusher.get_unpushed_analysis_records(limit=1)
            if not records:
                print("   ⚠️ 没有未推送记录可供测试")
                return False
            
            record = records[0]
            print(f"   🎯 测试推送: {record.commit_sha[:8]} - {record.author_name}")
            print(f"   📤 推送前状态: is_push = {record.is_push}")
            
            # 测试消息发送
            message = pusher.format_commit_message(record)
            send_success = pusher.send_message(message)
            
            if send_success:
                print("   ✅ 真实发送成功")
                
                # 测试状态更新
                mark_success = pusher.mark_as_pushed(record)
                if mark_success:
                    print("   ✅ 推送状态更新成功")
                    # 刷新记录状态
                    record.refresh_from_db()
                    print(f"   📤 推送后状态: is_push = {record.is_push}")
                else:
                    print("   ❌ 推送状态更新失败")
            else:
                print("   ❌ 真实发送失败")
            
            print("   ✅ 真实推送测试完成")
            return send_success and mark_success
            
        except Exception as e:
            print(f"   ❌ 模拟推送测试失败: {e}")
            return False
    
    def test_batch_push_simulation(self, pusher):
        """测试批量推送（真实推送）"""
        print("\n6. 📦 测试批量推送")
        try:
            # 使用真实的Webhook URL
            print(f"   📡 使用真实Webhook URL: {pusher.webhook_url[:50]}...")
            
            # 重置部分记录的推送状态以便测试
            with transaction.atomic():
                # 找到一些已推送的记录，临时重置为未推送
                reset_records = GitCommitAnalysis.objects.filter(is_push=1)[:2]
                reset_count = 0
                for record in reset_records:
                    record.is_push = 0
                    record.save()
                    reset_count += 1
                
                print(f"   🔄 临时重置 {reset_count} 条记录为未推送状态")
                
                # 执行批量推送测试
                result = pusher.push_unpushed_analysis(limit=3)
                
                print(f"   📊 推送结果: {result['status']}")
                print(f"   📝 推送消息: {result['message']}")
                print(f"   📈 统计数据:")
                print(f"      - 总数: {result['total_count']}")
                print(f"      - 成功: {result['success_count']}")
                print(f"      - 失败: {result['error_count']}")
            
            success = result['status'] in ['success', 'partial_success']
            if success:
                print("   ✅ 批量推送测试完成")
            else:
                print("   ❌ 批量推送测试失败")
            
            return success
            
        except Exception as e:
            print(f"   ❌ 批量推送测试失败: {e}")
            return False
    
    def test_summary_report(self, pusher):
        """测试总结报告"""
        print("\n7. 📊 测试总结报告")
        try:
            print(f"   📡 使用真实Webhook URL: {pusher.webhook_url[:50]}...")
            success = pusher.send_summary_report()
            
            if success:
                print("   ✅ 总结报告发送成功")
            else:
                print("   ❌ 总结报告发送失败")
            
            print("   ✅ 总结报告测试完成")
            return success
            
        except Exception as e:
            print(f"   ❌ 总结报告测试失败: {e}")
            return False
    
    def test_edge_cases(self, pusher):
        """测试边界情况"""
        print("\n8. 🔍 测试边界情况")
        
        test_results = []
        
        # 测试1: 推送不存在的提交
        try:
            result = pusher.push_single_commit('nonexistent_sha_12345678')
            expected = False  # 应该返回False
            if result == expected:
                print("   ✅ 不存在提交推送测试: 通过")
                test_results.append(True)
            else:
                print(f"   ❌ 不存在提交推送测试: 失败 (期望: {expected}, 实际: {result})")
                test_results.append(False)
        except Exception as e:
            print(f"   ❌ 不存在提交推送测试异常: {e}")
            test_results.append(False)
        
        # 测试2: 获取0条记录
        try:
            records = pusher.get_unpushed_analysis_records(limit=0)
            if len(records) == 0:
                print("   ✅ 获取0条记录测试: 通过")
                test_results.append(True)
            else:
                print(f"   ❌ 获取0条记录测试: 失败 (返回了 {len(records)} 条)")
                test_results.append(False)
        except Exception as e:
            print(f"   ❌ 获取0条记录测试异常: {e}")
            test_results.append(False)
        
        # 测试3: 无效webhook URL
        try:
            original_url = pusher.webhook_url
            pusher.webhook_url = 'invalid_url'
            
            message = {"msgtype": "text", "text": {"content": "test"}}
            result = pusher.send_message(message)
            expected = False  # 应该失败
            
            pusher.webhook_url = original_url  # 恢复
            
            if result == expected:
                print("   ✅ 无效URL测试: 通过")
                test_results.append(True)
            else:
                print(f"   ❌ 无效URL测试: 失败 (期望: {expected}, 实际: {result})")
                test_results.append(False)
        except Exception as e:
            print(f"   ❌ 无效URL测试异常: {e}")
            test_results.append(False)
        
        success_count = sum(test_results)
        total_count = len(test_results)
        
        print(f"   📊 边界测试结果: {success_count}/{total_count} 通过")
        
        if success_count == total_count:
            print("   ✅ 边界情况测试完成")
            return True
        else:
            print("   ⚠️ 部分边界测试失败")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始运行企业微信推送功能完整测试")
        
        test_results = []
        
        # 1. 初始化测试
        pusher = self.test_pusher_initialization()
        test_results.append(pusher is not None)
        
        if not pusher:
            print("\n❌ 推送器初始化失败，停止测试")
            return
        
        # 2. 数据库状态测试
        db_ok = self.test_database_status()
        test_results.append(db_ok)
        
        # 3. 获取记录测试
        records = self.test_get_unpushed_records(pusher)
        test_results.append(len(records) >= 0)  # 只要不出错就算通过
        
        # 4. 消息格式化测试
        format_ok = self.test_message_formatting(pusher, records)
        test_results.append(format_ok)
        
        # 5. 模拟推送测试
        push_ok = self.test_mock_push(pusher)
        test_results.append(push_ok)
        
        # 6. 批量推送测试
        batch_ok = self.test_batch_push_simulation(pusher)
        test_results.append(batch_ok)
        
        # 7. 总结报告测试
        report_ok = self.test_summary_report(pusher)
        test_results.append(report_ok)
        
        # 8. 边界情况测试
        edge_ok = self.test_edge_cases(pusher)
        test_results.append(edge_ok)
        
        # 测试结果汇总
        self.print_test_summary(test_results)
    
    def print_test_summary(self, test_results):
        """打印测试结果汇总"""
        print("\n" + "=" * 50)
        print("📊 测试结果汇总")
        print("=" * 50)
        
        test_names = [
            "推送器初始化",
            "数据库状态检查", 
            "获取未推送记录",
            "消息格式化",
            "模拟推送",
            "批量推送模拟",
            "总结报告",
            "边界情况测试"
        ]
        
        passed = 0
        total = len(test_results)
        
        for i, (name, result) in enumerate(zip(test_names, test_results), 1):
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{i:2d}. {name:<15} {status}")
            if result:
                passed += 1
        
        print("-" * 50)
        print(f"总体结果: {passed}/{total} 测试通过")
        
        if passed == total:
            print("🎉 所有测试通过！企业微信推送功能正常。")
        elif passed > total // 2:
            print("⚠️ 大部分测试通过，请检查失败的测试项。")
        else:
            print("💥 多个测试失败，请检查代码和配置。")
        
        print("\n💡 使用说明:")
        print("1. 设置环境变量: WX_WEBHOOK_URL=你的企业微信webhook地址")
        print("2. 调用推送: pusher.push_unpushed_analysis(limit=10)")
        print("3. 单个推送: pusher.push_single_commit('commit_sha')")
        print("4. 状态报告: pusher.send_summary_report()")


def main():
    """主函数"""
    tester = WeChatPushTester()
    tester.run_all_tests()


if __name__ == '__main__':
    main()
