"""
异步GET请求处理模块
用于异步获取GitHub数据并保存到数据库
"""
import logging
from celery import shared_task
from django.utils import timezone
from ..git_client import GitHubDataClient
from ..sql_client import DatabaseClient
from ..schemas import is_valid_async_data_type, ASYNC_DATA_TYPES

logger = logging.getLogger(__name__)


@shared_task(name='app_ai.tasks.async_get.fetch_github_data_async')
def fetch_github_data_async(data_type: str, **params):
    """
    异步获取GitHub数据并保存到数据库
    Args:
        data_type: 数据类型 (recent_commits, commit_details, etc.)
        **params: 请求参数
        
    Returns:
        dict: 任务执行结果，格式与同步版本保持一致
    """
    try:
        logger.info(f"开始异步获取GitHub数据: {data_type}")
        
        # 验证数据类型
        if not is_valid_async_data_type(data_type):
            return {
                'status': 'error',
                'error': f'无效的数据类型: {data_type}',
                'data_type': data_type,
                'execution_time': timezone.now().isoformat()
            }
        
        # 处理webhook状态（不需要异步）
        if data_type == 'webhook_status':
            from ..git_client import GitHubWebhookClient
            client = GitHubWebhookClient()
            return {
                'status': 'success',
                'webhook_configuration': client.get_webhook_stats(),
                'execution_time': timezone.now().isoformat()
            }
        
        # 创建GitHub数据客户端
        data_client = GitHubDataClient()
        
        # 获取数据
        result = data_client.get_data(data_type, **params)
        
        if result.get('status') != 'success':
            logger.error(f"GitHub API请求失败: {result.get('error', 'Unknown error')}")
            return {
                'status': 'error',
                'error': result.get('error', 'GitHub API请求失败'),
                'data_type': data_type,
                'execution_time': timezone.now().isoformat()
            }
        
        # 根据数据类型处理 - 只支持单个提交
        if data_type == 'commit_details':
            # 单个提交直接进行Ollama分析，不存数据库
            _process_single_commit_for_ollama(result)
        else:
            # 不再支持其他数据类型
            result['error'] = f'Unsupported data type: {data_type}. Only commit_details is supported.'
            result['status'] = 'error'
        
        # 添加执行时间
        result['execution_time'] = timezone.now().isoformat()
        
        logger.info(f"异步GitHub数据获取任务完成: {data_type}")
        return result
        
    except Exception as e:
        error_msg = f"异步GitHub数据获取任务异常: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'error': error_msg,
            'data_type': data_type,
            'execution_time': timezone.now().isoformat()
        }


def _process_single_commit_for_ollama(result):
    """处理单个提交，直接进行Ollama分析，不存数据库"""
    try:
        if 'ollama_data' not in result:
            logger.warning("结果中没有 ollama_data，跳过Ollama分析")
            result['ollama_analysis'] = {
                'triggered': False,
                'message': '没有找到 ollama_data，跳过分析'
            }
            return
        
        ollama_data = result['ollama_data']
        commit_sha = ollama_data.get('commit_sha', 'unknown')
        
        logger.info(f"开始直接Ollama分析单个提交: {commit_sha[:8]}")
        
        # 直接调用Ollama分析
        try:
            from ..ollama_client import OllamaClient
            
            ollama_client = OllamaClient()
            
            # 检查Ollama服务状态
            status_check = ollama_client.check_connection()
            if status_check['status'] != 'connected':
                logger.error(f"Ollama服务不可用: {status_check.get('error', 'Unknown error')}")
                result['ollama_analysis'] = {
                    'triggered': False,
                    'error': status_check.get('error', 'Ollama service unavailable'),
                    'message': 'Ollama服务不可用，跳过分析'
                }
                return
            
            # 进行分析
            analysis_result = ollama_client.explain_commit(
                commit_message=ollama_data['commit_message'],
                code_diff=ollama_data['code_diff'],
                author_name=ollama_data['author_name']
            )
            
            if analysis_result.get('status') == 'success':
                logger.info(f"Ollama分析成功: {commit_sha[:8]}")
                
                # 将分析结果添加到响应中
                result['ollama_analysis'] = {
                    'triggered': True,
                    'status': 'success',
                    'analysis_suggestion': analysis_result.get('response', ''),
                    'commit_sha': commit_sha,
                    'message': f'提交 {commit_sha[:8]} 分析完成'
                }
                
                # 自动触发推送（如果分析成功）
                try:
                    from .async_push import push_single_analysis_result
                    
                    # 构造推送数据
                    push_data = {
                        'repository_name': ollama_data['repository_name'],
                        'commit_sha': commit_sha,
                        'commit_message': ollama_data['commit_message'],
                        'author_name': ollama_data['author_name'],
                        'commit_date': ollama_data['commit_date'],
                        'modified_files': ollama_data['modified_files'],
                        'stats': ollama_data['stats'],
                        'commit_url': ollama_data['commit_url'],
                        'analysis_suggestion': analysis_result.get('response', '')
                    }
                    
                    push_task = push_single_analysis_result.delay(push_data)
                    logger.info(f"📱 自动触发推送任务: {push_task.id}")
                    
                    result['push_task'] = {
                        'triggered': True,
                        'task_id': push_task.id,
                        'message': f'已自动触发提交 {commit_sha[:8]} 的推送'
                    }
                    
                except Exception as push_error:
                    logger.error(f"触发推送任务失败: {push_error}")
                    result['push_task'] = {
                        'triggered': False,
                        'error': str(push_error),
                        'message': '推送任务触发失败'
                    }
                    
            else:
                logger.warning(f"Ollama分析失败: {commit_sha[:8]}, 错误: {analysis_result.get('error', 'Unknown error')}")
                result['ollama_analysis'] = {
                    'triggered': True,
                    'status': 'failed',
                    'error': analysis_result.get('error', 'Analysis failed'),
                    'message': f'提交 {commit_sha[:8]} 分析失败'
                }
                
                # 分析失败时不触发推送
                result['push_task'] = {
                    'triggered': False,
                    'message': '分析失败，跳过推送'
                }
                
        except Exception as ollama_error:
            logger.error(f"Ollama分析异常: {ollama_error}")
            result['ollama_analysis'] = {
                'triggered': False,
                'error': str(ollama_error),
                'message': f'Ollama分析异常: {str(ollama_error)}'
            }
            
            # 异常时不触发推送
            result['push_task'] = {
                'triggered': False,
                'error': str(ollama_error),
                'message': 'Ollama分析异常，跳过推送'
            }
            
    except Exception as e:
        logger.error(f"处理单个提交异常: {e}")
        result['ollama_analysis'] = {
            'triggered': False,
            'error': str(e),
            'message': f'处理异常: {str(e)}'
        }

