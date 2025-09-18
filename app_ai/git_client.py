import os
import json
import hashlib
import hmac
import requests
from django.http import JsonResponse, HttpResponseForbidden
from .schemas import get_param_rule


class ParamsValidator:
    """参数验证器"""
    
    @staticmethod
    def validate_request_params(request):
        """验证请求参数"""
        params = {}
        for key, value in request.GET.items():
            if key == 'type':
                continue
            
            value = value.strip()
            rule = get_param_rule(key)
            
            if rule:
                error = ParamsValidator._validate_param(key, value, rule)
                if error:
                    return None, error
                
                # 类型转换
                if rule['type'] == 'int':
                    params[key] = int(value)
                elif rule['type'] == 'bool':
                    params[key] = value.lower() == 'true'
                else:
                    params[key] = value
            else:
                params[key] = value
        
        return params, None
    
    @staticmethod
    def _validate_param(key, value, rule):
        """验证单个参数"""
        if rule['type'] == 'int':
            if not value.isdigit():
                return f'Parameter {key} must be a number'
            val = int(value)
            if 'min' in rule and val < rule['min']:
                return f'Parameter {key} must be >= {rule["min"]}'
            if 'max' in rule and val > rule['max']:
                return f'Parameter {key} must be <= {rule["max"]}'
        
        elif rule['type'] == 'bool':
            if value.lower() not in ['true', 'false']:
                return f'Parameter {key} must be true or false'
        
        elif rule['type'] == 'str':
            if rule.get('required') and not value:
                return f'Parameter {key} is required'
            if 'min_len' in rule and len(value) < rule['min_len']:
                return f'Parameter {key} must be at least {rule["min_len"]} characters'
            if 'max_len' in rule and len(value) > rule['max_len']:
                return f'Parameter {key} too long (max {rule["max_len"]} chars)'
        
        elif rule['type'] == 'choice':
            if value not in rule['choices']:
                return f'Parameter {key} must be: {", ".join(rule["choices"])}'
        
        return None


class GitHubWebhookClient:
    """
    GitHub Webhook客户端，专门处理POST请求的webhook验证和事件处理
    """
    
    def __init__(self):
        self.webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET', '')
        self.allowed_owner = os.getenv('REPO_OWNER', '').strip()
        self.allowed_name = os.getenv('REPO_NAME', '').strip()
    
    def verify_signature(self, payload_body, signature_header):
        """
        验证GitHub webhook签名
        
        Args:
            payload_body: 请求体内容
            signature_header: GitHub发送的签名头
            
        Returns:
            bool: 签名验证结果
        """
        print(f"🔐 开始签名验证...")
        print(f"   Secret配置: {'✅' if self.webhook_secret else '❌'}")
        print(f"   签名头: {signature_header}")
        print(f"   载荷长度: {len(payload_body)} bytes")
        
        if not self.webhook_secret:
            print("❌ 签名验证失败: 无webhook secret")
            return False
            
        if not signature_header.startswith('sha256='):
            print("❌ 签名验证失败: 签名头格式错误")
            return False
        
        # 提取签名
        received_signature = signature_header[7:]  # 移除 'sha256=' 前缀
        
        # 计算预期签名
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        print(f"   收到签名: {received_signature}")
        print(f"   期望签名: {expected_signature}")
        print(f"   载荷预览: {payload_body[:100]}...")
        
        # 安全比较签名
        is_valid = hmac.compare_digest(received_signature, expected_signature)
        print(f"   验证结果: {'✅ 通过' if is_valid else '❌ 失败'}")
        
        return is_valid
    
    def is_repository_allowed(self, repo_owner, repo_name):
        """
        检查仓库是否为指定的允许项目
        
        Args:
            repo_owner: 仓库所有者
            repo_name: 仓库名称
            
        Returns:
            bool: 是否允许访问
        """
        # 如果环境变量未配置，则拒绝所有请求
        if not self.allowed_owner or not self.allowed_name:
            return False
        
        # 检查仓库所有者和名称是否匹配
        return (repo_owner.lower() == self.allowed_owner.lower() and 
                repo_name.lower() == self.allowed_name.lower())
    
    def parse_push_payload(self, payload):
        """
        解析GitHub push事件的payload
        
        Args:
            payload: GitHub webhook payload
            
        Returns:
            dict: 解析后的推送信息
        """
        repository = payload.get('repository', {})
        commits = payload.get('commits', [])
        pusher = payload.get('pusher', {})
        ref = payload.get('ref', '')
        
        # 提取分支名
        branch = ref.replace('refs/heads/', '') if ref.startswith('refs/heads/') else ref
        
        return {
            'repository': {
                'full_name': repository.get('full_name', 'Unknown'),
                'name': repository.get('name', ''),
                'owner': repository.get('owner', {}).get('login', ''),
                'clone_url': repository.get('clone_url', ''),
                'ssh_url': repository.get('ssh_url', '')
            },
            'push_info': {
                'branch': branch,
                'pusher': pusher.get('name', 'Unknown'),
                'commits_count': len(commits),
                'before': payload.get('before', ''),
                'after': payload.get('after', ''),
                'compare_url': payload.get('compare', '')
            },
            'commits': [
                {
                    'id': commit.get('id', ''),
                    'message': commit.get('message', ''),
                    'author': {
                        'name': commit.get('author', {}).get('name', ''),
                        'email': commit.get('author', {}).get('email', ''),
                        'username': commit.get('author', {}).get('username', '')
                    },
                    'timestamp': commit.get('timestamp', ''),
                    'url': commit.get('url', ''),
                    'changes': {
                        'modified': commit.get('modified', []),
                        'added': commit.get('added', []),
                        'removed': commit.get('removed', [])
                    }
                }
                for commit in commits
            ]
        }
    
    def validate_webhook_request(self, request):
        """
        验证webhook请求的完整性和权限
        
        Args:
            request: Django HttpRequest对象
            
        Returns:
            tuple: (is_valid, error_response, payload)
        """
        # 临时调试：保存原始载荷用于分析
        print(f"🔍 收到webhook请求:")
        print(f"   请求体原始内容: {request.body}")
        print(f"   请求体字符串: {request.body.decode('utf-8')[:200]}...")
        
        # 检查webhook密钥配置
        if not self.webhook_secret:
            print("❌ Webhook验证失败: 未配置GITHUB_WEBHOOK_SECRET")
            return False, JsonResponse({'error': 'Webhook secret not configured'}, status=500), None
        
        # 检查签名头
        signature_header = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
        if not signature_header:
            print("❌ Webhook验证失败: 缺少X-Hub-Signature-256头")
            print(f"📋 可用的HTTP头: {[k for k in request.META.keys() if 'HTTP_' in k]}")
            return False, HttpResponseForbidden('Missing signature header'), None
        
        # 验证签名
        if not self.verify_signature(request.body, signature_header):
            print("❌ Webhook验证失败: 签名不匹配")
            print(f"📝 收到的签名: {signature_header}")
            print(f"📄 请求体长度: {len(request.body)} bytes")
            
            # 调试：计算我们期望的签名
            expected_sig = hmac.new(
                self.webhook_secret.encode('utf-8'),
                request.body,
                hashlib.sha256
            ).hexdigest()
            print(f"🔍 调试信息:")
            print(f"   期望签名: {expected_sig}")
            print(f"   实际载荷: {request.body.decode('utf-8')}")
            
            return False, HttpResponseForbidden('Invalid signature'), None
        
        # 解析JSON
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError as e:
            print(f"❌ Webhook验证失败: JSON解析错误 - {e}")
            return False, JsonResponse({'error': 'Invalid JSON payload'}, status=400), None
        
        # 验证仓库权限
        repository = payload.get('repository', {})
        repo_owner = repository.get('owner', {}).get('login', '')
        repo_name = repository.get('name', '')
        
        if not self.is_repository_allowed(repo_owner, repo_name):
            print(f"❌ Webhook验证失败: 仓库 {repo_owner}/{repo_name} 不在允许列表中")
            print(f"📋 允许的仓库: {self.allowed_owner}/{self.allowed_name}")
            return False, HttpResponseForbidden(f'Repository {repo_owner}/{repo_name} is not allowed for code review'), None
        
        print(f"✅ Webhook验证成功 (跳过签名): {repo_owner}/{repo_name}")
        return True, None, payload
    
    def handle_push_event(self, payload):
        """
        处理GitHub push事件
        
        Args:
            payload: GitHub webhook payload
            
        Returns:
            JsonResponse: 处理结果
        """
        push_data = self.parse_push_payload(payload)
        
        # 这里可以添加具体的业务逻辑
        # 比如：
        # 1. 触发代码审查
        # 2. 发送通知
        # 3. 保存到数据库
        # 4. 调用AI进行代码分析
        
        return JsonResponse({
            'message': 'Push event processed successfully',
            'repository': push_data['repository']['full_name'],
            'branch': push_data['push_info']['branch'],
            'pusher': push_data['push_info']['pusher'],
            'commits_count': push_data['push_info']['commits_count'],
            'status': 'success'
        })
    
    def handle_ping_event(self, payload):
        """
        处理GitHub ping事件（webhook测试）
        
        Args:
            payload: GitHub webhook payload
            
        Returns:
            JsonResponse: 响应结果
        """
        return JsonResponse({
            'message': 'pong',
            'webhook_id': payload.get('hook_id', ''),
            'repository': payload.get('repository', {}).get('full_name', ''),
            'status': 'success'
        })
    
    def get_webhook_stats(self):
        """
        获取webhook配置状态
        
        Returns:
            dict: 配置状态信息
        """
        return {
            'webhook_secret_configured': bool(self.webhook_secret),
            'allowed_repository': f"{self.allowed_owner}/{self.allowed_name}" if self.allowed_owner and self.allowed_name else None,
            'repository_access_restricted': bool(self.allowed_owner and self.allowed_name)
        }


class GitHubDataClient:
    """
    GitHub数据客户端，统一处理GET请求的数据获取和查询操作
    """
    
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN', '')
        self.repo_owner = os.getenv('REPO_OWNER', '').strip()
        self.repo_name = os.getenv('REPO_NAME', '').strip()
        self.base_url = 'https://api.github.com'
    
    def get_headers(self):
        """获取GitHub API请求头"""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'CodeReview-Bot/1.0'
        }
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        return headers
    
    def _format_basic_commit_info(self, commit_data):
        """格式化基本提交信息（公共方法，避免重复代码）"""
        return {
            'sha': commit_data['sha'],
            'short_sha': commit_data['sha'][:8],
            'full_sha': commit_data['sha'],
            'message': commit_data['commit']['message'],
            'subject': commit_data['commit']['message'].split('\n')[0],
            'author': {
                'name': commit_data['commit']['author']['name'],
                'email': commit_data['commit']['author']['email'],
                'username': commit_data['author']['login'] if commit_data['author'] else 'Unknown',
                'avatar_url': commit_data['author']['avatar_url'] if commit_data['author'] else None
            },
            'timestamp': {
                'authored_date': commit_data['commit']['author']['date'],
                'committed_date': commit_data['commit']['committer']['date']
            },
            'committer': {
                'name': commit_data['commit']['committer']['name'],
                'email': commit_data['commit']['committer']['email'],
                'date': commit_data['commit']['committer']['date']
            },
            'urls': {
                'html_url': commit_data['html_url'],
                'api_url': commit_data['url'],
                'compare_url': f"https://github.com/{self.repo_owner}/{self.repo_name}/commit/{commit_data['sha']}"
            },
            'parents': [parent['sha'] for parent in commit_data['parents']]
        }
    
    def _handle_api_error(self, response):
        """统一处理API错误响应"""
        return {
            'status': 'error',
            'error': f'GitHub API error: {response.status_code}',
            'message': response.text
        }
    
    def get_data(self, data_type, **params):
        """统一的GET数据接口"""
        
        # 基础配置检查
        if data_type != 'client_status' and (not self.repo_owner or not self.repo_name):
            return {'error': 'Repository not configured', 'status': 'error'}
        
        try:
            if data_type == 'repository_info':
                return self._get_repository_info()
            
            elif data_type == 'recent_commits':
                branch = params.get('branch', 'main')
                limit = params.get('limit', 10)
                return self._get_recent_commits(branch, limit)
            
            elif data_type == 'pull_requests':
                state = params.get('state', 'open')
                limit = params.get('limit', 10)
                return self._get_pull_requests(state, limit)
            
            elif data_type == 'repository_stats':
                return self._get_repository_statistics()
            
            elif data_type == 'search_code':
                query = params.get('query', '')
                limit = params.get('limit', 10)
                if not query:
                    return {'error': 'Search query is required', 'status': 'error'}
                return self._search_code(query, limit)
            
            elif data_type == 'commit_details':
                sha = params.get('sha', '')
                branch = params.get('branch', 'main')
                limit = params.get('limit', 5)
                include_diff = params.get('include_diff', True)
                
                if sha:
                    return self._get_single_commit_detail(sha, include_diff)
                else:
                    return self._get_commits_with_details(branch, limit, include_diff)
            
            elif data_type == 'client_status':
                return self._get_client_status()
            
            else:
                return {'error': f'Unknown data type: {data_type}', 'status': 'error'}
                
        except Exception as e:
            return {'error': f'Request failed: {str(e)}', 'status': 'error'}
    
    def _get_repository_info(self):
        """获取仓库基本信息"""
        return {
            'status': 'success',
            'repository_info': {
                'owner': self.repo_owner,
                'name': self.repo_name,
                'full_name': f"{self.repo_owner}/{self.repo_name}",
                'api_url': f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}",
                'web_url': f"https://github.com/{self.repo_owner}/{self.repo_name}"
            }
        }
    
    def _get_recent_commits(self, branch, limit):
        """获取最近的提交记录"""
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits"
        params = {'sha': branch, 'per_page': limit}
        
        response = requests.get(url, headers=self.get_headers(), params=params)
        
        if response.status_code == 200:
            commits = response.json()
            return {
                'status': 'success',
                'commits_data': {
                    'branch': branch,
                    'commits_count': len(commits),
                    'commits': [
                        {
                            'sha': commit['sha'],
                            'message': commit['commit']['message'],
                            'author': commit['commit']['author']['name'],
                            'date': commit['commit']['author']['date'],
                            'url': commit['html_url']
                        }
                        for commit in commits
                    ]
                }
            }
        else:
            return self._handle_api_error(response)
    
    def _get_pull_requests(self, state, limit):
        """获取拉取请求列表"""
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        params = {'state': state, 'per_page': limit}
        
        response = requests.get(url, headers=self.get_headers(), params=params)
        
        if response.status_code == 200:
            prs = response.json()
            return {
                'status': 'success',
                'pull_requests_data': {
                    'state': state,
                    'prs_count': len(prs),
                    'pull_requests': [
                        {
                            'number': pr['number'],
                            'title': pr['title'],
                            'state': pr['state'],
                            'author': pr['user']['login'],
                            'created_at': pr['created_at'],
                            'url': pr['html_url']
                        }
                        for pr in prs
                    ]
                }
            }
        else:
            return self._handle_api_error(response)
    
    def _get_repository_statistics(self):
        """获取仓库统计信息"""
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
        response = requests.get(url, headers=self.get_headers())
        
        if response.status_code == 200:
            repo_data = response.json()
            return {
                'status': 'success',
                'statistics': {
                    'repository': {
                        'name': repo_data['name'],
                        'full_name': repo_data['full_name'],
                        'description': repo_data['description'],
                        'language': repo_data['language'],
                        'stars': repo_data['stargazers_count'],
                        'forks': repo_data['forks_count'],
                        'issues': repo_data['open_issues_count'],
                        'created_at': repo_data['created_at'],
                        'updated_at': repo_data['updated_at']
                    }
                }
            }
        else:
            return self._handle_api_error(response)
    
    def _search_code(self, query, limit):
        """在仓库中搜索代码"""
        
        url = f"{self.base_url}/search/code"
        params = {
            'q': f'{query} repo:{self.repo_owner}/{self.repo_name}',
            'per_page': limit
        }
        
        response = requests.get(url, headers=self.get_headers(), params=params)
        
        if response.status_code == 200:
            search_data = response.json()
            return {
                'status': 'success',
                'search_results': {
                    'query': query,
                    'total_count': search_data['total_count'],
                    'results': [
                        {
                            'name': item['name'],
                            'path': item['path'],
                            'url': item['html_url'],
                            'score': item['score']
                        }
                        for item in search_data['items']
                    ]
                }
            }
        else:
            return self._handle_api_error(response)
    
    def _get_single_commit_detail(self, commit_sha, include_diff):
        """获取单个提交的详细信息"""
        
        if not commit_sha:
            return {'error': 'Commit SHA is required', 'status': 'error'}
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits/{commit_sha}"
        response = requests.get(url, headers=self.get_headers())
        
        if response.status_code == 200:
            commit_data = response.json()
            
            # 使用公共方法格式化基本信息
            commit_info = self._format_basic_commit_info(commit_data)
            
            # 添加详细信息特有的字段
            commit_info.update({
                'message_lines': commit_data['commit']['message'].split('\n'),
                'author': {
                    **commit_info['author'],
                    'profile_url': commit_data['author']['html_url'] if commit_data['author'] else None
                },
                'timestamp': {
                    **commit_info['timestamp'],
                    'authored_iso': commit_data['commit']['author']['date'],
                    'committed_iso': commit_data['commit']['committer']['date']
                },
                'stats': {
                    'total': commit_data.get('stats', {}).get('total', 0),
                    'additions': commit_data.get('stats', {}).get('additions', 0),
                    'deletions': commit_data.get('stats', {}).get('deletions', 0)
                }
            })
            
            # 文件变更详情 - 包含具体代码内容
            if include_diff and 'files' in commit_data:
                commit_info['files'] = []
                commit_info['files_summary'] = {
                    'total_files': len(commit_data['files']),
                    'total_additions': sum(f.get('additions', 0) for f in commit_data['files']),
                    'total_deletions': sum(f.get('deletions', 0) for f in commit_data['files']),
                    'file_types': list(set(f['filename'].split('.')[-1] for f in commit_data['files'] if '.' in f['filename']))
                }
                
                for file_data in commit_data['files']:
                    file_info = {
                        # 文件基本信息
                        'filename': file_data['filename'],
                        'status': file_data['status'],  # added, modified, deleted, renamed
                        'file_type': file_data['filename'].split('.')[-1] if '.' in file_data['filename'] else 'unknown',
                        
                        # 变更统计
                        'changes': {
                            'additions': file_data['additions'],
                            'deletions': file_data['deletions'],
                            'total_changes': file_data['changes']
                        },
                        
                        # 文件链接
                        'urls': {
                            'blob_url': file_data.get('blob_url', ''),
                            'raw_url': file_data.get('raw_url', ''),
                            'contents_url': file_data.get('contents_url', '')
                        }
                    }
                    
                    # 代码差异内容 - 这是具体的代码变更
                    if 'patch' in file_data:
                        file_info['code_changes'] = {
                            'raw_patch': file_data['patch'],
                            'patch_lines': file_data['patch'].split('\n'),
                            'has_content': True
                        }
                        
                        # 解析代码变更，分离添加和删除的行
                        added_lines = []
                        deleted_lines = []
                        context_lines = []
                        
                        for line in file_data['patch'].split('\n'):
                            if line.startswith('+') and not line.startswith('+++'):
                                added_lines.append(line[1:])  # 移除+号
                            elif line.startswith('-') and not line.startswith('---'):
                                deleted_lines.append(line[1:])  # 移除-号
                            elif line.startswith(' '):
                                context_lines.append(line[1:])  # 移除空格
                        
                        file_info['code_changes']['parsed'] = {
                            'added_lines': added_lines,
                            'deleted_lines': deleted_lines,
                            'context_lines': context_lines,
                            'added_count': len(added_lines),
                            'deleted_count': len(deleted_lines)
                        }
                    else:
                        file_info['code_changes'] = {
                            'raw_patch': None,
                            'has_content': False,
                            'note': 'No patch content available (binary file or too large)'
                        }
                    
                    # 重命名文件的原始名称
                    if file_data['status'] == 'renamed':
                        file_info['previous_filename'] = file_data.get('previous_filename', '')
                    
                    commit_info['files'].append(file_info)
                
                # 生成整体的raw_patch（所有文件的patch合并）
                all_patches = []
                for file_data in commit_data['files']:
                    if 'patch' in file_data:
                        all_patches.append(f"diff --git a/{file_data['filename']} b/{file_data['filename']}")
                        all_patches.append(file_data['patch'])
                
                commit_info['raw_patch'] = '\n'.join(all_patches) if all_patches else ''
            else:
                # 如果不包含diff，设置空的raw_patch
                commit_info['raw_patch'] = ''
            
            return {
                'status': 'success',
                'commit_detail': {'commit': commit_info}
            }
        else:
            return self._handle_api_error(response)
    
    def _get_commits_with_details(self, branch, limit, include_diff):
        """获取多个提交的详细信息"""
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits"
        params = {'sha': branch, 'per_page': limit}
        
        response = requests.get(url, headers=self.get_headers(), params=params)
        
        if response.status_code == 200:
            commits = response.json()
            detailed_commits = []
            
            for commit in commits:
                if include_diff:
                    detail = self._get_single_commit_detail(commit['sha'], include_diff=True)
                    if detail['status'] == 'success':
                        detailed_commits.append(detail['commit_detail']['commit'])
                    else:
                        # 失败时使用基本信息
                        basic_info = self._format_basic_commit_info(commit)
                        basic_info['error'] = detail.get('error', 'Failed to get detailed info')
                        detailed_commits.append(basic_info)
                else:
                    # 简化版本的提交信息（不包含文件差异）
                    detailed_commits.append(self._format_basic_commit_info(commit))
            
            return {
                'status': 'success',
                'commits_detail': {
                    'branch': branch,
                    'commits_count': len(detailed_commits),
                    'include_diff': include_diff,
                    'commits': detailed_commits
                }
            }
        else:
            return self._handle_api_error(response)
    
    def _get_client_status(self):
        """获取客户端配置状态"""
        return {
            'status': 'success',
            'webhook_client': {
                'webhook_secret_configured': bool(os.getenv('GITHUB_WEBHOOK_SECRET', '')),
                'allowed_repository': f"{self.repo_owner}/{self.repo_name}" if self.repo_owner and self.repo_name else None,
                'repository_access_restricted': bool(self.repo_owner and self.repo_name)
            },
            'data_client': {
                'github_token_configured': bool(self.github_token),
                'repository_configured': bool(self.repo_owner and self.repo_name),
                'repository': f"{self.repo_owner}/{self.repo_name}" if self.repo_owner and self.repo_name else None,
                'api_base_url': self.base_url
            },
            'system_status': 'active'
        }
