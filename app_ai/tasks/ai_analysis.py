"""
AI分析相关的Celery任务
简单的定时任务：检查未分析的提交，用Ollama分析后保存到数据库
"""
import logging
from celery import shared_task
from ..sql_client import DatabaseClient
from ..ollama_service import ollama_client

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue='ai_analysis')
def check_analyze_commits(self):
    """
    定时任务：检查数据库中analysis_suggestion为空的记录，用Ollama分析后保存
    """
    logger.info("开始AI分析任务")
    
    try:
        db_client = DatabaseClient()
        
        # 获取未分析的提交
        unanalyzed_commits = db_client.get_unanalyzed_commits(limit=10)
        if not unanalyzed_commits:
            logger.info("没有需要分析的提交")
            return {'status': 'success', 'message': '没有需要分析的提交'}
        
        logger.info(f"发现 {len(unanalyzed_commits)} 条未分析记录")
        
        # 检查Ollama连接
        if ollama_client.check_connection()['status'] != 'connected':
            logger.error("Ollama服务不可用")
            return {'status': 'error', 'message': 'Ollama服务不可用'}
        
        success_count = 0
        error_count = 0
        
        # 逐个分析提交
        for commit in unanalyzed_commits:
            try:
                commit_sha = commit['commit_sha']
                logger.info(f"分析提交: {commit_sha[:8]}")
                
                # 准备数据给Ollama
                ollama_data = {
                    'sha': commit_sha,
                    'message': commit.get('commit_message', ''),
                    'files': []
                }
                
                # 简单处理diff
                if commit.get('code_diff'):
                    ollama_data['files'] = [{'patch': commit['code_diff'][:2000]}]  # 限制长度
                
                # 调用Ollama分析
                result = ollama_client.explain_commit(ollama_data)
                
                if result['status'] == 'success' and result.get('response'):
                    # 保存分析结果
                    update_result = db_client.update_analysis_suggestion(
                        commit_sha, result['response']
                    )
                    
                    if update_result['success']:
                        success_count += 1
                        logger.info(f"提交 {commit_sha[:8]} 分析完成")
                    else:
                        error_count += 1
                        logger.error(f"保存失败: {commit_sha[:8]}")
                else:
                    error_count += 1
                    logger.error(f"分析失败: {commit_sha[:8]}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"处理异常: {commit.get('commit_sha', 'unknown')[:8]} - {e}")
        
        message = f'分析完成: 成功 {success_count}, 失败 {error_count}'
        logger.info(message)
        return {'status': 'success', 'message': message}
        
    except Exception as e:
        logger.error(f"任务执行异常: {e}")
        return {'status': 'error', 'message': f'任务执行异常: {e}'}
