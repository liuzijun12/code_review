from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.utils import timezone
import json
from .git_client import GitHubWebhookClient, GitHubDataClient
from .schemas import is_valid_async_data_type, ASYNC_DATA_TYPES, success_response, error_response
from .tasks.async_get import fetch_github_data_async
from .tasks.async_push import start_push_task
from celery.result import AsyncResult
import logging

logger = logging.getLogger(__name__)


# ==================== Webhook处理 ====================

@csrf_exempt
@require_http_methods(["POST"])
def git_webhook(request):
    """GitHub webhook处理器 - 异步版本"""
    try:
        body = request.body.decode('utf-8')
        payload_data = json.loads(body)
        
        # 提取仓库信息
        repo_info = payload_data.get('repository', {})
        repo_name = repo_info.get('name')
        repo_owner = repo_info.get('owner', {}).get('login')
        
    except (json.JSONDecodeError, AttributeError):
        repo_name = None
        repo_owner = None
    
    github_client = GitHubWebhookClient()
    is_valid, error_response_data, payload = github_client.validate_webhook_request(request, repo_owner, repo_name)
    
    if not is_valid:
        return error_response_data

    event_type = request.META.get('HTTP_X_GITHUB_EVENT', '')
    logger.info(f"处理webhook事件: {event_type}")
    
    # 处理push事件，自动触发异步数据获取和分析
    if event_type == 'push':
        try:
            # 使用封装的方法从 payload 中获取最新提交的 SHA
            latest_sha, sha_source = github_client.extract_latest_commit_sha(payload)
            
            if not latest_sha:
                logger.error("无法从 payload 中获取最新提交 SHA")
                return JsonResponse(error_response('无法获取最新提交 SHA', 400), status=400)
            
            # 验证 SHA 格式
            if not github_client.validate_commit_sha(latest_sha):
                logger.error(f"提取的 SHA 格式无效: {latest_sha}")
                return JsonResponse(error_response(f'提取的 SHA 格式无效: {latest_sha}', 400), status=400)
            
            # 启动异步GitHub数据获取任务 - 只处理单个提交
            task = fetch_github_data_async.delay(
                data_type='commit_details',
                repo_owner=repo_owner,
                repo_name=repo_name,
                sha=latest_sha,
                include_diff=True
            )
            
            logger.info(f"🚀 Webhook触发异步任务: {task.id}, 处理提交: {latest_sha[:8]} (来源: {sha_source})")
            
            return JsonResponse(success_response({
                'event_type': event_type,
                'message': f'Push事件处理成功，已启动单个提交的异步数据获取和AI分析',
                'async_task_id': task.id,
                'commit_sha': latest_sha,
                'commit_short_sha': latest_sha[:8],
                'sha_source': sha_source,
                'repository': payload.get('repository', {}).get('full_name', 'unknown'),
                'branch': payload.get('ref', 'refs/heads/main').replace('refs/heads/', ''),
                'total_commits_in_push': len(payload.get('commits', [])),
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
    
    # 获取仓库信息
    repo_owner = request.GET.get('repo_owner', '').strip()
    repo_name = request.GET.get('repo_name', '').strip()
    
    # 简化参数处理，只获取基本参数
    params = {
        'branch': request.GET.get('branch', 'main'),
        'limit': int(request.GET.get('limit', 10)),
        'sha': request.GET.get('sha', ''),
        'include_diff': request.GET.get('include_diff', 'true').lower() == 'true'
    }
    
    # 使用仓库信息创建客户端
    data_client = GitHubDataClient(repo_owner=repo_owner, repo_name=repo_name)
    result = data_client.get_data(data_type, **params)
    
    if result.get('status') == 'error':
        return JsonResponse(error_response(
            result.get('error', 'Unknown error'), 500
        ), status=500)
    
    return JsonResponse(success_response(result))
        
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
        
        # 获取仓库信息
        repo_owner = data.get('repo_owner', '').strip()
        repo_name = data.get('repo_name', '').strip()
        params = data.get('params', {})
        
        task = fetch_github_data_async.delay(
            data_type, 
            repo_owner=repo_owner, 
            repo_name=repo_name, 
            **params
        )
        
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
def get_commit_details_async_start(request):
    """快速启动异步获取提交详情的任务"""
    try:
        sha = request.GET.get('sha', '').strip()
        if not sha:
            return JsonResponse(error_response("Missing required parameter: " + 'sha'), status=400)
        
        # 获取仓库信息
        repo_owner = request.GET.get('repo_owner', '').strip()
        repo_name = request.GET.get('repo_name', '').strip()
        
        include_diff = request.GET.get('include_diff', 'true').lower() == 'true'
        task = fetch_github_data_async.delay(
            'commit_details', 
            repo_owner=repo_owner, 
            repo_name=repo_name, 
            sha=sha, 
            include_diff=include_diff
        )
        
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


# ==================== 健康检查接口 ====================

@require_GET
def health_check(request):
    """
    系统健康检查接口
    用于 Docker 容器健康检查和负载均衡器状态检测
    """
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'services': {}
        }
        
        # 检查数据库连接
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                health_status['services']['database'] = 'healthy'
        except Exception as e:
            health_status['services']['database'] = f'unhealthy: {str(e)}'
            health_status['status'] = 'degraded'
        
        # 检查 Redis 连接 (Celery)
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            if stats:
                health_status['services']['redis'] = 'healthy'
                health_status['services']['celery_workers'] = len(stats)
            else:
                health_status['services']['redis'] = 'healthy'
                health_status['services']['celery_workers'] = 0
        except Exception as e:
            health_status['services']['redis'] = f'unhealthy: {str(e)}'
            health_status['services']['celery_workers'] = 0
            health_status['status'] = 'degraded'
        
        # 检查 Ollama 服务
        try:
            from .ollama_client import OllamaClient
            ollama_client = OllamaClient()
            # 简单的健康检查，不进行实际的模型调用
            models = ollama_client.list_models()
            if models.get('status') == 'success':
                health_status['services']['ollama'] = 'healthy'
                health_status['services']['ollama_models'] = len(models.get('models', []))
            else:
                health_status['services']['ollama'] = 'unhealthy'
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['services']['ollama'] = f'unhealthy: {str(e)}'
            health_status['status'] = 'degraded'
        
        # 检查磁盘空间
        try:
            import shutil
            disk_usage = shutil.disk_usage('/')
            free_space_gb = disk_usage.free / (1024**3)
            health_status['services']['disk_space'] = f'{free_space_gb:.2f}GB free'
            if free_space_gb < 1:  # 少于1GB时标记为不健康
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['services']['disk_space'] = f'unknown: {str(e)}'
        
        # 根据整体状态设置 HTTP 状态码
        if health_status['status'] == 'healthy':
            return JsonResponse(success_response(health_status))
        else:
            return JsonResponse(success_response(health_status), status=503)  # Service Unavailable
            
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return JsonResponse(error_response(f'Health check failed: {str(e)}', 500), status=500)


@require_GET
def health_simple(request):
    """
    简单的健康检查接口 - 仅检查应用是否运行
    用于快速的存活性检查
    """
    return JsonResponse(success_response({
        'status': 'ok',
        'timestamp': timezone.now().isoformat(),
        'message': 'Application is running'
    }))


# ==================== 推送接口 ====================

@require_POST
@csrf_exempt
def start_push_task_api(request):
    """启动推送任务"""
    try:
        data = json.loads(request.body)
        delay_seconds = data.get('delay_seconds', 3)
        repo_owner = data.get('repo_owner', '')
        repo_name = data.get('repo_name', '')
        
        # 验证延迟时间
        if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
            return JsonResponse(error_response('delay_seconds must be a non-negative number', 400), status=400)
        
        # 启动推送任务
        task = start_push_task(delay_seconds, repo_owner, repo_name)
        
        logger.info(f"启动推送任务: {task.id}")
        
        return JsonResponse(success_response({
            'task_id': task.id,
            'message': '推送任务已启动',
            'delay_seconds': delay_seconds,
            'repo_owner': repo_owner,
            'repo_name': repo_name,
            'check_url': f'/ai/task-status/{task.id}/'
        }))
        
    except json.JSONDecodeError:
        return JsonResponse(error_response('Invalid JSON payload', 400), status=400)
    except Exception as e:
        logger.error(f"启动推送任务失败: {e}")
        return JsonResponse(error_response(str(e), 500), status=500)
