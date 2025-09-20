"""
异步Ollama分析任务模块
在Git数据获取完成后自动触发AI分析
"""
import logging
from celery import shared_task
from django.utils import timezone
from ..sql_client import DatabaseClient
from ..ollama_client import OllamaClient

logger = logging.getLogger(__name__)


@shared_task(name='app_ai.tasks.async_ollama.analyze_commits_async')
def analyze_commits_async(commit_shas=None, auto_trigger=True):
    """
    异步分析提交记录
    
    Args:
        commit_shas: 指定要分析的提交SHA列表，如果为None则分析所有未分析的提交
        auto_trigger: 是否为自动触发（Git请求完成后）
        
    Returns:
        dict: 分析结果统计
    """
    try:
        start_time = timezone.now()
        logger.info(f"开始异步Ollama分析任务，自动触发: {auto_trigger}")
        
        # 获取要分析的提交
        if commit_shas:
            # 分析指定的提交
            commits_to_analyze = []
            for sha in commit_shas:
                unanalyzed = DatabaseClient.get_unanalyzed_commits(limit=100)
                for commit in unanalyzed:
                    if commit['commit_sha'] == sha:
                        commits_to_analyze.append(commit)
                        break
            logger.info(f"指定分析 {len(commits_to_analyze)} 个提交")
        else:
            # 获取所有未分析的提交
            commits_to_analyze = DatabaseClient.get_unanalyzed_commits(limit=50)
            logger.info(f"自动分析 {len(commits_to_analyze)} 个未分析提交")
        
        if not commits_to_analyze:
            logger.info("没有需要分析的提交")
            return {
                'status': 'success',
                'message': '没有需要分析的提交',
                'analyzed_count': 0,
                'failed_count': 0,
                'execution_time': (timezone.now() - start_time).total_seconds()
            }
        
        # 初始化Ollama客户端
        ollama_client = OllamaClient()
        
        # 检查Ollama服务状态
        status_check = ollama_client.check_connection()
        if status_check['status'] != 'connected':
            logger.error(f"Ollama服务不可用: {status_check.get('error', 'Unknown error')}")
            logger.error(f"连接状态详情: {status_check}")
            return {
                'status': 'error',
                'message': f"Ollama服务不可用: {status_check.get('error', 'Unknown error')}",
                'analyzed_count': 0,
                'failed_count': len(commits_to_analyze),
                'execution_time': (timezone.now() - start_time).total_seconds(),
                'connection_details': status_check
            }
        
        logger.info("Ollama服务连接正常，开始分析")
        
        # 分析统计
        analyzed_count = 0
        failed_count = 0
        analysis_results = []
        
        # 逐个分析提交
        for commit in commits_to_analyze:
            try:
                commit_sha = commit['commit_sha']
                logger.info(f"分析提交: {commit_sha[:8]}")
                
                # 准备Ollama分析数据
                ollama_data = {
                    'sha': commit_sha,
                    'message': commit.get('commit_message', ''),
                    'author': commit.get('author_name', ''),
                    'files': []
                }
                
                # 添加代码差异（完整内容，无长度限制）
                if commit.get('code_diff'):
                    ollama_data['files'] = [{'patch': commit['code_diff']}]
                
                # 调用Ollama进行分析
                logger.info(f"🤖 开始调用Ollama分析提交: {commit_sha[:8]}")
                logger.info(f"📊 数据准备完成: 消息长度={len(ollama_data.get('message', ''))}, 文件数={len(ollama_data.get('files', []))}")
                
                result = ollama_client.explain_commit(ollama_data)
                
                logger.info(f"🎯 Ollama分析完成: {commit_sha[:8]}, 状态={result.get('status', 'unknown')}")
                
                if result['status'] == 'success' and result.get('response'):
                    # 保存分析结果到数据库
                    analysis_suggestion = result['response']
                    update_result = DatabaseClient.update_analysis_suggestion(
                        commit_sha, analysis_suggestion
                    )
                    
                    if update_result['success']:
                        analyzed_count += 1
                        logger.info(f"✅ 提交 {commit_sha[:8]} 分析完成")
                        analysis_results.append({
                            'commit_sha': commit_sha,
                            'status': 'success',
                            'analysis_length': len(analysis_suggestion)
                        })
                    else:
                        failed_count += 1
                        logger.error(f"❌ 提交 {commit_sha[:8]} 分析结果保存失败: {update_result['message']}")
                        analysis_results.append({
                            'commit_sha': commit_sha,
                            'status': 'save_failed',
                            'error': update_result['message']
                        })
                else:
                    failed_count += 1
                    error_msg = result.get('error', 'AI分析失败')
                    logger.error(f"❌ 提交 {commit_sha[:8]} AI分析失败: {error_msg}")
                    analysis_results.append({
                        'commit_sha': commit_sha,
                        'status': 'analysis_failed',
                        'error': error_msg
                    })
                    
            except Exception as commit_error:
                failed_count += 1
                logger.error(f"❌ 处理提交 {commit.get('commit_sha', 'unknown')[:8]} 时出错: {commit_error}")
                analysis_results.append({
                    'commit_sha': commit.get('commit_sha', 'unknown'),
                    'status': 'exception',
                    'error': str(commit_error)
                })
        
        execution_time = (timezone.now() - start_time).total_seconds()
        
        # 返回分析结果
        result = {
            'status': 'success',
            'message': f'Ollama分析完成: 成功 {analyzed_count}, 失败 {failed_count}',
            'analyzed_count': analyzed_count,
            'failed_count': failed_count,
            'total_commits': len(commits_to_analyze),
            'execution_time': execution_time,
            'auto_trigger': auto_trigger,
            'analysis_results': analysis_results
        }
        
        logger.info(f"🎉 异步Ollama分析任务完成: {result['message']}, 耗时: {execution_time:.2f}秒")
        
        # 如果有成功分析的提交，自动触发推送任务
        if analyzed_count > 0:
            try:
                from .async_push import auto_push_after_ollama
                push_task = auto_push_after_ollama.delay(result)
                logger.info(f"📱 自动触发推送任务: {push_task.id}")
                
                # 在结果中添加推送任务信息
                result['push_task'] = {
                    'triggered': True,
                    'task_id': push_task.id,
                    'message': f'已自动触发 {analyzed_count} 个分析结果的推送'
                }
            except Exception as push_error:
                logger.error(f"触发推送任务失败: {push_error}")
                result['push_task'] = {
                    'triggered': False,
                    'error': str(push_error),
                    'message': '推送任务触发失败'
                }
        else:
            result['push_task'] = {
                'triggered': False,
                'message': '没有成功分析的提交，跳过推送'
            }
        
        return result
        
    except Exception as e:
        error_msg = f"异步Ollama分析任务失败: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'analyzed_count': 0,
            'failed_count': 0,
            'execution_time': (timezone.now() - start_time).total_seconds() if 'start_time' in locals() else 0,
            'error': str(e)
        }


@shared_task(name='app_ai.tasks.async_ollama.analyze_single_commit_async')
def analyze_single_commit_async(commit_sha):
    """
    异步分析单个提交
    
    Args:
        commit_sha: 要分析的提交SHA
        
    Returns:
        dict: 分析结果
    """
    logger.info(f"开始异步分析单个提交: {commit_sha[:8]}")
    return analyze_commits_async(commit_shas=[commit_sha], auto_trigger=False)


@shared_task(name='app_ai.tasks.async_ollama.auto_analyze_after_git_fetch')
def auto_analyze_after_git_fetch(git_task_result):
    """
    Git数据获取完成后自动触发Ollama分析
    
    Args:
        git_task_result: Git异步任务的结果
        
    Returns:
        dict: 分析结果
    """
    try:
        logger.info("Git数据获取完成，自动触发Ollama分析")
        
        # 检查Git任务是否成功
        if not git_task_result or git_task_result.get('status') != 'success':
            logger.warning(f"Git任务未成功完成，跳过Ollama分析: {git_task_result}")
            return {
                'status': 'skipped',
                'message': 'Git任务未成功完成，跳过Ollama分析',
                'git_task_result': git_task_result
            }
        
        # 获取新保存的提交SHA列表
        saved_commits = []
        if 'database_save' in git_task_result:
            db_save = git_task_result['database_save']
            if db_save.get('success') and 'saved_commits' in db_save:
                saved_commits = db_save['saved_commits']
        
        if saved_commits:
            logger.info(f"自动分析新保存的 {len(saved_commits)} 个提交")
            # 分析新保存的提交
            return analyze_commits_async(commit_shas=saved_commits, auto_trigger=True)
        else:
            logger.info("没有新保存的提交，分析所有未分析的提交")
            # 分析所有未分析的提交
            return analyze_commits_async(commit_shas=None, auto_trigger=True)
            
    except Exception as e:
        error_msg = f"自动Ollama分析触发失败: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'error': str(e),
            'git_task_result': git_task_result
        }


def trigger_ollama_analysis_after_git(git_task_id):
    """
    在Git任务完成后触发Ollama分析的便捷函数
    
    Args:
        git_task_id: Git异步任务的ID
        
    Returns:
        AsyncResult: Ollama分析任务的结果对象
    """
    from celery.result import AsyncResult
    
    # 获取Git任务结果
    git_task = AsyncResult(git_task_id)
    
    if git_task.ready():
        # Git任务已完成，立即触发Ollama分析
        git_result = git_task.result
        return auto_analyze_after_git_fetch.delay(git_result)
    else:
        # Git任务未完成，等待完成后触发
        logger.info(f"Git任务 {git_task_id} 未完成，等待完成后触发Ollama分析")
        # 这里可以使用Celery的链式任务，但为了简单起见，先返回None
        return None


# 便捷函数
def start_ollama_analysis(commit_shas=None):
    """
    启动Ollama分析任务的便捷函数
    
    Args:
        commit_shas: 要分析的提交SHA列表，None表示分析所有未分析的提交
        
    Returns:
        AsyncResult: 任务结果对象
    """
    return analyze_commits_async.delay(commit_shas, auto_trigger=False)


def start_single_commit_analysis(commit_sha):
    """
    启动单个提交分析的便捷函数
    
    Args:
        commit_sha: 要分析的提交SHA
        
    Returns:
        AsyncResult: 任务结果对象
    """
    return analyze_single_commit_async.delay(commit_sha)
