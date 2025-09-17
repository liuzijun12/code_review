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
    GitHub数据客户端，专门处理GET请求的数据获取和查询操作
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
    
    def get_repository_info(self):
        """
        获取仓库基本信息
        
        Returns:
            dict: 仓库信息
        """
        if not self.repo_owner or not self.repo_name:
            return {'error': 'Repository not configured'}
        
        return {
            'owner': self.repo_owner,
            'name': self.repo_name,
            'full_name': f"{self.repo_owner}/{self.repo_name}",
            'api_url': f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}",
            'web_url': f"https://github.com/{self.repo_owner}/{self.repo_name}"
        }
    
    def get_recent_commits(self, branch='main', limit=10):
        """
        获取最近的提交记录
        
        Args:
            branch: 分支名称，默认main
            limit: 返回数量限制
            
        Returns:
            dict: 提交记录信息
        """
        import requests
        
        if not self.repo_owner or not self.repo_name:
            return {'error': 'Repository not configured'}
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits"
        params = {
            'sha': branch,
            'per_page': limit
        }
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 200:
                commits = response.json()
                return {
                    'status': 'success',
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
            else:
                return {
                    'error': f'GitHub API error: {response.status_code}',
                    'message': response.text
                }
                
        except Exception as e:
            return {'error': f'Request failed: {str(e)}'}
    
    def get_pull_requests(self, state='open', limit=10):
        """
        获取拉取请求列表
        
        Args:
            state: PR状态 (open, closed, all)
            limit: 返回数量限制
            
        Returns:
            dict: PR列表信息
        """
        import requests
        
        if not self.repo_owner or not self.repo_name:
            return {'error': 'Repository not configured'}
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        params = {
            'state': state,
            'per_page': limit
        }
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 200:
                prs = response.json()
                return {
                    'status': 'success',
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
            else:
                return {
                    'error': f'GitHub API error: {response.status_code}',
                    'message': response.text
                }
                
        except Exception as e:
            return {'error': f'Request failed: {str(e)}'}
    
    def get_repository_statistics(self):
        """
        获取仓库统计信息
        
        Returns:
            dict: 统计信息
        """
        import requests
        
        if not self.repo_owner or not self.repo_name:
            return {'error': 'Repository not configured'}
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
        
        try:
            response = requests.get(url, headers=self.get_headers())
            
            if response.status_code == 200:
                repo_data = response.json()
                return {
                    'status': 'success',
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
            else:
                return {
                    'error': f'GitHub API error: {response.status_code}',
                    'message': response.text
                }
                
        except Exception as e:
            return {'error': f'Request failed: {str(e)}'}
    
    def search_code(self, query, limit=10):
        """
        在仓库中搜索代码
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            dict: 搜索结果
        """
        import requests
        
        if not self.repo_owner or not self.repo_name:
            return {'error': 'Repository not configured'}
        
        url = f"{self.base_url}/search/code"
        params = {
            'q': f'{query} repo:{self.repo_owner}/{self.repo_name}',
            'per_page': limit
        }
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 200:
                search_data = response.json()
                return {
                    'status': 'success',
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
            else:
                return {
                    'error': f'GitHub API error: {response.status_code}',
                    'message': response.text
                }
                
        except Exception as e:
            return {'error': f'Request failed: {str(e)}'}
    
    def get_single_commit_detail(self, commit_sha, include_diff=True):
        """
        获取单个提交的详细信息，包括代码差异
        
        Args:
            commit_sha: 提交的SHA值
            include_diff: 是否包含代码差异
            
        Returns:
            dict: 详细的提交信息
        """
        import requests
        
        if not self.repo_owner or not self.repo_name:
            return {'error': 'Repository not configured'}
        
        if not commit_sha:
            return {'error': 'Commit SHA is required'}
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits/{commit_sha}"
        
        try:
            response = requests.get(url, headers=self.get_headers())
            
            if response.status_code == 200:
                commit_data = response.json()
                
                # 基本提交信息
                commit_info = {
                    'sha': commit_data['sha'],
                    'short_sha': commit_data['sha'][:7],  # 短SHA
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
                    'stats': commit_data.get('stats', {}),  # 统计信息（添加、删除、修改的行数）
                }
                
                # 如果需要包含代码差异
                if include_diff and 'files' in commit_data:
                    commit_info['files'] = []
                    for file_data in commit_data['files']:
                        file_info = {
                            'filename': file_data['filename'],
                            'status': file_data['status'],  # added, modified, removed, renamed
                            'additions': file_data['additions'],
                            'deletions': file_data['deletions'],
                            'changes': file_data['changes'],
                            'blob_url': file_data.get('blob_url', ''),
                            'raw_url': file_data.get('raw_url', ''),
                        }
                        
                        # 包含代码差异内容
                        if 'patch' in file_data:
                            file_info['patch'] = file_data['patch']  # 具体的代码差异
                        
                        # 如果是重命名文件
                        if file_data['status'] == 'renamed':
                            file_info['previous_filename'] = file_data.get('previous_filename', '')
                        
                        commit_info['files'].append(file_info)
                
                return {
                    'status': 'success',
                    'commit': commit_info
                }
            else:
                return {
                    'error': f'GitHub API error: {response.status_code}',
                    'message': response.text
                }
                
        except Exception as e:
            return {'error': f'Request failed: {str(e)}'}
    
    def get_commits_with_details(self, branch='main', limit=5, include_diff=False):
        """
        获取多个提交的详细信息
        
        Args:
            branch: 分支名称
            limit: 获取数量
            include_diff: 是否包含代码差异（注意：包含差异会增加API调用次数）
            
        Returns:
            dict: 多个提交的详细信息
        """
        import requests
        
        if not self.repo_owner or not self.repo_name:
            return {'error': 'Repository not configured'}
        
        # 首先获取提交列表
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits"
        params = {
            'sha': branch,
            'per_page': limit
        }
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 200:
                commits = response.json()
                detailed_commits = []
                
                for commit in commits:
                    if include_diff:
                        # 获取每个提交的详细信息（包含代码差异）
                        detail = self.get_single_commit_detail(commit['sha'], include_diff=True)
                        if 'error' not in detail:
                            detailed_commits.append(detail['commit'])
                        else:
                            # 如果获取详细信息失败，使用基本信息
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
                        # 只使用基本信息
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
                    'branch': branch,
                    'commits_count': len(detailed_commits),
                    'include_diff': include_diff,
                    'commits': detailed_commits
                }
            else:
                return {
                    'error': f'GitHub API error: {response.status_code}',
                    'message': response.text
                }
                
        except Exception as e:
            return {'error': f'Request failed: {str(e)}'}

    def get_client_status(self):
        """
        获取客户端配置状态
        
        Returns:
            dict: 客户端状态信息
        """
        return {
            'github_token_configured': bool(self.github_token),
            'repository_configured': bool(self.repo_owner and self.repo_name),
            'repository': f"{self.repo_owner}/{self.repo_name}" if self.repo_owner and self.repo_name else None,
            'api_base_url': self.base_url
        }
