"""
AI分析相关的Celery任务
处理代码审查、提交分析等AI任务
"""
import logging
from typing import Dict, List, Any
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta

from ..sql_client import DatabaseClient
from ..ollama_service import ollama_client

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue='ai_analysis')
def check_and_analyze_pending_commits(self):
    """
    定时任务：检查数据库中analysis_suggestion为空的记录，并进行AI分析
    
    Returns:
        dict: 执行结果统计
    """
    logger.info("开始执行定时AI分析任务")
    
    try:
        # 初始化数据库客户端
        db_client = DatabaseClient()
        
        # 获取需要分析的提交记录
        unanalyzed_commits = db_client.get_unanalyzed_commits()
        
        if not unanalyzed_commits:
            logger.info("没有需要分析的提交记录")
            return {
                'status': 'success',
                'message': '没有需要分析的提交记录',
                'total_count': 0,
                'processed_count': 0,
                'success_count': 0,
                'error_count': 0,
                'errors': []
            }
        
        logger.info(f"发现 {len(unanalyzed_commits)} 条需要分析的记录")
        
        # 检查Ollama服务状态
        connection_status = ollama_client.check_connection()
        if connection_status['status'] != 'connected':
            error_msg = f"Ollama服务不可用: {connection_status.get('error', 'Unknown error')}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'message': error_msg,
                'total_count': len(unanalyzed_commits),
                'processed_count': 0,
                'success_count': 0,
                'error_count': 0,
                'ollama_status': connection_status
            }
        
        logger.info(f"Ollama服务连接正常，可用模型: {len(connection_status.get('available_models', []))}")
        
        # 统计变量
        processed_count = 0
        success_count = 0
        error_count = 0
        errors = []
        
        # 逐个处理提交记录
        for commit in unanalyzed_commits:
            try:
                commit_sha = commit['commit_sha']
                logger.info(f"正在分析提交: {commit_sha[:8]}")
                
                # 调用单个提交分析任务
                result = analyze_single_commit_sync(commit)
                processed_count += 1
                
                if result['status'] == 'success':
                    success_count += 1
                    logger.info(f"提交 {commit_sha[:8]} 分析成功")
                else:
                    error_count += 1
                    error_msg = f"提交 {commit_sha[:8]} 分析失败: {result.get('error', 'Unknown error')}"
                    logger.error(error_msg)
                    errors.append({
                        'commit_sha': commit_sha,
                        'error': result.get('error', 'Unknown error')
                    })
                
                # 添加短暂延迟，避免过度占用资源
                import time
                time.sleep(1)
                
            except Exception as e:
                processed_count += 1
                error_count += 1
                error_msg = f"处理提交 {commit.get('commit_sha', 'unknown')[:8]} 时发生异常: {str(e)}"
                logger.error(error_msg)
                errors.append({
                    'commit_sha': commit.get('commit_sha', 'unknown'),
                    'error': str(e)
                })
        
        # 返回执行结果
        result = {
            'status': 'success' if error_count == 0 else 'partial_success',
            'message': f'定时分析完成: 成功 {success_count}, 失败 {error_count}',
            'total_count': len(unanalyzed_commits),
            'processed_count': processed_count,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors[:10],  # 只返回前10个错误
            'execution_time': timezone.now().isoformat(),
            'ollama_status': connection_status['status']
        }
        
        logger.info(f"定时AI分析任务完成: {result['message']}")
        return result
        
    except Exception as e:
        error_msg = f"定时AI分析任务执行异常: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'total_count': 0,
            'processed_count': 0,
            'success_count': 0,
            'error_count': 0,
            'errors': [{'error': str(e)}]
        }


def analyze_single_commit_sync(commit_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    同步分析单个提交记录
    
    Args:
        commit_data: 提交数据字典
        
    Returns:
        dict: 分析结果
    """
    try:
        commit_sha = commit_data['commit_sha']
        
        # 准备提交数据给Ollama
        ollama_commit_data = {
            'sha': commit_sha,
            'message': commit_data.get('commit_message', ''),
            'files': []
        }
        
        # 解析代码变更
        code_diff = commit_data.get('code_diff', '')
        if code_diff:
            # 简单解析diff，提取文件信息
            files_info = parse_git_diff(code_diff)
            ollama_commit_data['files'] = files_info
        
        # 调用Ollama进行提交分析
        logger.debug(f"调用Ollama分析提交 {commit_sha[:8]}")
        analysis_result = ollama_client.explain_commit(ollama_commit_data)
        
        if analysis_result['status'] == 'success':
            # 获取AI分析结果
            ai_suggestion = analysis_result.get('response', '')
            
            if ai_suggestion:
                # 保存分析结果到数据库
                db_client = DatabaseClient()
                update_result = db_client.update_analysis_suggestion(commit_sha, ai_suggestion)
                
                if update_result['success']:
                    return {
                        'status': 'success',
                        'message': 'AI分析完成并已保存',
                        'commit_sha': commit_sha,
                        'analysis_length': len(ai_suggestion),
                        'model_used': analysis_result.get('model_used', 'unknown')
                    }
                else:
                    return {
                        'status': 'error',
                        'error': f'数据库更新失败: {update_result.get("message", "Unknown error")}',
                        'commit_sha': commit_sha
                    }
            else:
                return {
                    'status': 'error',
                    'error': 'AI分析返回空结果',
                    'commit_sha': commit_sha
                }
        else:
            return {
                'status': 'error',
                'error': f'AI分析失败: {analysis_result.get("error", "Unknown error")}',
                'commit_sha': commit_sha
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'error': f'分析过程异常: {str(e)}',
            'commit_sha': commit_data.get('commit_sha', 'unknown')
        }


def parse_git_diff(diff_content: str) -> List[Dict[str, Any]]:
    """
    简单解析Git diff内容，提取文件变更信息
    
    Args:
        diff_content: Git diff内容
        
    Returns:
        list: 文件变更信息列表
    """
    files = []
    
    try:
        if not diff_content:
            return files
        
        # 按行分割diff内容
        lines = diff_content.split('\n')
        current_file = None
        
        for line in lines:
            line = line.strip()
            
            # 检测文件头
            if line.startswith('diff --git'):
                # 提取文件名
                parts = line.split(' ')
                if len(parts) >= 4:
                    filename = parts[3].replace('b/', '')
                    current_file = {
                        'filename': filename,
                        'status': 'modified',
                        'additions': 0,
                        'deletions': 0,
                        'patch': []
                    }
                    files.append(current_file)
            
            # 统计增删行数
            elif current_file and line.startswith('+') and not line.startswith('+++'):
                current_file['additions'] += 1
                current_file['patch'].append(line)
            elif current_file and line.startswith('-') and not line.startswith('---'):
                current_file['deletions'] += 1
                current_file['patch'].append(line)
            elif current_file and line.startswith(' '):
                current_file['patch'].append(line)
        
        # 将patch列表转换为字符串，限制长度
        for file_info in files:
            patch_lines = file_info['patch']
            if patch_lines:
                # 只保留前50行patch
                if len(patch_lines) > 50:
                    patch_lines = patch_lines[:50] + ['... (truncated)']
                file_info['patch'] = '\n'.join(patch_lines)
            else:
                file_info['patch'] = ''
        
        return files
        
    except Exception as e:
        logger.error(f"解析diff内容失败: {e}")
        return []


@shared_task(bind=True, queue='ai_analysis')
def analyze_commit_by_sha_async(self, commit_sha: str):
    """
    异步分析指定SHA的提交
    
    Args:
        commit_sha: 提交SHA
        
    Returns:
        dict: 分析结果
    """
    logger.info(f"开始异步分析提交: {commit_sha[:8]}")
    
    try:
        # 从数据库获取提交数据
        db_client = DatabaseClient()
        success, commit_data, error = db_client.get_commit_by_sha(commit_sha)
        
        if not success or not commit_data:
            error_msg = f"未找到提交记录: {commit_sha} - {error}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'commit_sha': commit_sha
            }
        
        # 执行分析
        result = analyze_single_commit_sync(commit_data)
        
        logger.info(f"异步分析完成: {commit_sha[:8]} - {result['status']}")
        return result
        
    except Exception as e:
        error_msg = f"异步分析异常: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'error': error_msg,
            'commit_sha': commit_sha
        }


@shared_task(bind=True, queue='ai_analysis')
def batch_analyze_commits_async(self, commit_shas: List[str], max_concurrent: int = 5):
    """
    批量异步分析多个提交
    
    Args:
        commit_shas: 提交SHA列表
        max_concurrent: 最大并发数
        
    Returns:
        dict: 批量分析结果
    """
    logger.info(f"开始批量异步分析 {len(commit_shas)} 个提交")
    
    try:
        results = []
        success_count = 0
        error_count = 0
        
        for i, commit_sha in enumerate(commit_shas):
            logger.info(f"批量分析进度: {i+1}/{len(commit_shas)} - {commit_sha[:8]}")
            
            # 调用单个分析任务
            result = analyze_commit_by_sha_async.apply(args=[commit_sha])
            analysis_result = result.get()
            
            results.append({
                'commit_sha': commit_sha,
                'result': analysis_result
            })
            
            if analysis_result['status'] == 'success':
                success_count += 1
            else:
                error_count += 1
            
            # 添加延迟避免过载
            if i < len(commit_shas) - 1:
                import time
                time.sleep(2)
        
        summary = {
            'status': 'success' if error_count == 0 else 'partial_success',
            'message': f'批量分析完成: 成功 {success_count}, 失败 {error_count}',
            'total_count': len(commit_shas),
            'success_count': success_count,
            'error_count': error_count,
            'results': results,
            'execution_time': timezone.now().isoformat()
        }
        
        logger.info(f"批量异步分析完成: {summary['message']}")
        return summary
        
    except Exception as e:
        error_msg = f"批量分析异常: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'error': error_msg,
            'total_count': len(commit_shas),
            'success_count': 0,
            'error_count': len(commit_shas)
        }
