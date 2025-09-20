"""
数据库操作客户端 - 异步任务专用
只保留异步任务需要的核心数据库操作
"""

import logging
from django.utils.dateparse import parse_datetime
from .models import GitCommitAnalysis
from .schemas import format_commit_for_database

# 创建logger实例
logger = logging.getLogger(__name__)


class DatabaseClient:
    """数据库操作客户端 - 异步任务专用"""
    
    @staticmethod
    def save_commit_to_database(github_commit_data, analysis_suggestion=None):
        """
        将GitHub提交数据保存到数据库，可选包含AI分析建议
        
        Args:
            github_commit_data: GitHub API返回的提交数据
            analysis_suggestion: AI分析建议（可选）
            
        Returns:
            tuple: (success: bool, message: str, commit_obj: GitCommitAnalysis or None)
        """
        try:
            # 使用schemas中的格式转换函数
            db_data = format_commit_for_database(github_commit_data)
            
            # 如果提供了AI分析建议，添加到数据中
            if analysis_suggestion:
                db_data['analysis_suggestion'] = analysis_suggestion
                logger.info(f"包含AI分析建议的提交保存: {db_data['commit_sha'][:8]}")
            
            # 解析时间字符串为Django的datetime对象
            commit_timestamp = parse_datetime(db_data['commit_timestamp'])
            if not commit_timestamp:
                return False, f"无效的时间格式: {db_data['commit_timestamp']}", None
            
            # 使用get_or_create避免重复插入，但允许更新AI分析
            commit_obj, created = GitCommitAnalysis.objects.get_or_create(
                commit_sha=db_data['commit_sha'],
                defaults={
                    'author_name': db_data['author_name'],
                    'commit_timestamp': commit_timestamp,
                    'code_diff': db_data['code_diff'],
                    'commit_message': db_data['commit_message'],
                    'analysis_suggestion': db_data.get('analysis_suggestion'),
                }
            )
            
            # 如果记录已存在但没有AI分析，或者有新的AI分析，则更新
            if not created and analysis_suggestion:
                updated = False
                if not commit_obj.analysis_suggestion:
                    commit_obj.analysis_suggestion = analysis_suggestion
                    updated = True
                    logger.info(f"为现有提交添加AI分析: {commit_obj.commit_sha[:8]}")
                elif commit_obj.analysis_suggestion != analysis_suggestion:
                    commit_obj.analysis_suggestion = analysis_suggestion
                    updated = True
                    logger.info(f"更新提交的AI分析: {commit_obj.commit_sha[:8]}")
                
                if updated:
                    commit_obj.save()
                    return True, f"提交已更新AI分析: {commit_obj.commit_sha[:8]}", commit_obj
            
            if created:
                message = f"新提交已保存: {commit_obj.commit_sha[:8]}"
                if analysis_suggestion:
                    message += " (包含AI分析)"
                return True, message, commit_obj
            else:
                return True, f"提交已存在: {commit_obj.commit_sha[:8]}", commit_obj
                
        except Exception as e:
            logger.error(f"数据库保存失败: {str(e)}")
            return False, f"数据库保存失败: {str(e)}", None
    
    @staticmethod
    def get_unanalyzed_commits(limit=50):
        """
        获取未分析的提交记录
        
        Args:
            limit: 返回记录的最大数量
            
        Returns:
            list: 未分析的提交记录列表
        """
        logger.info(f"获取未分析的提交记录，限制数量: {limit}")
        
        try:
            from django.db.models import Q
            
            # 查询analysis_suggestion为空或NULL的记录
            unanalyzed_commits = GitCommitAnalysis.objects.filter(
                Q(analysis_suggestion__isnull=True) | 
                Q(analysis_suggestion='')
            ).order_by('-commit_timestamp')[:limit]
            
            commits_list = []
            for commit in unanalyzed_commits:
                commit_dict = {
                    'commit_sha': commit.commit_sha,
                    'author_name': commit.author_name,
                    'commit_timestamp': commit.commit_timestamp.isoformat(),
                    'commit_message': commit.commit_message,
                    'code_diff': commit.code_diff,
                    'created_at': commit.created_at.isoformat(),
                    'updated_at': commit.updated_at.isoformat()
                }
                commits_list.append(commit_dict)
            
            logger.info(f"获取到 {len(commits_list)} 条未分析的提交记录")
            return commits_list
            
        except Exception as e:
            error_msg = f"获取未分析提交记录失败: {str(e)}"
            logger.error(error_msg)
            return []

    @staticmethod
    def update_analysis_suggestion(commit_sha, analysis_suggestion):
        """
        更新指定提交的AI分析建议
        
        Args:
            commit_sha: 提交SHA
            analysis_suggestion: AI分析建议内容
            
        Returns:
            dict: 更新结果
        """
        logger.info(f"更新提交 {commit_sha[:8]} 的AI分析建议")
        
        try:
            # 查找指定的提交记录
            commit = GitCommitAnalysis.objects.filter(commit_sha=commit_sha).first()
            
            if not commit:
                error_msg = f"未找到提交记录: {commit_sha}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                    'commit_sha': commit_sha
                }
            
            # 更新分析建议
            commit.analysis_suggestion = analysis_suggestion
            commit.save()
            
            logger.info(f"成功更新提交 {commit_sha[:8]} 的AI分析建议，长度: {len(analysis_suggestion)}")
            return {
                'success': True,
                'message': 'AI分析建议更新成功',
                'commit_sha': commit_sha,
                'analysis_length': len(analysis_suggestion),
                'updated_at': commit.updated_at.isoformat()
            }
            
        except Exception as e:
            error_msg = f"更新AI分析建议失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'commit_sha': commit_sha,
                'error': str(e)
            }
