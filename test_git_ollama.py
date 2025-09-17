#!/usr/bin/env python3
"""
Git信息获取 + Ollama处理 综合测试脚本
测试GitHub数据获取和Ollama AI分析功能
"""

import os
import requests
import json
import time
from datetime import datetime
from urllib.parse import urlencode


class GitOllamaTest:
    """Git + Ollama 综合测试类"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.api_endpoint = f"{base_url}/ai/github-data/"
        
    def print_section(self, title):
        """打印分节标题"""
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")
    
    def print_result(self, result, title="结果"):
        """格式化打印结果"""
        print(f"\n{title}:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    def make_request(self, params):
        """发送GET请求"""
        url = f"{self.api_endpoint}?{urlencode(params)}"
        print(f"🔗 请求URL: {url}")
        
        try:
            response = requests.get(url, timeout=120)  # 增加到2分钟
            print(f"📊 状态码: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    'error': f'HTTP {response.status_code}',
                    'message': response.text
                }
        except requests.exceptions.ConnectionError:
            return {
                'error': 'Connection failed',
                'message': 'Django服务器未运行，请执行: python manage.py runserver'
            }
        except requests.exceptions.Timeout:
            return {
                'error': 'Request timeout',
                'message': '请求超时，可能是Ollama处理时间较长'
            }
        except Exception as e:
            return {
                'error': 'Request exception',
                'message': str(e)
            }
    
    def test_ollama_connection(self):
        """测试Ollama连接状态"""
        self.print_section("1. Ollama连接状态检查")
        
        params = {'type': 'ollama_status'}
        result = self.make_request(params)
        self.print_result(result, "Ollama连接状态")
        
        if result.get('status') == 'connected':
            print("✅ Ollama服务连接正常")
            models = result.get('available_models', [])
            print(f"📋 可用模型: {', '.join(models) if models else '无'}")
            return True
        else:
            print("❌ Ollama服务连接失败")
            if 'troubleshooting' in result:
                print("\n🔧 故障排除:")
                for tip in result['troubleshooting']:
                    print(f"   • {tip}")
            return False
    
    def test_ollama_models(self):
        """测试获取Ollama模型列表"""
        self.print_section("2. Ollama模型列表")
        
        params = {'type': 'ollama_models'}
        result = self.make_request(params)
        self.print_result(result, "模型列表")
        
        if result.get('status') == 'success':
            models = result.get('models', [])
            print(f"✅ 找到 {len(models)} 个模型")
            for model in models:
                name = model.get('name', 'Unknown')
                size = model.get('size', 0)
                size_mb = size / (1024 * 1024) if size > 0 else 0
                print(f"   📦 {name} ({size_mb:.1f} MB)")
            return models
        else:
            print("❌ 获取模型列表失败")
            return []
    
    def test_github_data(self):
        """测试GitHub数据获取"""
        self.print_section("3. GitHub数据获取测试")
        
        # 测试仓库信息
        print("\n📂 获取仓库信息...")
        params = {'type': 'repository_info'}
        result = self.make_request(params)
        
        if result.get('status') == 'success':
            repo_info = result.get('repository_info', {})
            print(f"✅ 仓库: {repo_info.get('full_name', 'Unknown')}")
            print(f"🔗 URL: {repo_info.get('web_url', 'Unknown')}")
        else:
            print("❌ 获取仓库信息失败")
            print(f"错误: {result.get('error', 'Unknown error')}")
            return None
        
        # 测试最近提交
        print("\n📝 获取最近提交...")
        params = {'type': 'recent_commits', 'limit': 3}
        result = self.make_request(params)
        
        if result.get('status') == 'success':
            commits_data = result.get('commits_data', {})
            commits = commits_data.get('commits', [])
            print(f"✅ 获取到 {len(commits)} 个提交")
            
            if commits:
                latest_commit = commits[0]
                print(f"🔖 最新提交: {latest_commit.get('sha', '')[:8]}")
                print(f"👤 作者: {latest_commit.get('author', 'Unknown')}")
                print(f"💬 消息: {latest_commit.get('message', '')[:50]}...")
                return latest_commit.get('sha', '')
        else:
            print("❌ 获取提交记录失败")
            print(f"错误: {result.get('error', 'Unknown error')}")
            return None
    
    def test_code_review(self):
        """测试代码审查功能"""
        self.print_section("4. 代码审查测试")
        
        # 测试代码示例
        test_code = '''
def process_user_data(user_input):
    # 潜在的安全问题：没有输入验证
    data = eval(user_input)  # 危险！
    
    # 潜在的性能问题：重复计算
    result = []
    for i in range(len(data)):
        for j in range(len(data)):
            if data[i] > data[j]:
                result.append(data[i])
    
    return result
'''
        
        print("📝 测试代码:")
        print(test_code)
        
        print("\n🔍 正在进行AI代码审查...")
        params = {
            'type': 'code_review',
            'code': test_code,
            'model': 'llama2'
        }
        
        start_time = time.time()
        result = self.make_request(params)
        end_time = time.time()
        
        if result.get('status') == 'success':
            print(f"✅ 代码审查完成 (耗时: {end_time - start_time:.2f}s)")
            review_response = result.get('response', '')
            print(f"\n🤖 AI审查结果:")
            print(f"{review_response[:500]}..." if len(review_response) > 500 else review_response)
            
            # 显示统计信息
            stats = {
                'code_length': result.get('code_length', 0),
                'model_used': result.get('model_used', 'Unknown'),
                'eval_count': result.get('eval_count', 0),
                'total_duration': result.get('total_duration', 0)
            }
            print(f"\n📊 审查统计:")
            for key, value in stats.items():
                if key == 'total_duration' and value > 0:
                    print(f"   • {key}: {value / 1000000:.2f} ms")
                else:
                    print(f"   • {key}: {value}")
            
            return True
        else:
            print("❌ 代码审查失败")
            print(f"错误: {result.get('error', 'Unknown error')}")
            return False
    
    def test_commit_analysis(self, commit_sha=None):
        """测试提交分析功能"""
        self.print_section("5. 提交分析测试")
        
        if not commit_sha:
            print("⚠️  没有提供commit SHA，跳过提交分析测试")
            return False
        
        print(f"🔍 正在分析提交: {commit_sha[:8]}...")
        
        params = {
            'type': 'commit_analysis',
            'sha': commit_sha,
            'model': 'llama2'
        }
        
        start_time = time.time()
        result = self.make_request(params)
        end_time = time.time()
        
        if result.get('status') == 'success':
            print(f"✅ 提交分析完成 (耗时: {end_time - start_time:.2f}s)")
            analysis_response = result.get('response', '')
            print(f"\n🤖 AI分析结果:")
            print(f"{analysis_response[:500]}..." if len(analysis_response) > 500 else analysis_response)
            
            # 显示分析统计
            stats = {
                'commit_sha': result.get('commit_sha', 'Unknown'),
                'files_count': result.get('files_count', 0),
                'model_used': result.get('model_used', 'Unknown'),
                'analysis_type': result.get('analysis_type', 'Unknown')
            }
            print(f"\n📊 分析统计:")
            for key, value in stats.items():
                print(f"   • {key}: {value}")
            
            return True
        else:
            print("❌ 提交分析失败")
            print(f"错误: {result.get('error', 'Unknown error')}")
            return False
    
    def test_comprehensive_workflow(self):
        """测试完整工作流程"""
        self.print_section("6. 综合工作流程测试")
        
        print("🚀 开始完整的Git + Ollama工作流程测试...")
        
        # 1. 获取最近提交
        print("\n📝 步骤1: 获取最近提交详情...")
        params = {'type': 'commit_details', 'limit': 1, 'include_diff': 'true'}
        result = self.make_request(params)
        
        if result.get('status') != 'success':
            print("❌ 无法获取提交详情，终止工作流程测试")
            return False
        
        commits_detail = result.get('commits_detail', {})
        commits = commits_detail.get('commits', [])
        
        if not commits:
            print("❌ 没有找到提交记录")
            return False
        
        commit = commits[0]
        commit_sha = commit.get('sha', '')
        commit_message = commit.get('message', '')
        files = commit.get('files', [])
        
        print(f"✅ 找到提交: {commit_sha[:8]}")
        print(f"💬 提交消息: {commit_message[:50]}...")
        print(f"📁 修改文件数: {len(files)}")
        
        # 2. 分析提交内容
        if files:
            print(f"\n🔍 步骤2: 分析提交内容...")
            analysis_result = self.test_commit_analysis(commit_sha)
            
            if analysis_result:
                print("✅ 提交分析完成")
            else:
                print("❌ 提交分析失败")
        
        # 3. 如果有代码变更，进行代码审查
        code_files = [f for f in files if f.get('patch') and any(f.get('filename', '').endswith(ext) for ext in ['.py', '.js', '.java', '.cpp', '.c'])]
        
        if code_files:
            print(f"\n📋 步骤3: 发现 {len(code_files)} 个代码文件，进行代码审查...")
            
            for file_info in code_files[:2]:  # 最多审查前2个文件
                filename = file_info.get('filename', 'Unknown')
                patch = file_info.get('patch', '')
                
                if patch:
                    print(f"\n🔍 审查文件: {filename}")
                    params = {
                        'type': 'code_review',
                        'code': patch[:1000],  # 限制代码长度
                        'model': 'llama2'
                    }
                    
                    review_result = self.make_request(params)
                    
                    if review_result.get('status') == 'success':
                        print(f"✅ {filename} 审查完成")
                        response = review_result.get('response', '')
                        print(f"💡 建议: {response[:100]}...")
                    else:
                        print(f"❌ {filename} 审查失败")
        else:
            print("\n📋 步骤3: 没有发现代码文件变更")
        
        print("\n🎉 综合工作流程测试完成!")
        return True
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 Git + Ollama 综合测试开始")
        print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔗 API端点: {self.api_endpoint}")
        
        test_results = {
            'ollama_connection': False,
            'ollama_models': False,
            'github_data': False,
            'code_review': False,
            'commit_analysis': False,
            'comprehensive_workflow': False
        }
        
        # 1. 测试Ollama连接
        test_results['ollama_connection'] = self.test_ollama_connection()
        
        # 2. 测试模型列表
        if test_results['ollama_connection']:
            models = self.test_ollama_models()
            test_results['ollama_models'] = len(models) > 0
        
        # 3. 测试GitHub数据
        commit_sha = self.test_github_data()
        test_results['github_data'] = commit_sha is not None
        
        # 4. 测试代码审查
        if test_results['ollama_connection']:
            test_results['code_review'] = self.test_code_review()
        
        # 5. 测试提交分析
        if test_results['ollama_connection'] and commit_sha:
            test_results['commit_analysis'] = self.test_commit_analysis(commit_sha)
        
        # 6. 综合工作流程测试
        if test_results['ollama_connection'] and test_results['github_data']:
            test_results['comprehensive_workflow'] = self.test_comprehensive_workflow()
        
        # 测试结果总结
        self.print_section("测试结果总结")
        
        passed_tests = sum(test_results.values())
        total_tests = len(test_results)
        
        print(f"📊 测试统计: {passed_tests}/{total_tests} 通过")
        
        for test_name, result in test_results.items():
            status = "✅ 通过" if result else "❌ 失败"
            print(f"   • {test_name}: {status}")
        
        if passed_tests == total_tests:
            print("\n🎉 所有测试通过！Git + Ollama 集成工作正常。")
        else:
            print(f"\n⚠️  {total_tests - passed_tests} 个测试失败，请检查配置。")
            
            # 提供故障排除建议
            print("\n🔧 故障排除建议:")
            if not test_results['ollama_connection']:
                print("   • 检查Ollama Docker容器是否运行: docker-compose ps")
                print("   • 启动Ollama服务: docker-compose up -d ollama")
            if not test_results['github_data']:
                print("   • 检查GitHub配置: REPO_OWNER, REPO_NAME, GITHUB_TOKEN")
                print("   • 确认环境变量已正确设置")
            if not test_results['ollama_models']:
                print("   • 拉取AI模型: docker exec ollama ollama pull llama2")


def main():
    """主函数"""
    # 检查环境变量
    required_env = ['REPO_OWNER', 'REPO_NAME', 'GITHUB_TOKEN']
    missing_env = [env for env in required_env if not os.getenv(env)]
    
    if missing_env:
        print(f"⚠️  缺少环境变量: {', '.join(missing_env)}")
        print("请设置这些环境变量后重新运行测试")
        return
    
    # 创建测试实例并运行
    tester = GitOllamaTest()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
