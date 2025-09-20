"""
异步推送消息模块
在Ollama分析完成后自动触发企业微信推送
"""
import logging
import time
from celery import shared_task
from django.utils import timezone
from ..sql_client import DatabaseClient
from ..info_push import WeChatWorkPusher

logger = logging.getLogger(__name__)


@shared_task(name='app_ai.tasks.async_push.push_analysis_results')
def push_analysis_results(ollama_task_result=None, delay_seconds=3):
    """
    推送分析结果到企业微信
    
    Args:
        ollama_task_result: Ollama分析任务的结果
        delay_seconds: 多条消息之间的延迟时间（秒）
        
    Returns:
        dict: 推送结果统计
    """
    try:
        start_time = timezone.now()
        logger.info("开始异步推送分析结果到企业微信")
        
        # 获取需要推送的数据（已分析且未推送的记录）
        from app_ai.models import GitCommitAnalysis
        
        # 查询条件：analysis_suggestion不为空且is_push为0
        unpushed_records = GitCommitAnalysis.objects.filter(
            analysis_suggestion__isnull=False,
            is_push=0
        ).exclude(
            analysis_suggestion=''
        ).order_by('commit_timestamp')  # 按提交时间排序，先提交的先发送
        
        if not unpushed_records.exists():
            logger.info("没有需要推送的分析结果")
            return {
                'status': 'success',
                'message': '没有需要推送的分析结果',
                'pushed_count': 0,
                'failed_count': 0,
                'execution_time': (timezone.now() - start_time).total_seconds()
            }
        
        logger.info(f"找到 {unpushed_records.count()} 条需要推送的分析结果")
        
        # 初始化推送器
        pusher = WeChatWorkPusher()
        
        # 推送统计
        pushed_count = 0
        failed_count = 0
        push_results = []
        
        # 逐条推送，按时间顺序
        for index, record in enumerate(unpushed_records):
            try:
                logger.info(f"推送第 {index + 1}/{unpushed_records.count()} 条: {record.commit_sha[:8]}")
                
                # 准备推送数据
                push_data = {
                    'commit_sha': record.commit_sha,
                    'short_sha': record.commit_sha[:8],
                    'author_name': record.author_name,
                    'commit_message': record.commit_message,
                    'commit_timestamp': record.commit_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'analysis_suggestion': record.analysis_suggestion,
                    'code_diff_length': len(record.code_diff) if record.code_diff else 0
                }
                
                # 调用推送方法
                push_result = pusher.push_single_commit_data(push_data)
                
                if push_result.get('success', False):
                    # 推送成功，更新is_push状态
                    record.is_push = 1
                    record.save()
                    
                    pushed_count += 1
                    logger.info(f"✅ 提交 {record.commit_sha[:8]} 推送成功")
                    
                    push_results.append({
                        'commit_sha': record.commit_sha,
                        'status': 'success',
                        'message': push_result.get('message', 'Push successful')
                    })
                    
                else:
                    failed_count += 1
                    error_msg = push_result.get('message', 'Unknown error')
                    logger.error(f"❌ 提交 {record.commit_sha[:8]} 推送失败: {error_msg}")
                    
                    push_results.append({
                        'commit_sha': record.commit_sha,
                        'status': 'failed',
                        'error': error_msg
                    })
                
                # 如果不是最后一条记录，等待指定时间
                if index < unpushed_records.count() - 1:
                    logger.info(f"等待 {delay_seconds} 秒后发送下一条消息...")
                    time.sleep(delay_seconds)
                    
            except Exception as record_error:
                failed_count += 1
                logger.error(f"❌ 处理提交 {record.commit_sha[:8]} 时出错: {record_error}")
                push_results.append({
                    'commit_sha': record.commit_sha,
                    'status': 'exception',
                    'error': str(record_error)
                })
        
        execution_time = (timezone.now() - start_time).total_seconds()
        
        # 返回推送结果
        result = {
            'status': 'success',
            'message': f'推送完成: 成功 {pushed_count}, 失败 {failed_count}',
            'pushed_count': pushed_count,
            'failed_count': failed_count,
            'total_records': unpushed_records.count(),
            'execution_time': execution_time,
            'delay_seconds': delay_seconds,
            'push_results': push_results,
            'ollama_trigger': ollama_task_result is not None
        }
        
        logger.info(f"🎉 异步推送任务完成: {result['message']}, 耗时: {execution_time:.2f}秒")
        return result
        
    except Exception as e:
        error_msg = f"异步推送任务失败: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'pushed_count': 0,
            'failed_count': 0,
            'execution_time': (timezone.now() - start_time).total_seconds() if 'start_time' in locals() else 0,
            'error': str(e)
        }


@shared_task(name='app_ai.tasks.async_push.auto_push_after_ollama')
def auto_push_after_ollama(ollama_task_result):
    """
    Ollama分析完成后自动触发推送
    
    Args:
        ollama_task_result: Ollama分析任务的结果
        
    Returns:
        dict: 推送结果
    """
    try:
        logger.info("Ollama分析完成，自动触发推送任务")
        
        # 检查Ollama任务是否成功
        if not ollama_task_result or ollama_task_result.get('status') != 'success':
            logger.warning(f"Ollama任务未成功完成，跳过推送: {ollama_task_result}")
            return {
                'status': 'skipped',
                'message': 'Ollama任务未成功完成，跳过推送',
                'ollama_task_result': ollama_task_result
            }
        
        analyzed_count = ollama_task_result.get('analyzed_count', 0)
        if analyzed_count > 0:
            logger.info(f"Ollama成功分析了 {analyzed_count} 个提交，开始推送")
            # 启动推送任务
            return push_analysis_results(ollama_task_result, delay_seconds=3)
        else:
            logger.info("Ollama没有成功分析任何提交，跳过推送")
            return {
                'status': 'skipped',
                'message': 'Ollama没有成功分析任何提交，跳过推送',
                'analyzed_count': analyzed_count
            }
            
    except Exception as e:
        error_msg = f"自动推送触发失败: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'error': str(e),
            'ollama_task_result': ollama_task_result
        }


@shared_task(name='app_ai.tasks.async_push.manual_push_all')
def manual_push_all(delay_seconds=3):
    """
    手动推送所有未推送的分析结果
    
    Args:
        delay_seconds: 多条消息之间的延迟时间（秒）
        
    Returns:
        dict: 推送结果
    """
    logger.info("手动触发推送所有未推送的分析结果")
    return push_analysis_results(ollama_task_result=None, delay_seconds=delay_seconds)


# 便捷函数
def start_push_task(delay_seconds=3):
    """
    启动推送任务的便捷函数
    
    Args:
        delay_seconds: 多条消息之间的延迟时间（秒）
        
    Returns:
        AsyncResult: 任务结果对象
    """
    return manual_push_all.delay(delay_seconds)


def trigger_push_after_ollama(ollama_task_id):
    """
    在Ollama任务完成后触发推送的便捷函数
    
    Args:
        ollama_task_id: Ollama任务的ID
        
    Returns:
        AsyncResult: 推送任务的结果对象
    """
    from celery.result import AsyncResult
    
    # 获取Ollama任务结果
    ollama_task = AsyncResult(ollama_task_id)
    
    if ollama_task.ready():
        # Ollama任务已完成，立即触发推送
        ollama_result = ollama_task.result
        return auto_push_after_ollama.delay(ollama_result)
    else:
        # Ollama任务未完成，等待完成后触发
        logger.info(f"Ollama任务 {ollama_task_id} 未完成，等待完成后触发推送")
        return None
