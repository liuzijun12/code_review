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
            from .git_client import GitHubWebhookClient
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
        
        # 根据数据类型处理数据库保存
        if data_type == 'commit_details':
            _save_commit_details_to_db(result)
        elif data_type == 'recent_commits':
            _save_recent_commits_to_db(result, data_client)
        
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


def _save_commit_details_to_db(result):
    """保存单个提交详情到数据库（与同步版本保持一致）"""
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
            
            # 保存到数据库
            success, message, commit_obj = DatabaseClient.save_commit_to_database(github_data)
            
            if success:
                logger.info(f"提交详情保存成功: {commit_obj.commit_sha[:8] if commit_obj else 'Unknown'}")
            else:
                logger.warning(f"提交详情保存失败: {message}")
            
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


def _save_recent_commits_to_db(result, data_client):
    """批量保存最近提交到数据库（与同步版本保持一致）"""
    try:
        if 'commits_data' in result and 'commits' in result['commits_data']:
            commits = result['commits_data']['commits']
            saved_count = 0
            logger.info(f"开始处理 {len(commits)} 个提交，获取详细信息并保存到数据库")
            
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
                    
                    success, message, _ = DatabaseClient.save_commit_to_database(github_data)
                    if success:
                        saved_count += 1
                        logger.info(f"保存提交成功: {commit['sha'][:8]}")
                    else:
                        logger.warning(f"保存提交失败: {commit['sha'][:8]} - {message}")
                        
                except Exception as commit_error:
                    logger.error(f"处理提交 {commit['sha'][:8]} 时出错: {commit_error}")
                    # 继续处理下一个提交
                    continue
            
            # 收集保存成功的提交SHA
            saved_commit_shas = []
            if saved_count > 0:
                # 重新获取保存的提交SHA（简化处理）
                for commit in commits:
                    saved_commit_shas.append(commit['sha'])
            
            # 在响应中添加批量保存状态
            result['database_save'] = {
                'success': True,
                'message': f'异步批量保存完成，成功保存 {saved_count}/{len(commits)} 个提交（包含详细diff）',
                'saved_count': saved_count,
                'total_count': len(commits),
                'saved_commits': saved_commit_shas[:saved_count]  # 只包含实际保存成功的数量
            }
            
            logger.info(f"异步批量保存完成：{saved_count}/{len(commits)} 个提交")
            
            # 自动触发Ollama分析
            if saved_count > 0:
                try:
                    from .async_ollama import auto_analyze_after_git_fetch
                    ollama_task = auto_analyze_after_git_fetch.delay(result)
                    logger.info(f"🤖 自动触发Ollama分析任务: {ollama_task.id}")
                    
                    # 在结果中添加Ollama任务信息
                    result['ollama_analysis'] = {
                        'triggered': True,
                        'task_id': ollama_task.id,
                        'message': f'已自动触发 {saved_count} 个提交的AI分析'
                    }
                except Exception as ollama_error:
                    logger.error(f"触发Ollama分析失败: {ollama_error}")
                    result['ollama_analysis'] = {
                        'triggered': False,
                        'error': str(ollama_error),
                        'message': 'Ollama分析触发失败'
                    }
            else:
                result['ollama_analysis'] = {
                    'triggered': False,
                    'message': '没有新保存的提交，跳过AI分析'
                }
            
    except Exception as e:
        result['database_save'] = {
            'success': False,
            'message': f'批量保存失败: {str(e)}',
            'saved_count': 0
        }


@shared_task(name='app_ai.tasks.async_get.fetch_recent_commits_async')
def fetch_recent_commits_async(limit: int = 10, include_details: bool = True):
    """
    异步获取最近的提交记录
    
    Args:
        limit: 获取数量限制
        include_details: 是否包含详细信息和diff
        
    Returns:
        dict: 任务执行结果
    """
    return fetch_github_data_async('recent_commits', limit=limit, include_details=include_details)


@shared_task(name='app_ai.tasks.async_get.fetch_commit_details_async')
def fetch_commit_details_async(sha: str, include_diff: bool = True):
    """
    异步获取单个提交的详细信息
    
    Args:
        sha: 提交SHA
        include_diff: 是否包含diff信息
        
    Returns:
        dict: 任务执行结果
    """
    return fetch_github_data_async('commit_details', sha=sha, include_diff=include_diff)
