import os
import json
import hashlib
import hmac
import logging
import requests
from django.http import JsonResponse, HttpResponseForbidden

# 创建logger实例
logger = logging.getLogger(__name__)


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
        is_valid = hmac.compare_digest(received_signature, expected_signature)
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
        logger.info("开始验证GitHub webhook请求")
        
        # 检查webhook密钥配置
        if not self.webhook_secret:
            logger.error("Webhook密钥未配置")
            return False, JsonResponse({'error': 'Webhook secret not configured'}, status=500), None
        
        # 检查签名头
        signature_header = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
        a = "/n".join([f"{key}:{value}" for key, value in request.META.items()])
        if not signature_header:
            logger.warning("Webhook请求缺少签名头")
            return False, HttpResponseForbidden('Missing signature header'), None
        
        # 验证签名
        if not self.verify_signature(request.body, signature_header):
            logger.error("Webhook签名验证失败")
            return False, HttpResponseForbidden('Invalid signature'), None
        
        # 解析JSON
        try:
            if len(request.body) == 0:
                logger.error("Webhook请求体为空")
                return False, JsonResponse({'error': 'Empty request body'}, status=400), None
            
            body_str = request.body.decode('utf-8')
            
            # GitHub webhook可能发送两种格式：
            # 1. 直接JSON格式
            # 2. form-encoded格式: payload=<URL_encoded_JSON>
            if body_str.startswith('payload='):
                from urllib.parse import unquote_plus
                payload_str = body_str[8:]  # 移除 'payload=' 前缀
                payload_str = unquote_plus(payload_str)  # URL解码
                payload = json.loads(payload_str)
            else:
                payload = json.loads(body_str)
                
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.error(f"Webhook请求解析失败: {str(e)}")
            return False, JsonResponse({'error': 'Invalid JSON payload'}, status=400), None
        
        # 验证仓库权限
        repository = payload.get('repository', {})
        repo_owner = repository.get('owner', {}).get('login', '')
        repo_name = repository.get('name', '')
        
        if not self.is_repository_allowed(repo_owner, repo_name):
            logger.warning(f"仓库 {repo_owner}/{repo_name} 不在允许列表中，允许的仓库: {self.allowed_owner}/{self.allowed_name}")
            return False, HttpResponseForbidden(f'Repository {repo_owner}/{repo_name} is not allowed for code review'), None
        
        logger.info(f"Webhook验证成功，仓库: {repo_owner}/{repo_name}")
        return True, None, payload
    
    def extract_latest_commit_sha(self, payload):
        """
        从 GitHub push event payload 中提取最新提交的 SHA
        
        Args:
            payload: GitHub webhook push event payload
            
        Returns:
            tuple: (sha, source) - SHA值和来源说明，如果未找到则返回 (None, None)
        """
        logger.info("从 payload 中提取最新提交 SHA")
        
        # 优先使用 head_commit.id（最可靠）
        if payload.get('head_commit') and payload['head_commit'].get('id'):
            sha = payload['head_commit']['id']
            logger.info(f"从 head_commit 获取最新 SHA: {sha[:8]}...{sha[-8:]}")
            return sha, 'head_commit.id'
        
        # 备选：使用 after 字段
        elif payload.get('after') and payload['after'] != '0000000000000000000000000000000000000000':
            sha = payload['after']
            logger.info(f"从 after 字段获取最新 SHA: {sha[:8]}...{sha[-8:]}")
            return sha, 'after'
        
        # 最后备选：使用 commits 列表的第一个
        elif payload.get('commits') and len(payload['commits']) > 0:
            sha = payload['commits'][0].get('id')
            if sha:
                logger.info(f"从 commits[0] 获取最新 SHA: {sha[:8]}...{sha[-8:]}")
                return sha, 'commits[0].id'
            else:
                logger.warning("commits[0] 中没有 id 字段")
                return None, None
        
        # 所有方法都失败
        logger.error("无法从 payload 中提取最新提交 SHA")
        return None, None
    
    def validate_commit_sha(self, sha):
        """
        验证提交 SHA 的格式
        
        Args:
            sha: 提交 SHA 字符串
            
        Returns:
            bool: SHA 格式是否有效
        """
        if not sha or not isinstance(sha, str):
            return False
        
        # GitHub SHA 应该是 40 位十六进制字符串
        if len(sha) != 40:
            return False
        
        # 检查是否为有效的十六进制
        try:
            int(sha, 16)
            return True
        except ValueError:
            return False
    
    # 注意：handle_push_event, handle_ping_event, get_webhook_stats 方法已删除
    # 现在 webhook 处理直接在 views.py 中实现


class GitHubDataClient:
    """
    GitHub数据客户端，专门用于异步任务的数据获取
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
    
    def _handle_api_error(self, response):
        """统一处理API错误响应"""
        logger.error(f"GitHub API调用失败: HTTP {response.status_code}")
        return {
            'status': 'error',
            'error': f'GitHub API error: {response.status_code}',
            'message': response.text[:200]
        }
    
    def get_data(self, data_type, **params):
        """统一的GET数据接口 - 只支持单个提交处理"""
        logger.info(f"请求GitHub数据，类型: {data_type}, 参数: {params}")
        
        if not self.repo_owner or not self.repo_name:
            logger.error("仓库配置未完成")
            return {'error': 'Repository not configured', 'status': 'error'}
        
        try:
            if data_type == 'commit_details':
                sha = params.get('sha', '')
                include_diff = params.get('include_diff', True)
                
                if not sha:
                    return {'error': 'SHA is required for single commit processing', 'status': 'error'}
                
                return self._get_single_commit_detail(sha, include_diff)
            
            else:
                return {'error': f'Unsupported data type: {data_type}. Only commit_details is supported.', 'status': 'error'}
                
        except Exception as e:
            logger.error(f"GitHub数据请求失败: {str(e)}")
            return {'error': f'Request failed: {str(e)}', 'status': 'error'}
    
    
    # 批量处理方法已删除，现在只支持单个提交处理
    
    
    def _get_single_commit_detail(self, commit_sha, include_diff):
        """获取单个提交的详细信息 - 直接用于Ollama分析"""
        
        if not commit_sha:
            logger.error("获取提交详情失败: 缺少commit SHA")
            return {'error': 'Commit SHA is required', 'status': 'error'}
        
        logger.info(f"获取单个提交详情用于Ollama分析: SHA={commit_sha[:8]}")
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits/{commit_sha}"
        response = requests.get(url, headers=self.get_headers())
        
        if response.status_code == 200:
            commit_data = response.json()
            
            # 提取修改的文件列表
            modified_files = []
            code_diff = ""
            
            if 'files' in commit_data:
                for file_data in commit_data['files']:
                    file_info = {
                        'filename': file_data.get('filename', ''),
                        'status': file_data.get('status', 'modified'),  # added, removed, modified
                        'additions': file_data.get('additions', 0),
                        'deletions': file_data.get('deletions', 0),
                        'changes': file_data.get('changes', 0)
                    }
                    modified_files.append(file_info)
                    
                    # 收集代码diff
                    if include_diff and 'patch' in file_data:
                        code_diff += f"\n--- {file_data['filename']} ---\n"
                        code_diff += file_data['patch']
                        code_diff += "\n"
            
            # 构造Ollama需要的数据格式
            ollama_data = {
                'repository_name': f"{self.repo_owner}/{self.repo_name}",
                'commit_sha': commit_data['sha'],
                'commit_message': commit_data['commit']['message'],
                'author_name': commit_data['commit']['author']['name'],
                'author_email': commit_data['commit']['author']['email'],
                'author_username': commit_data['author']['login'] if commit_data['author'] else 'Unknown',
                'commit_date': commit_data['commit']['author']['date'],
                'modified_files': modified_files,
                'code_diff': code_diff.strip(),
                'stats': {
                    'total_additions': commit_data.get('stats', {}).get('additions', 0),
                    'total_deletions': commit_data.get('stats', {}).get('deletions', 0),
                    'total_changes': commit_data.get('stats', {}).get('total', 0),
                    'files_changed': len(modified_files)
                },
                'commit_url': commit_data['html_url']
            }
            
            return {
                'status': 'success',
                'ollama_data': ollama_data
            }
        else:
            return self._handle_api_error(response)
