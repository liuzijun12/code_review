#!/usr/bin/env python3
"""
AI分析服务模块
处理代码审查和提交分析，集成Ollama服务
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from .ollama_client import ollama_client
from .config import ollama_config

# 创建logger实例
logger = logging.getLogger(__name__)


class AIAnalysisService:
    """AI分析服务，处理代码审查和提交分析"""
    
    def __init__(self):
        """初始化AI分析服务"""
        self.ollama_client = ollama_client
        self.config = ollama_config.get_config()
        logger.info("AI分析服务初始化完成")
    
    def analyze_commit_data(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析单个提交数据
        
        Args:
            commit_data: 提交数据，包含SHA、消息、文件变更等信息
            
        Returns:
            dict: 分析结果，包含AI分析建议
        """
        try:
            commit_sha = commit_data.get('sha', 'unknown')
            logger.info(f"开始分析提交: {commit_sha[:8]}")
            
            # 构造提交分析数据
            analysis_data = {
                'sha': commit_sha,
                'message': commit_data.get('commit', {}).get('message', ''),
                'author': commit_data.get('commit', {}).get('author', {}).get('name', ''),
                'timestamp': commit_data.get('commit', {}).get('author', {}).get('date', ''),
                'files': []
            }
            
            # 处理文件变更信息
            files_data = commit_data.get('files', [])
            if files_data:
                for file_info in files_data:
                    file_data = {
                        'filename': file_info.get('filename', ''),
                        'status': file_info.get('status', ''),
                        'additions': file_info.get('additions', 0),
                        'deletions': file_info.get('deletions', 0),
                        'patch': file_info.get('patch', '')
                    }
                    analysis_data['files'].append(file_data)
            
            # 使用Ollama进行提交分析
            logger.info(f"使用Ollama分析提交: {commit_sha[:8]}")
            start_time = time.time()
            
            ollama_result = self.ollama_client.explain_commit(
                commit_data=analysis_data,
                model_name=self.config.default_commit_analysis_model
            )
            
            analysis_time = time.time() - start_time
            
            if ollama_result['status'] == 'success':
                logger.info(f"提交分析完成: {commit_sha[:8]}, 耗时: {analysis_time:.1f}秒")
                
                # 构造分析结果
                analysis_result = {
                    'status': 'success',
                    'commit_sha': commit_sha,
                    'analysis_suggestion': ollama_result.get('response', ''),
                    'analysis_metadata': {
                        'model_used': ollama_result.get('model_used', ''),
                        'analysis_time': analysis_time,
                        'files_count': ollama_result.get('files_count', 0),
                        'analysis_type': 'commit_explanation',
                        'timestamp': time.time()
                    }
                }
                
                # 如果有性能统计，添加到元数据
                if 'total_duration' in ollama_result:
                    analysis_result['analysis_metadata']['model_inference_time'] = ollama_result['total_duration'] / 1000000  # 纳秒转毫秒
                
                return analysis_result
                
            else:
                error_msg = f"Ollama分析失败: {ollama_result.get('error', 'Unknown error')}"
                logger.error(f"提交分析失败: {commit_sha[:8]} - {error_msg}")
                
                return {
                    'status': 'error',
                    'commit_sha': commit_sha,
                    'error': error_msg,
                    'analysis_suggestion': None
                }
                
        except Exception as e:
            error_msg = f"分析提交时发生异常: {str(e)}"
            logger.error(f"提交分析异常: {commit_data.get('sha', 'unknown')[:8]} - {error_msg}")
            
            return {
                'status': 'error',
                'commit_sha': commit_data.get('sha', 'unknown'),
                'error': error_msg,
                'analysis_suggestion': None
            }
    
    def analyze_code_diff(self, file_info: Dict[str, Any], commit_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        分析单个文件的代码变更
        
        Args:
            file_info: 文件信息，包含patch、文件名等
            commit_context: 提交上下文信息
            
        Returns:
            dict: 代码分析结果
        """
        try:
            filename = file_info.get('filename', 'unknown')
            patch = file_info.get('patch', '')
            
            if not patch:
                return {
                    'status': 'skipped',
                    'filename': filename,
                    'reason': 'No patch data available'
                }
            
            logger.info(f"开始分析文件代码变更: {filename}")
            
            # 构造代码审查内容
            code_content = f"""
文件名: {filename}
状态: {file_info.get('status', 'unknown')}
添加行数: {file_info.get('additions', 0)}
删除行数: {file_info.get('deletions', 0)}

代码变更:
{patch}
"""
            
            # 如果有提交上下文，添加到分析中
            if commit_context:
                code_content = f"""
提交信息: {commit_context.get('message', '')}
提交作者: {commit_context.get('author', '')}

{code_content}
"""
            
            # 使用Ollama进行代码审查
            start_time = time.time()
            
            ollama_result = self.ollama_client.code_review(
                code_content=code_content,
                model_name=self.config.default_code_review_model
            )
            
            analysis_time = time.time() - start_time
            
            if ollama_result['status'] == 'success':
                logger.info(f"文件代码分析完成: {filename}, 耗时: {analysis_time:.1f}秒")
                
                return {
                    'status': 'success',
                    'filename': filename,
                    'code_review': ollama_result.get('response', ''),
                    'analysis_metadata': {
                        'model_used': ollama_result.get('model_used', ''),
                        'analysis_time': analysis_time,
                        'code_length': ollama_result.get('code_length', 0),
                        'analysis_type': 'code_review'
                    }
                }
            else:
                error_msg = f"代码审查失败: {ollama_result.get('error', 'Unknown error')}"
                logger.error(f"文件代码分析失败: {filename} - {error_msg}")
                
                return {
                    'status': 'error',
                    'filename': filename,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"分析文件代码时发生异常: {str(e)}"
            logger.error(f"文件代码分析异常: {file_info.get('filename', 'unknown')} - {error_msg}")
            
            return {
                'status': 'error',
                'filename': file_info.get('filename', 'unknown'),
                'error': error_msg
            }
    
    def batch_analyze_commits(self, commits_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量分析多个提交
        
        Args:
            commits_data: 提交数据列表
            
        Returns:
            dict: 批量分析结果
        """
        logger.info(f"开始批量分析 {len(commits_data)} 个提交")
        
        results = []
        success_count = 0
        error_count = 0
        total_analysis_time = 0
        
        for i, commit_data in enumerate(commits_data, 1):
            commit_sha = commit_data.get('sha', f'unknown_{i}')
            logger.info(f"分析进度: {i}/{len(commits_data)} - {commit_sha[:8]}")
            
            try:
                # 分析单个提交
                analysis_result = self.analyze_commit_data(commit_data)
                results.append(analysis_result)
                
                if analysis_result['status'] == 'success':
                    success_count += 1
                    if 'analysis_metadata' in analysis_result:
                        total_analysis_time += analysis_result['analysis_metadata'].get('analysis_time', 0)
                else:
                    error_count += 1
                
                # 避免请求过快
                if i < len(commits_data):  # 不是最后一个
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"批量分析异常: {commit_sha[:8]} - {e}")
                results.append({
                    'status': 'error',
                    'commit_sha': commit_sha,
                    'error': f'批量分析异常: {str(e)}'
                })
                error_count += 1
        
        batch_result = {
            'status': 'completed',
            'total_commits': len(commits_data),
            'success_count': success_count,
            'error_count': error_count,
            'total_analysis_time': total_analysis_time,
            'average_analysis_time': total_analysis_time / success_count if success_count > 0 else 0,
            'results': results
        }
        
        logger.info(f"批量分析完成: {success_count}/{len(commits_data)} 成功, 总耗时: {total_analysis_time:.1f}秒")
        
        return batch_result
    
    def get_analysis_summary(self, analysis_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成分析摘要
        
        Args:
            analysis_results: 分析结果列表
            
        Returns:
            dict: 分析摘要
        """
        total_count = len(analysis_results)
        success_count = sum(1 for result in analysis_results if result.get('status') == 'success')
        error_count = total_count - success_count
        
        # 统计使用的模型
        models_used = {}
        total_analysis_time = 0
        
        for result in analysis_results:
            if result.get('status') == 'success' and 'analysis_metadata' in result:
                metadata = result['analysis_metadata']
                model = metadata.get('model_used', 'unknown')
                models_used[model] = models_used.get(model, 0) + 1
                total_analysis_time += metadata.get('analysis_time', 0)
        
        return {
            'total_analyses': total_count,
            'successful_analyses': success_count,
            'failed_analyses': error_count,
            'success_rate': (success_count / total_count * 100) if total_count > 0 else 0,
            'total_analysis_time': total_analysis_time,
            'average_analysis_time': total_analysis_time / success_count if success_count > 0 else 0,
            'models_used': models_used,
            'ollama_config': {
                'default_model': self.config.default_commit_analysis_model,
                'max_retries': self.config.max_retries,
                'request_timeout': self.config.request_timeout
            }
        }


# 创建全局AI分析服务实例
ai_analysis_service = AIAnalysisService()