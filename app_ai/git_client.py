import os
import json
import hashlib
import hmac
from django.http import JsonResponse, HttpResponseForbidden


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
        if not self.webhook_secret:
            return False
            
        if not signature_header.startswith('sha256='):
            return False
        
        # 提取签名
        received_signature = signature_header[7:]  # 移除 'sha256=' 前缀
        
        # 计算预期签名
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        # 安全比较签名
        return hmac.compare_digest(received_signature, expected_signature)
    
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
        # 检查webhook密钥配置
        if not self.webhook_secret:
            return False, JsonResponse({'error': 'Webhook secret not configured'}, status=500), None
        
        # 检查签名头
        signature_header = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
        if not signature_header:
            return False, HttpResponseForbidden('Missing signature header'), None
        
        # 验证签名
        if not self.verify_signature(request.body, signature_header):
            return False, HttpResponseForbidden('Invalid signature'), None
        
        # 解析JSON
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return False, JsonResponse({'error': 'Invalid JSON payload'}, status=400), None
        
        # 验证仓库权限
        repository = payload.get('repository', {})
        repo_owner = repository.get('owner', {}).get('login', '')
        repo_name = repository.get('name', '')
        
        if not self.is_repository_allowed(repo_owner, repo_name):
            return False, HttpResponseForbidden(f'Repository {repo_owner}/{repo_name} is not allowed for code review'), None
        
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
        """
        获取GitHub API请求头
        
        Returns:
            dict: 请求头信息
        """
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'CodeReview-Bot/1.0'
        }
        
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        return headers
    
    def get_data(self, data_type, **params):
        """
        统一的GET数据接口
        
        Args:
            data_type: 数据类型 ('repository_info', 'recent_commits', 'pull_requests', 
                      'repository_stats', 'search_code', 'commit_details', 'client_status')
            **params: 各种参数
            
        Returns:
            dict: 请求结果
        """
        import requests
        
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
        import requests
        
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
            return {
                'status': 'error',
                'error': f'GitHub API error: {response.status_code}',
                'message': response.text
            }
    
    def _get_pull_requests(self, state, limit):
        """获取拉取请求列表"""
        import requests
        
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
            return {
                'status': 'error',
                'error': f'GitHub API error: {response.status_code}',
                'message': response.text
            }
    
    def _get_repository_statistics(self):
        """获取仓库统计信息"""
        import requests
        
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
            return {
                'status': 'error',
                'error': f'GitHub API error: {response.status_code}',
                'message': response.text
            }
    
    def _search_code(self, query, limit):
        """在仓库中搜索代码"""
        import requests
        
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
            return {
                'status': 'error',
                'error': f'GitHub API error: {response.status_code}',
                'message': response.text
            }
    
    def _get_single_commit_detail(self, commit_sha, include_diff):
        """获取单个提交的详细信息"""
        import requests
        
        if not commit_sha:
            return {'error': 'Commit SHA is required', 'status': 'error'}
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits/{commit_sha}"
        response = requests.get(url, headers=self.get_headers())
        
        if response.status_code == 200:
            commit_data = response.json()
            
            commit_info = {
                'sha': commit_data['sha'],
                'short_sha': commit_data['sha'][:7],
                'message': commit_data['commit']['message'],
                'author': {
                    'name': commit_data['commit']['author']['name'],
                    'email': commit_data['commit']['author']['email'],
                    'date': commit_data['commit']['author']['date'],
                    'username': commit_data['author']['login'] if commit_data['author'] else 'Unknown'
                },
                'committer': {
                    'name': commit_data['commit']['committer']['name'],
                    'email': commit_data['commit']['committer']['email'],
                    'date': commit_data['commit']['committer']['date']
                },
                'url': commit_data['html_url'],
                'api_url': commit_data['url'],
                'parents': [parent['sha'] for parent in commit_data['parents']],
                'stats': commit_data.get('stats', {})
            }
            
            if include_diff and 'files' in commit_data:
                commit_info['files'] = []
                for file_data in commit_data['files']:
                    file_info = {
                        'filename': file_data['filename'],
                        'status': file_data['status'],
                        'additions': file_data['additions'],
                        'deletions': file_data['deletions'],
                        'changes': file_data['changes'],
                        'blob_url': file_data.get('blob_url', ''),
                        'raw_url': file_data.get('raw_url', ''),
                    }
                    
                    if 'patch' in file_data:
                        file_info['patch'] = file_data['patch']
                    
                    if file_data['status'] == 'renamed':
                        file_info['previous_filename'] = file_data.get('previous_filename', '')
                    
                    commit_info['files'].append(file_info)
            
            return {
                'status': 'success',
                'commit_detail': {'commit': commit_info}
            }
        else:
            return {
                'status': 'error',
                'error': f'GitHub API error: {response.status_code}',
                'message': response.text
            }
    
    def _get_commits_with_details(self, branch, limit, include_diff):
        """获取多个提交的详细信息"""
        import requests
        
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
                        detailed_commits.append({
                            'sha': commit['sha'],
                            'short_sha': commit['sha'][:7],
                            'message': commit['commit']['message'],
                            'author': {
                                'name': commit['commit']['author']['name'],
                                'email': commit['commit']['author']['email'],
                                'date': commit['commit']['author']['date'],
                                'username': commit['author']['login'] if commit['author'] else 'Unknown'
                            },
                            'url': commit['html_url'],
                            'error': detail.get('error', 'Failed to get detailed info')
                        })
                else:
                    detailed_commits.append({
                        'sha': commit['sha'],
                        'short_sha': commit['sha'][:7],
                        'message': commit['commit']['message'],
                        'author': {
                            'name': commit['commit']['author']['name'],
                            'email': commit['commit']['author']['email'],
                            'date': commit['commit']['author']['date'],
                            'username': commit['author']['login'] if commit['author'] else 'Unknown'
                        },
                        'committer': {
                            'name': commit['commit']['committer']['name'],
                            'email': commit['commit']['committer']['email'],
                            'date': commit['commit']['committer']['date']
                        },
                        'url': commit['html_url'],
                        'api_url': commit['url'],
                        'parents': [parent['sha'] for parent in commit['parents']]
                    })
            
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
            return {
                'status': 'error',
                'error': f'GitHub API error: {response.status_code}',
                'message': response.text
            }
    
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
