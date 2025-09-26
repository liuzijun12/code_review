"""
异步推送消息模块
在Ollama分析完成后自动触发企业微信推送
"""
import logging
import time
from celery import shared_task
from django.utils import timezone
from ..info_push import WeChatWorkPusher

logger = logging.getLogger(__name__)


@shared_task(name='app_ai.tasks.async_push.push_analysis_results')
def push_analysis_results(ollama_task_result=None, delay_seconds=3, repo_owner=None, repo_name=None):
    """
    推送分析结果到企业微信
    
    Args:
        ollama_task_result: Ollama分析任务的结果
        delay_seconds: 多条消息之间的延迟时间（秒）
        repo_owner: 仓库所有者用户名
        repo_name: 仓库名称
        
    Returns:
        dict: 推送结果统计
    """
    try:
        start_time = timezone.now()
        logger.info("开始异步推送分析结果到企业微信")
        
        # 数据库存储功能已禁用
        unpushed_records = []
        
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
        
        # 初始化推送器（使用仓库信息）
        pusher = WeChatWorkPusher(repo_owner=repo_owner, repo_name=repo_name)
        
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
def auto_push_after_ollama(ollama_task_result, repo_owner=None, repo_name=None):
    """
    Ollama分析完成后自动触发推送
    
    Args:
        ollama_task_result: Ollama分析任务的结果
        repo_owner: 仓库所有者用户名
        repo_name: 仓库名称
        
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
            return push_analysis_results(ollama_task_result, delay_seconds=3, repo_owner=repo_owner, repo_name=repo_name)
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


@shared_task(name='app_ai.tasks.async_push.push_single_analysis_result')
def push_single_analysis_result(analysis_data, repo_owner=None, repo_name=None):
    """
    推送单个分析结果到企业微信（不依赖数据库）
    
    Args:
        analysis_data: 包含分析结果的字典
        repo_owner: 仓库所有者用户名
        repo_name: 仓库名称
        
    Returns:
        dict: 推送结果
    """
    try:
        start_time = timezone.now()
        logger.info("开始推送单个分析结果到企业微信")
        
        # 验证必要字段
        required_fields = ['commit_sha', 'commit_message', 'author_name', 'analysis_suggestion']
        for field in required_fields:
            if not analysis_data.get(field):
                logger.error(f"分析数据缺少必要字段: {field}")
                return {
                    'status': 'error',
                    'message': f'分析数据缺少必要字段: {field}',
                    'execution_time': (timezone.now() - start_time).total_seconds()
                }
        
        # 初始化推送器（使用仓库信息）
        pusher = WeChatWorkPusher(repo_owner=repo_owner, repo_name=repo_name)
        
        # 格式化消息
        commit_sha = analysis_data['commit_sha']
        message = _format_single_analysis_message(analysis_data)
        
        if not message:
            logger.error(f"消息格式化失败: {commit_sha[:8]}")
            return {
                'status': 'error',
                'message': '消息格式化失败',
                'execution_time': (timezone.now() - start_time).total_seconds()
            }
        
        # 发送消息
        success = pusher.send_to_wechat(message)
        
        if success:
            logger.info(f"单个分析结果推送成功: {commit_sha[:8]}")
            return {
                'status': 'success',
                'message': f'提交 {commit_sha[:8]} 分析结果推送成功',
                'commit_sha': commit_sha,
                'pushed_count': 1,
                'execution_time': (timezone.now() - start_time).total_seconds()
            }
        else:
            logger.error(f"单个分析结果推送失败: {commit_sha[:8]}")
            return {
                'status': 'error',
                'message': f'提交 {commit_sha[:8]} 分析结果推送失败',
                'commit_sha': commit_sha,
                'execution_time': (timezone.now() - start_time).total_seconds()
            }
            
    except Exception as e:
        error_msg = f"推送单个分析结果异常: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'error': str(e),
            'execution_time': (timezone.now() - start_time).total_seconds() if 'start_time' in locals() else 0
        }


def _format_single_analysis_message(analysis_data):
    """格式化单个分析结果消息"""
    try:
        commit_sha = analysis_data['commit_sha']
        repository_name = analysis_data.get('repository_name', 'Unknown Repository')
        commit_message = analysis_data['commit_message']
        author_name = analysis_data['author_name']
        commit_date = analysis_data.get('commit_date', 'Unknown Date')
        modified_files = analysis_data.get('modified_files', [])
        stats = analysis_data.get('stats', {})
        commit_url = analysis_data.get('commit_url', '')
        analysis_suggestion = analysis_data['analysis_suggestion']
        
        # 构造文件变更信息
        files_info = ""
        if modified_files:
            files_info = "\n**📁 修改文件:**\n"
            for file_info in modified_files[:5]:  # 最多显示5个文件
                filename = file_info.get('filename', 'Unknown')
                status = file_info.get('status', 'modified')
                additions = file_info.get('additions', 0)
                deletions = file_info.get('deletions', 0)
                
                status_emoji = {'added': '➕', 'removed': '➖', 'modified': '📝'}.get(status, '📝')
                files_info += f"- {status_emoji} `{filename}` (+{additions}/-{deletions})\n"
            
            if len(modified_files) > 5:
                files_info += f"- ... 还有 {len(modified_files) - 5} 个文件\n"
        
        # 构造统计信息
        stats_info = ""
        if stats:
            total_additions = stats.get('total_additions', 0)
            total_deletions = stats.get('total_deletions', 0)
            files_changed = stats.get('files_changed', 0)
            stats_info = f"\n**📊 变更统计:** {files_changed} 个文件，+{total_additions}/-{total_deletions}\n"
        
        # 格式化时间
        try:
            from datetime import datetime
            commit_datetime = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
            formatted_date = commit_datetime.strftime('%Y-%m-%d %H:%M:%S')
        except:
            formatted_date = commit_date
        
        # 构造完整消息内容
        markdown_content = f"""# 🤖 代码审查报告

**📦 仓库:** {repository_name}
**👤 作者:** {author_name}
**🕐 时间:** {formatted_date}
**🔗 链接:** [查看提交]({commit_url})

## 📝 提交信息
```
{commit_message}
```

## 🔍 AI 分析建议
{analysis_suggestion}
{files_info}{stats_info}
---
*提交 SHA: `{commit_sha[:8]}...`*"""

        # 返回企业微信 Markdown 消息格式
        return {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_content.strip()
            }
        }
        
    except Exception as e:
        logger.error(f"格式化消息异常: {e}")
        return None


@shared_task(name='app_ai.tasks.async_push.manual_push_all')
def manual_push_all(delay_seconds=3, repo_owner=None, repo_name=None):
    """
    手动推送所有未推送的分析结果
    
    Args:
        delay_seconds: 多条消息之间的延迟时间（秒）
        repo_owner: 仓库所有者用户名
        repo_name: 仓库名称
        
    Returns:
        dict: 推送结果
    """
    logger.info("手动触发推送所有未推送的分析结果")
    return push_analysis_results(ollama_task_result=None, delay_seconds=delay_seconds, repo_owner=repo_owner, repo_name=repo_name)


# 便捷函数
def start_push_task(delay_seconds=3, repo_owner=None, repo_name=None):
    """
    启动推送任务的便捷函数
    
    Args:
        delay_seconds: 多条消息之间的延迟时间（秒）
        repo_owner: 仓库所有者用户名
        repo_name: 仓库名称
        
    Returns:
        AsyncResult: 任务结果对象
    """
    return manual_push_all.delay(delay_seconds, repo_owner=repo_owner, repo_name=repo_name)


def trigger_push_after_ollama(ollama_task_id, repo_owner=None, repo_name=None):
    """
    在Ollama任务完成后触发推送的便捷函数
    
    Args:
        ollama_task_id: Ollama任务的ID
        repo_owner: 仓库所有者用户名
        repo_name: 仓库名称
        
    Returns:
        AsyncResult: 推送任务的结果对象
    """
    from celery.result import AsyncResult
    
    # 获取Ollama任务结果
    ollama_task = AsyncResult(ollama_task_id)
    
    if ollama_task.ready():
        # Ollama任务已完成，立即触发推送
        ollama_result = ollama_task.result
        return auto_push_after_ollama.delay(ollama_result, repo_owner=repo_owner, repo_name=repo_name)
    else:
        # Ollama任务未完成，等待完成后触发
        logger.info(f"Ollama任务 {ollama_task_id} 未完成，等待完成后触发推送")
        return None
