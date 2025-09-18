from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.db import transaction
import requests
import json
from .git_client import GitHubWebhookClient, GitHubDataClient, ParamsValidator
from .ollama_client import OllamaClient
from .schemas import is_valid_data_type, DATA_TYPES, success_response, COMMON_RESPONSES
from .models import GitCommitAnalysis
from .sql_client import DatabaseClient
from .service import process_webhook_event


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
    
    # 使用service层处理webhook事件并触发GET请求
    return process_webhook_event(request, event_type, payload)


@require_GET
def get_github_data(request):
    """统一数据获取接口"""
    data_type = request.GET.get('type', '').strip()
    if not data_type:
        return JsonResponse(COMMON_RESPONSES["MISSING_PARAM"]('type'), status=400)
    
    # 验证数据类型是否有效
    if not is_valid_data_type(data_type):
        return JsonResponse(COMMON_RESPONSES["INVALID_PARAM"](
            'type', f'Must be one of: {", ".join(DATA_TYPES)}'
        ), status=400)
    
    # 参数验证
    params, error = ParamsValidator.validate_request_params(request)
    if error:
        return JsonResponse(COMMON_RESPONSES["INVALID_PARAM"]('params', error), status=400)
    
    # 处理webhook状态
    if data_type == 'webhook_status':
        client = GitHubWebhookClient()
        result = {'webhook_configuration': client.get_webhook_stats()}
        return JsonResponse(success_response(result))
    
    # 处理GitHub数据请求
    data_client = GitHubDataClient()
    result = data_client.get_data(data_type, **params)
    
    # 如果请求失败，直接返回错误
    if result.get('status') == 'error':
        return JsonResponse(COMMON_RESPONSES["SERVER_ERROR"](
            result.get('error', 'Unknown error')
        ), status=result.get('status_code', 500))
    
    # 如果是提交详情请求，自动保存到数据库
    if data_type == 'commit_details' and result.get('status') == 'success':
        try:
            # 构造GitHub API格式的数据用于保存
            if 'commit_detail' in result and 'commit' in result['commit_detail']:
                commit_detail = result['commit_detail']['commit']
                github_data = {
                    'sha': commit_detail['sha'],
                    'commit': {
                        'author': {
                            'name': commit_detail['author']['name'],
                            'email': commit_detail['author']['email'],
                            'date': commit_detail['timestamp']['authored_date']
                        },
                        'message': commit_detail['message']
                    },
                    'author': {
                        'login': commit_detail['author']['username'],
                        'avatar_url': commit_detail['author'].get('avatar_url')
                    },
                    'html_url': commit_detail['urls']['html_url'],
                    'url': commit_detail['urls']['api_url'],
                    'stats': commit_detail.get('stats', {}),
                    'files': commit_detail.get('files', []),
                    'parents': commit_detail.get('parents', [])
                }
                
                # 保存到数据库
                success, message, commit_obj = DatabaseClient.save_commit_to_database(github_data)
                
                # 在响应中添加数据库保存状态
                result['database_save'] = {
                    'success': success,
                    'message': message,
                    'commit_saved': commit_obj.commit_sha[:8] if commit_obj else None
                }
                
        except Exception as e:
            # 数据库保存失败不影响API响应
            result['database_save'] = {
                'success': False,
                'message': f'数据库保存失败: {str(e)}',
                'commit_saved': None
            }
    
    # 如果是最近提交请求，批量保存到数据库（获取详细信息）
    elif data_type == 'recent_commits' and result.get('status') == 'success':
        try:
            if 'commits_data' in result and 'commits' in result['commits_data']:
                commits = result['commits_data']['commits']
                saved_count = 0
                
                for commit in commits:
                    # 为每个提交获取详细信息（包含diff）
                    try:
                        detail_result = data_client.get_data('commit_details', 
                                                           sha=commit['sha'], 
                                                           include_diff=True)
                        
                        if detail_result.get('status') == 'success':
                            # 使用详细信息构造GitHub数据格式
                            commit_detail = detail_result['commit_detail']['commit']
                            github_data = {
                                'sha': commit_detail['sha'],
                                'commit': {
                                    'author': {
                                        'name': commit_detail['author']['name'],
                                        'email': commit_detail['author']['email'],
                                        'date': commit_detail['timestamp']['authored_date']
                                    },
                                    'message': commit_detail['message']
                                },
                                'author': {
                                    'login': commit_detail['author']['username'],
                                    'avatar_url': commit_detail['author'].get('avatar_url')
                                },
                                'html_url': commit_detail['urls']['html_url'],
                                'url': commit_detail['urls']['api_url'],
                                'stats': commit_detail.get('stats', {}),
                                'files': commit_detail.get('files', []),
                                'parents': commit_detail.get('parents', []),
                                'patch': commit_detail.get('raw_patch', '')  # 添加patch字段用于diff
                            }
                        else:
                            # 如果获取详细信息失败，使用简化版本
                            github_data = {
                                'sha': commit['sha'],
                                'commit': {
                                    'author': {
                                        'name': commit['author'],
                                        'email': 'unknown@example.com',
                                        'date': commit['date']
                                    },
                                    'message': commit['message']
                                },
                                'author': {
                                    'login': 'unknown',
                                    'avatar_url': None
                                },
                                'html_url': commit['url'],
                                'url': commit['url'],
                                'stats': {},
                                'files': [],
                                'parents': [],
                                'patch': ''  # 空的patch
                            }
                        
                        success, _, _ = DatabaseClient.save_commit_to_database(github_data)
                        if success:
                            saved_count += 1
                            
                    except Exception as commit_error:
                        print(f"处理提交 {commit['sha'][:8]} 时出错: {commit_error}")
                        # 继续处理下一个提交
                        continue
                
                # 在响应中添加批量保存状态
                result['database_save'] = {
                    'success': True,
                    'message': f'批量保存完成，成功保存 {saved_count}/{len(commits)} 个提交（包含详细diff）',
                    'saved_count': saved_count,
                    'total_count': len(commits)
                }
                
        except Exception as e:
            result['database_save'] = {
                'success': False,
                'message': f'批量保存失败: {str(e)}',
                'saved_count': 0
            }
    
    return JsonResponse(success_response(result))


@require_GET
def get_saved_commits(request):
    """
    获取数据库中保存的提交记录
    GET /ai/saved-commits/?limit=10&offset=0
    """
    try:
        # 获取分页参数
        limit = int(request.GET.get('limit', 10))
        offset = int(request.GET.get('offset', 0))
        
        # 验证参数
        if limit < 1 or limit > 100:
            return JsonResponse(COMMON_RESPONSES["INVALID_PARAM"](
                'limit', 'Must be between 1 and 100'
            ), status=400)
        
        if offset < 0:
            return JsonResponse(COMMON_RESPONSES["INVALID_PARAM"](
                'offset', 'Must be >= 0'
            ), status=400)
        
        # 使用DatabaseClient查询
        success, data, error = DatabaseClient.get_saved_commits(limit, offset)
        
        if success:
            return JsonResponse(success_response(data))
        else:
            return JsonResponse(COMMON_RESPONSES["SERVER_ERROR"](error), status=500)
        
    except ValueError:
        return JsonResponse(COMMON_RESPONSES["INVALID_PARAM"](
            'pagination', 'limit and offset must be integers'
        ), status=400)
    except Exception as e:
        return JsonResponse(COMMON_RESPONSES["SERVER_ERROR"](str(e)), status=500)


@require_GET
def get_commit_detail(request, commit_sha):
    """
    获取单个提交的详细信息
    GET /ai/commit-detail/<commit_sha>/
    """
    try:
        # 使用DatabaseClient查询
        success, commit, error = DatabaseClient.get_commit_by_sha(commit_sha)
        
        if not success:
            if "未找到" in error:
                return JsonResponse(COMMON_RESPONSES["NOT_FOUND"](
                    f"Commit with SHA starting with '{commit_sha}'"
                ), status=404)
            else:
                return JsonResponse(COMMON_RESPONSES["INVALID_PARAM"](
                    'sha', error
                ), status=400)
        
        # 返回详细信息
        return JsonResponse(success_response({
            'commit_detail': {
                'commit_sha': commit.commit_sha,
                'short_sha': commit.commit_sha[:8],
                'author_name': commit.author_name,
                'commit_message': commit.commit_message,
                'commit_timestamp': commit.commit_timestamp.isoformat(),
                'code_diff': commit.code_diff,
                'analysis_suggestion': commit.analysis_suggestion,
                'created_at': commit.created_at.isoformat(),
                'updated_at': commit.updated_at.isoformat(),
                'stats': {
                    'message_length': len(commit.commit_message),
                    'diff_length': len(commit.code_diff),
                    'has_analysis': bool(commit.analysis_suggestion)
                }
            }
        }))
        
    except Exception as e:
        return JsonResponse(COMMON_RESPONSES["SERVER_ERROR"](str(e)), status=500)


@require_GET
def get_database_stats(request):
    """
    获取数据库统计信息
    GET /ai/database-stats/
    """
    try:
        stats = DatabaseClient.get_database_stats()
        return JsonResponse(success_response(stats))
    except Exception as e:
        return JsonResponse(COMMON_RESPONSES["SERVER_ERROR"](str(e)), status=500)


@require_GET
def search_commits(request):
    """
    搜索提交记录
    GET /ai/search-commits/?q=关键词&limit=10
    """
    try:
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse(COMMON_RESPONSES["MISSING_PARAM"]('q'), status=400)
        
        limit = int(request.GET.get('limit', 10))
        if limit < 1 or limit > 100:
            return JsonResponse(COMMON_RESPONSES["INVALID_PARAM"](
                'limit', 'Must be between 1 and 100'
            ), status=400)
        
        # 使用DatabaseClient搜索
        success, commits, error = DatabaseClient.search_commits(query, limit)
        
        if success:
            return JsonResponse(success_response({
                'query': query,
                'results_count': len(commits),
                'commits': commits
            }))
        else:
            return JsonResponse(COMMON_RESPONSES["SERVER_ERROR"](error), status=500)
        
    except ValueError:
        return JsonResponse(COMMON_RESPONSES["INVALID_PARAM"](
            'limit', 'Must be an integer'
        ), status=400)
    except Exception as e:
        return JsonResponse(COMMON_RESPONSES["SERVER_ERROR"](str(e)), status=500)