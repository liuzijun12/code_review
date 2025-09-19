"""
企业微信推送相关的Celery任务
定时检查数据库中未推送的分析记录并推送到企业微信
"""
import logging
from celery import shared_task
from django.utils import timezone
from ..info_push import wechat_pusher

logger = logging.getLogger(__name__)


@shared_task(name='wx_push.check_and_push_messages')
def check_and_push_messages():
    """
    定时检查数据库中是否有未推送的分析记录，如果有则推送到企业微信
    
    Returns:
        dict: 推送结果统计
    """
    try:
        logger.info("开始执行定时企业微信推送任务")
        
        # 检查推送器是否可用
        if not wechat_pusher:
            logger.error("企业微信推送器未初始化，跳过推送")
            return {
                'status': 'error',
                'message': '企业微信推送器未初始化',
                'execution_time': timezone.now().isoformat()
            }
        
        # 执行推送（最多推送3条记录）
        result = wechat_pusher.push_unpushed_analysis(limit=3)
        
        # 添加执行时间到结果中
        result['execution_time'] = timezone.now().isoformat()
        
        if result['total_count'] > 0:
            logger.info(f"定时推送任务完成: 成功 {result['success_count']}, 失败 {result['error_count']}")
        else:
            logger.info("定时推送任务完成: 没有需要推送的记录")
        
        return result
        
    except Exception as e:
        error_msg = f"定时推送任务异常: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'total_count': 0,
            'success_count': 0,
            'error_count': 0,
            'execution_time': timezone.now().isoformat()
        }


@shared_task(name='wx_push.push_single_commit_task')
def push_single_commit_task(commit_sha: str):
    """
    推送单个提交的分析结果（异步任务版本）
    
    Args:
        commit_sha: 提交SHA
        
    Returns:
        dict: 推送结果
    """
    try:
        logger.info(f"开始推送单个提交任务: {commit_sha[:8]}")
        
        # 检查推送器是否可用
        if not wechat_pusher:
            logger.error("企业微信推送器未初始化，跳过推送")
            return {
                'status': 'error',
                'message': '企业微信推送器未初始化',
                'commit_sha': commit_sha,
                'execution_time': timezone.now().isoformat()
            }
        
        # 执行单个提交推送
        success = wechat_pusher.push_single_commit(commit_sha)
        
        result = {
            'status': 'success' if success else 'failed',
            'message': f"提交 {commit_sha[:8]} {'推送成功' if success else '推送失败'}",
            'commit_sha': commit_sha,
            'success': success,
            'execution_time': timezone.now().isoformat()
        }
        
        logger.info(f"单个提交推送任务完成: {result['message']}")
        return result
        
    except Exception as e:
        error_msg = f"单个提交推送任务异常: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'commit_sha': commit_sha,
            'success': False,
            'execution_time': timezone.now().isoformat()
        }


@shared_task(name='wx_push.send_summary_report_task')
def send_summary_report_task():
    """
    发送系统状态总结报告（异步任务版本）
    
    Returns:
        dict: 发送结果
    """
    try:
        logger.info("开始发送系统状态总结报告任务")
        
        # 检查推送器是否可用
        if not wechat_pusher:
            logger.error("企业微信推送器未初始化，跳过报告发送")
            return {
                'status': 'error',
                'message': '企业微信推送器未初始化',
                'execution_time': timezone.now().isoformat()
            }
        
        # 发送总结报告
        success = wechat_pusher.send_summary_report()
        
        result = {
            'status': 'success' if success else 'failed',
            'message': f"系统状态报告{'发送成功' if success else '发送失败'}",
            'success': success,
            'execution_time': timezone.now().isoformat()
        }
        
        logger.info(f"系统状态报告任务完成: {result['message']}")
        return result
        
    except Exception as e:
        error_msg = f"系统状态报告任务异常: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'success': False,
            'execution_time': timezone.now().isoformat()
        }
