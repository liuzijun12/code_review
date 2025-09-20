from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET, require_POST
import json
from .git_client import GitHubWebhookClient, GitHubDataClient
from .schemas import is_valid_async_data_type, ASYNC_DATA_TYPES, success_response, error_response
from .sql_client import DatabaseClient
# from .service import process_webhook_event  # 不再使用同步处理
from .tasks.async_get import fetch_github_data_async
from .tasks.async_ollama import start_ollama_analysis, start_single_commit_analysis
from .tasks.async_push import start_push_task
from celery.result import AsyncResult
import logging

logger = logging.getLogger(__name__)


# ==================== Webhook处理 ====================

@csrf_exempt
@require_http_methods(["POST"])
def git_webhook(request):
    """GitHub webhook处理器 - 异步版本"""
    github_client = GitHubWebhookClient()
    is_valid, error_response_data, payload = github_client.validate_webhook_request(request)
    
    if not is_valid:
        return error_response_data
    
    event_type = request.META.get('HTTP_X_GITHUB_EVENT', '')
    logger.info(f"处理webhook事件: {event_type}")
    
    # 处理push事件，自动触发异步数据获取和分析
    if event_type == 'push':
        try:
            # 启动异步GitHub数据获取任务
            task = fetch_github_data_async.delay(
                data_type='recent_commits',
                params={
                    'branch': payload.get('ref', 'refs/heads/main').replace('refs/heads/', ''),
                    'limit': 10,
                    'include_diff': True
                }
            )
            
            logger.info(f"🚀 Webhook触发异步任务: {task.id}")
            
            return JsonResponse(success_response({
                'event_type': event_type,
                'message': 'Push事件处理成功，已启动异步数据获取和AI分析',
                'async_task_id': task.id,
                'repository': payload.get('repository', {}).get('full_name', 'unknown'),
                'branch': payload.get('ref', 'refs/heads/main').replace('refs/heads/', ''),
                'commits_count': len(payload.get('commits', [])),
                'check_url': f'/ai/task-status/{task.id}/'
            }))
            
        except Exception as e:
            logger.error(f"Webhook异步任务启动失败: {e}")
            return JsonResponse(error_response(f'异步任务启动失败: {str(e)}', 500), status=500)
    
    elif event_type == 'ping':
        return JsonResponse(success_response({
            'event_type': event_type,
            'message': 'Webhook ping事件处理成功',
            'repository': payload.get('repository', {}).get('full_name', 'unknown')
        }))
    
    else:
        logger.info(f"忽略事件类型: {event_type}")
        return JsonResponse(success_response({
            'event_type': event_type,
            'message': f'事件类型 {event_type} 已忽略'
        }))


# ==================== 同步数据接口 ====================

@require_GET
def get_github_data(request):
    """同步获取GitHub数据接口"""
    data_type = request.GET.get('type', '').strip()
    if not data_type:
        return JsonResponse(error_response("Missing required parameter: type", 400), status=400)
    
    if not is_valid_async_data_type(data_type):
        return JsonResponse(error_response(
            f'Invalid data type. Must be one of: {", ".join(ASYNC_DATA_TYPES)}', 400
        ), status=400)
    
    # 简化参数处理，只获取基本参数
    params = {
        'branch': request.GET.get('branch', 'main'),
        'limit': int(request.GET.get('limit', 10)),
        'sha': request.GET.get('sha', ''),
        'include_diff': request.GET.get('include_diff', 'true').lower() == 'true'
    }
    
    data_client = GitHubDataClient()
    result = data_client.get_data(data_type, **params)
    
    if result.get('status') == 'error':
        return JsonResponse(error_response(
            result.get('error', 'Unknown error'), 500
        ), status=500)
    
    # 自动保存到数据库
    _save_data_to_database(data_type, result, data_client)
    
    return JsonResponse(success_response(result))


def _save_data_to_database(result, data_type, data_client):
    """统一的数据库保存逻辑"""
    if data_type == 'commit_details' and result.get('status') == 'success':
        _save_single_commit(result)
    elif data_type == 'recent_commits' and result.get('status') == 'success':
        _save_recent_commits_batch(result, data_client)


def _save_single_commit(result):
    """保存单个提交到数据库"""
    try:
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
            
            success, message, commit_obj = DatabaseClient.save_commit_to_database(github_data)
            result['database_save'] = {
                'success': success,
                'message': message,
                'commit_saved': commit_obj.commit_sha[:8] if commit_obj else None
            }
            
    except Exception as e:
        result['database_save'] = {
            'success': False,
            'message': f'数据库保存失败: {str(e)}',
            'commit_saved': None
        }


def _save_recent_commits_batch(result, data_client):
    """批量保存最近提交到数据库"""
    try:
        if 'commits_data' in result and 'commits' in result['commits_data']:
            commits = result['commits_data']['commits']
            saved_count = 0
            
            for commit in commits:
                try:
                    detail_result = data_client.get_data('commit_details', 
                                                       sha=commit['sha'], 
                                                       include_diff=True)
                    
                    if detail_result.get('status') == 'success':
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
                            'patch': commit_detail.get('raw_patch', '')
                        }
                    else:
                        # 简化版本
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
                            'author': {'login': 'unknown', 'avatar_url': None},
                            'html_url': commit['url'],
                            'url': commit['url'],
                            'stats': {}, 'files': [], 'parents': [], 'patch': ''
                        }
                    
                    success, message, _ = DatabaseClient.save_commit_to_database(github_data)
                    if success:
                        saved_count += 1
                        
                except Exception as commit_error:
                    logger.error(f"处理提交 {commit['sha'][:8]} 时出错: {commit_error}")
                    continue
            
            result['database_save'] = {
                'success': True,
                'message': f'批量保存完成，成功保存 {saved_count}/{len(commits)} 个提交',
                'saved_count': saved_count,
                'total_count': len(commits)
            }
            
    except Exception as e:
        result['database_save'] = {
            'success': False,
            'message': f'批量保存失败: {str(e)}',
            'saved_count': 0
        }


# ==================== 数据库查询接口 ====================
# 注意：这些接口在 urls.py 中定义但可能未被实际使用，保留以防需要


# ==================== 异步接口 ====================

@require_POST
@csrf_exempt
def get_github_data_async(request):
    """异步获取GitHub数据接口"""
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(error_response(
                'body', 'Invalid JSON format'
            ), status=400)
        
        data_type = data.get('type', '').strip()
        if not data_type:
            return JsonResponse(error_response("Missing required parameter: " + 'type'), status=400)
        
        if not is_valid_async_data_type(data_type):
            return JsonResponse(error_response(
                f'Invalid data type. Must be one of: {", ".join(ASYNC_DATA_TYPES)}', 400
            ), status=400)
        
        params = data.get('params', {})
        task = fetch_github_data_async.delay(data_type, **params)
        
        logger.info(f"启动异步GitHub数据获取任务: {task.id}, 类型: {data_type}")
        
        return JsonResponse(success_response({
            'task_id': task.id,
            'status': 'pending',
            'message': f'异步任务已启动，正在获取 {data_type} 数据',
            'data_type': data_type,
            'params': params,
            'check_url': f'/ai/task-status/{task.id}/'
        }))
        
    except Exception as e:
        return JsonResponse(error_response(str(e)), status=500)


@require_GET
def get_task_status(request, task_id):
    """获取异步任务状态"""
    try:
        task_result = AsyncResult(task_id)
        
        if task_result.state == 'PENDING':
            response = {
                'task_id': task_id,
                'status': 'pending',
                'message': '任务正在执行中...',
                'progress': None
            }
        elif task_result.state == 'SUCCESS':
            response = {
                'task_id': task_id,
                'status': 'completed',
                'message': '任务执行完成',
                'result': task_result.result
            }
        elif task_result.state == 'FAILURE':
            response = {
                'task_id': task_id,
                'status': 'failed',
                'message': '任务执行失败',
                'error': str(task_result.info)
            }
        else:
            response = {
                'task_id': task_id,
                'status': task_result.state.lower(),
                'message': f'任务状态: {task_result.state}',
                'info': str(task_result.info) if task_result.info else None
            }
        
        return JsonResponse(success_response(response))
        
    except Exception as e:
        return JsonResponse(error_response(str(e)), status=500)


@require_GET
def get_recent_commits_async_start(request):
    """快速启动异步获取最近提交的任务"""
    try:
        limit = int(request.GET.get('limit', 10))
        include_details = request.GET.get('include_details', 'true').lower() == 'true'
        
        if limit < 1 or limit > 100:
            return JsonResponse(error_response(
                'limit', 'Must be between 1 and 100'
            ), status=400)
        
        task = fetch_github_data_async.delay('recent_commits', limit=limit, include_details=include_details)
        
        logger.info(f"启动异步获取最近提交任务: {task.id}, limit={limit}")
        
        return JsonResponse(success_response({
            'task_id': task.id,
            'status': 'pending',
            'message': f'异步任务已启动，正在获取最近 {limit} 个提交',
            'data_type': 'recent_commits',
            'params': {'limit': limit, 'include_details': include_details},
            'check_url': f'/ai/task-status/{task.id}/'
        }))
        
    except ValueError:
        return JsonResponse(error_response(
            'limit', 'Must be an integer'
        ), status=400)
    except Exception as e:
        return JsonResponse(error_response(str(e)), status=500)


@require_GET
def get_commit_details_async_start(request):
    """快速启动异步获取提交详情的任务"""
    try:
        sha = request.GET.get('sha', '').strip()
        if not sha:
            return JsonResponse(error_response("Missing required parameter: " + 'sha'), status=400)
        
        include_diff = request.GET.get('include_diff', 'true').lower() == 'true'
        task = fetch_github_data_async.delay('commit_details', sha=sha, include_diff=include_diff)
        
        logger.info(f"启动异步获取提交详情任务: {task.id}, sha={sha[:8]}")
        
        return JsonResponse(success_response({
            'task_id': task.id,
            'status': 'pending',
            'message': f'异步任务已启动，正在获取提交 {sha[:8]} 的详情',
            'data_type': 'commit_details',
            'params': {'sha': sha, 'include_diff': include_diff},
            'check_url': f'/ai/task-status/{task.id}/'
        }))
        
    except Exception as e:
        return JsonResponse(error_response(str(e), 500), status=500)


# ==================== Ollama分析接口 ====================

@require_POST
@csrf_exempt
def start_ollama_analysis_api(request):
    """启动Ollama分析任务"""
    try:
        data = json.loads(request.body)
        commit_shas = data.get('commit_shas')  # 可选，指定要分析的提交SHA列表
        
        # 启动异步分析任务
        task = start_ollama_analysis(commit_shas)
        
        logger.info(f"启动Ollama分析任务: {task.id}")
        
        return JsonResponse(success_response({
            'task_id': task.id,
            'message': f'Ollama分析任务已启动',
            'target_commits': len(commit_shas) if commit_shas else '所有未分析提交',
            'check_url': f'/ai/task-status/{task.id}/'
        }))
        
    except json.JSONDecodeError:
        return JsonResponse(error_response('Invalid JSON payload', 400), status=400)
    except Exception as e:
        logger.error(f"启动Ollama分析任务失败: {e}")
        return JsonResponse(error_response(str(e), 500), status=500)


@require_POST
@csrf_exempt
def analyze_single_commit_api(request):
    """分析单个提交"""
    try:
        data = json.loads(request.body)
        commit_sha = data.get('commit_sha', '').strip()
        
        if not commit_sha:
            return JsonResponse(error_response("Missing required parameter: commit_sha", 400), status=400)
        
        # 启动单个提交分析任务
        task = start_single_commit_analysis(commit_sha)
        
        logger.info(f"启动单个提交分析任务: {task.id}, 提交: {commit_sha[:8]}")
        
        return JsonResponse(success_response({
            'task_id': task.id,
            'commit_sha': commit_sha,
            'message': f'单个提交分析任务已启动',
            'check_url': f'/ai/task-status/{task.id}/'
        }))
        
    except json.JSONDecodeError:
        return JsonResponse(error_response('Invalid JSON payload', 400), status=400)
    except Exception as e:
        logger.error(f"启动单个提交分析失败: {e}")
        return JsonResponse(error_response(str(e), 500), status=500)


@require_GET
def get_unanalyzed_commits_api(request):
    """获取未分析的提交列表"""
    try:
        limit = int(request.GET.get('limit', 20))
        if limit < 1 or limit > 100:
            return JsonResponse(error_response('limit must be between 1 and 100', 400), status=400)
        
        # 获取未分析的提交
        unanalyzed_commits = DatabaseClient.get_unanalyzed_commits(limit)
        
        # 格式化返回数据
        commits_data = []
        for commit in unanalyzed_commits:
            commits_data.append({
                'commit_sha': commit['commit_sha'],
                'short_sha': commit['commit_sha'][:8],
                'author_name': commit['author_name'],
                'commit_message': commit['commit_message'][:100] + '...' if len(commit['commit_message']) > 100 else commit['commit_message'],
                'commit_timestamp': commit['commit_timestamp'],
                'code_diff_length': len(commit.get('code_diff', '')),
                'created_at': commit['created_at']
            })
        
        return JsonResponse(success_response({
            'unanalyzed_commits': commits_data,
            'count': len(commits_data),
            'limit': limit,
            'message': f'找到 {len(commits_data)} 个未分析的提交'
        }))
        
    except ValueError:
        return JsonResponse(error_response('limit must be an integer', 400), status=400)
    except Exception as e:
        logger.error(f"获取未分析提交失败: {e}")
        return JsonResponse(error_response(str(e), 500), status=500)


# ==================== 推送接口 ====================

@require_POST
@csrf_exempt
def start_push_task_api(request):
    """启动推送任务"""
    try:
        data = json.loads(request.body)
        delay_seconds = data.get('delay_seconds', 3)  # 默认3秒延迟
        
        # 验证延迟时间
        if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
            return JsonResponse(error_response('delay_seconds must be a non-negative number', 400), status=400)
        
        # 启动推送任务
        task = start_push_task(delay_seconds)
        
        logger.info(f"启动推送任务: {task.id}")
        
        return JsonResponse(success_response({
            'task_id': task.id,
            'message': '推送任务已启动',
            'delay_seconds': delay_seconds,
            'check_url': f'/ai/task-status/{task.id}/'
        }))
        
    except json.JSONDecodeError:
        return JsonResponse(error_response('Invalid JSON payload', 400), status=400)
    except Exception as e:
        logger.error(f"启动推送任务失败: {e}")
        return JsonResponse(error_response(str(e), 500), status=500)


@require_GET
def get_unpushed_commits_api(request):
    """获取未推送的分析结果列表"""
    try:
        limit = int(request.GET.get('limit', 20))
        if limit < 1 or limit > 100:
            return JsonResponse(error_response('limit must be between 1 and 100', 400), status=400)
        
        # 获取未推送的分析结果
        from app_ai.models import GitCommitAnalysis
        
        unpushed_records = GitCommitAnalysis.objects.filter(
            analysis_suggestion__isnull=False,
            is_push=0
        ).exclude(
            analysis_suggestion=''
        ).order_by('commit_timestamp')[:limit]
        
        # 格式化返回数据
        commits_data = []
        for record in unpushed_records:
            commits_data.append({
                'commit_sha': record.commit_sha,
                'short_sha': record.commit_sha[:8],
                'author_name': record.author_name,
                'commit_message': record.commit_message[:100] + '...' if len(record.commit_message) > 100 else record.commit_message,
                'commit_timestamp': record.commit_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'analysis_length': len(record.analysis_suggestion),
                'code_diff_length': len(record.code_diff) if record.code_diff else 0,
                'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return JsonResponse(success_response({
            'unpushed_commits': commits_data,
            'count': len(commits_data),
            'limit': limit,
            'message': f'找到 {len(commits_data)} 个未推送的分析结果'
        }))
        
    except ValueError:
        return JsonResponse(error_response('limit must be an integer', 400), status=400)
    except Exception as e:
        logger.error(f"获取未推送提交失败: {e}")
        return JsonResponse(error_response(str(e), 500), status=500)