from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET
from django.conf import settings
import requests
from .git_client import GitHubWebhookClient, GitHubDataClient
from .ollama_client import OllamaClient


@csrf_exempt
@require_http_methods(["POST"])
def git_webhook(request):
    """
    GitHub webhook处理器，验证请求签名并处理各种事件
    """
    # 创建GitHub客户端实例
    github_client = GitHubWebhookClient()
    
    # 验证webhook请求
    is_valid, error_response, payload = github_client.validate_webhook_request(request)
    
    if not is_valid:
        return error_response
    
    # 获取事件类型
    event_type = request.META.get('HTTP_X_GITHUB_EVENT', '')
    
    # 根据事件类型分发处理
    if event_type == 'push':
        return github_client.handle_push_event(payload)
    elif event_type == 'ping':
        return github_client.handle_ping_event(payload)
    else:
        return JsonResponse({
            'message': f'Event type "{event_type}" is not supported',
            'supported_events': ['push', 'ping'],
            'status': 'ignored'
        }, status=200)


@require_GET
def get_github_data(request):
    """
    统一的GitHub数据获取接口 (GET请求)
    
    支持的数据类型:
    - webhook_status: Webhook配置状态
    - repository_info: 仓库基本信息
    - recent_commits: 最近提交记录  
    - pull_requests: PR列表
    - repository_stats: 仓库统计
    - search_code: 代码搜索
    - commit_details: 提交详情
    - client_status: 客户端状态
    - ollama_status: Ollama服务状态
    - ollama_models: 可用模型列表
    - code_review: 代码审查
    - commit_analysis: 提交分析
    
    使用方法:
    GET /ai/github-data/?type=repository_info
    GET /ai/github-data/?type=recent_commits&branch=main&limit=5
    GET /ai/github-data/?type=commit_details&sha=abc123&include_diff=true
    GET /ai/github-data/?type=search_code&query=function&limit=5
    """
    # 获取数据类型
    data_type = request.GET.get('type', '')
    if not data_type:
        return JsonResponse({
            'error': 'Missing required parameter "type"',
            'supported_types': [
                'webhook_status', 'repository_info', 'recent_commits', 'pull_requests', 
                'repository_stats', 'search_code', 'commit_details', 'client_status',
                'ollama_status', 'ollama_models', 'code_review', 'commit_analysis'
            ],
            'usage_examples': [
                '/ai/github-data/?type=webhook_status',
                '/ai/github-data/?type=repository_info',
                '/ai/github-data/?type=recent_commits&branch=main&limit=5',
                '/ai/github-data/?type=pull_requests&state=open&limit=10',
                '/ai/github-data/?type=repository_stats',
                '/ai/github-data/?type=search_code&query=function&limit=5',
                '/ai/github-data/?type=commit_details&sha=abc123&include_diff=true',
                '/ai/github-data/?type=commit_details&branch=main&limit=3&include_diff=false',
                '/ai/github-data/?type=client_status',
                '/ai/github-data/?type=ollama_status',
                '/ai/github-data/?type=ollama_models',
                '/ai/github-data/?type=code_review&code=your_code_here&model=llama2',
                '/ai/github-data/?type=commit_analysis&sha=abc123&model=llama2'
            ],
            'status': 'error'
        }, status=400)
    
    # 处理webhook_status类型
    if data_type == 'webhook_status':
        github_client = GitHubWebhookClient()
        stats = github_client.get_webhook_stats()
        
        return JsonResponse({
            'webhook_configuration': stats,
            'endpoint': '/ai/git-webhook/',
            'supported_events': ['push', 'ping'],
            'status': 'active',
            'parameters': {'type': data_type},
            'timestamp': request.META.get('HTTP_DATE', '')
        })
    
    # 收集所有GET参数
    params = {}
    for key, value in request.GET.items():
        if key != 'type':
            # 尝试转换数字类型
            if value.isdigit():
                params[key] = int(value)
            elif value.lower() in ['true', 'false']:
                params[key] = value.lower() == 'true'
            else:
                params[key] = value
    
    # 处理Ollama相关请求
    if data_type in ['ollama_status', 'ollama_models', 'code_review', 'commit_analysis']:
        ollama_client = OllamaClient()
        
        if data_type == 'ollama_status':
            result = ollama_client.check_connection()
        elif data_type == 'ollama_models':
            result = ollama_client.list_models()
        elif data_type == 'code_review':
            code = params.get('code', '')
            model = params.get('model', 'llama2')
            if not code:
                result = {
                    'status': 'error',
                    'error': 'Missing required parameter "code"'
                }
            else:
                result = ollama_client.code_review(code, model)
        elif data_type == 'commit_analysis':
            sha = params.get('sha', '')
            model = params.get('model', 'llama2')
            if not sha:
                result = {
                    'status': 'error',
                    'error': 'Missing required parameter "sha"'
                }
            else:
                # 首先获取提交详情
                data_client = GitHubDataClient()
                commit_detail = data_client.get_data('commit_details', sha=sha, include_diff=True)
                
                if commit_detail.get('status') == 'success' and 'commit_detail' in commit_detail:
                    commit_data = commit_detail['commit_detail']['commit']
                    result = ollama_client.explain_commit(commit_data, model)
                else:
                    result = {
                        'status': 'error',
                        'error': f'Failed to fetch commit details: {commit_detail.get("error", "Unknown error")}'
                    }
    else:
        # 处理GitHub数据请求
        data_client = GitHubDataClient()
        result = data_client.get_data(data_type, **params)
    
    # 添加请求参数到响应
    result['parameters'] = {
        'type': data_type,
        **params
    }
    result['timestamp'] = request.META.get('HTTP_DATE', '')
    
    return JsonResponse(result)