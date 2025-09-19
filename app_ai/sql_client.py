"""
数据库操作客户端
封装所有与数据库相关的操作
"""

import logging
from django.utils.dateparse import parse_datetime
from django.db import transaction
from .models import GitCommitAnalysis
from .schemas import format_commit_for_database

# 创建logger实例
logger = logging.getLogger(__name__)


class DatabaseClient:
    """数据库操作客户端"""
    
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
    def save_commit_with_ai_analysis(github_commit_data, ai_analysis_result):
        """
        保存提交数据并包含AI分析结果
        
        Args:
            github_commit_data: GitHub提交数据
            ai_analysis_result: AI分析结果字典
            
        Returns:
            tuple: (success: bool, message: str, commit_obj: GitCommitAnalysis or None)
        """
        try:
            # 提取AI分析建议
            analysis_suggestion = None
            if ai_analysis_result and ai_analysis_result.get('status') == 'success':
                analysis_suggestion = ai_analysis_result.get('analysis_suggestion', '')
                
                # 如果有分析元数据，可以添加到建议中
                if 'analysis_metadata' in ai_analysis_result:
                    metadata = ai_analysis_result['analysis_metadata']
                    analysis_suggestion += f"\n\n[AI分析元数据]\n"
                    analysis_suggestion += f"模型: {metadata.get('model_used', 'unknown')}\n"
                    analysis_suggestion += f"分析时间: {metadata.get('analysis_time', 0):.1f}秒\n"
                    analysis_suggestion += f"分析类型: {metadata.get('analysis_type', 'unknown')}\n"
            
            # 保存到数据库
            return DatabaseClient.save_commit_to_database(github_commit_data, analysis_suggestion)
            
        except Exception as e:
            logger.error(f"保存AI分析结果失败: {str(e)}")
            return False, f"保存AI分析结果失败: {str(e)}", None
    
    @staticmethod
    def update_commit_analysis(commit_sha, analysis_suggestion):
        """
        更新指定提交的AI分析建议
        
        Args:
            commit_sha: 提交SHA
            analysis_suggestion: AI分析建议
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            commit_obj = GitCommitAnalysis.objects.get(commit_sha=commit_sha)
            commit_obj.analysis_suggestion = analysis_suggestion
            commit_obj.save()
            
            logger.info(f"更新提交AI分析: {commit_sha[:8]}")
            return True, f"AI分析已更新: {commit_sha[:8]}"
            
        except GitCommitAnalysis.DoesNotExist:
            error_msg = f"提交不存在: {commit_sha[:8]}"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"更新AI分析失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    @staticmethod
    def get_commits_without_analysis(limit=10):
        """
        获取没有AI分析的提交记录
        
        Args:
            limit: 限制返回的记录数量
            
        Returns:
            tuple: (success: bool, commits: list, error: str or None)
        """
        try:
            commits = GitCommitAnalysis.objects.filter(
                analysis_suggestion__isnull=True
            ).order_by('-commit_timestamp')[:limit]
            
            commit_list = []
            for commit in commits:
                commit_list.append({
                    'commit_sha': commit.commit_sha,
                    'author_name': commit.author_name,
                    'commit_message': commit.commit_message,
                    'commit_timestamp': commit.commit_timestamp.isoformat(),
                    'code_diff': commit.code_diff
                })
            
            return True, commit_list, None
            
        except Exception as e:
            error_msg = f"查询未分析提交失败: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    @staticmethod
    def get_saved_commits(limit=10, offset=0):
        """
        获取数据库中保存的提交记录
        
        Args:
            limit: 限制返回的记录数量
            offset: 偏移量
            
        Returns:
            tuple: (success: bool, data: dict, error: str or None)
        """
        try:
            # 查询数据库
            total_count = GitCommitAnalysis.objects.count()
            commits = GitCommitAnalysis.objects.all()[offset:offset+limit]
            
            # 格式化返回数据
            commit_list = []
            for commit in commits:
                commit_list.append({
                    'commit_sha': commit.commit_sha,
                    'short_sha': commit.commit_sha[:8],
                    'author_name': commit.author_name,
                    'commit_message': commit.commit_message[:100] + '...' if len(commit.commit_message) > 100 else commit.commit_message,
                    'commit_timestamp': commit.commit_timestamp.isoformat(),
                    'code_diff_length': len(commit.code_diff),
                    'has_analysis': bool(commit.analysis_suggestion),
                    'analysis_preview': commit.analysis_suggestion[:200] + '...' if commit.analysis_suggestion and len(commit.analysis_suggestion) > 200 else commit.analysis_suggestion,
                    'created_at': commit.created_at.isoformat(),
                    'updated_at': commit.updated_at.isoformat()
                })
            
            return True, {
                'commits': commit_list,
                'pagination': {
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': offset + limit < total_count
                },
                'analysis_stats': {
                    'total_commits': total_count,
                    'analyzed_commits': GitCommitAnalysis.objects.filter(analysis_suggestion__isnull=False).count(),
                    'unanalyzed_commits': GitCommitAnalysis.objects.filter(analysis_suggestion__isnull=True).count()
                }
            }, None
            
        except Exception as e:
            error_msg = f"查询数据库失败: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    @staticmethod
    def get_commit_by_sha(commit_sha):
        """
        根据SHA获取特定提交记录
        
        Args:
            commit_sha: 提交SHA
            
        Returns:
            tuple: (success: bool, commit_data: dict or None, error: str or None)
        """
        try:
            commit = GitCommitAnalysis.objects.get(commit_sha=commit_sha)
            
            commit_data = {
                'commit_sha': commit.commit_sha,
                'author_name': commit.author_name,
                'commit_message': commit.commit_message,
                'commit_timestamp': commit.commit_timestamp.isoformat(),
                'code_diff': commit.code_diff,
                'analysis_suggestion': commit.analysis_suggestion,
                'has_analysis': bool(commit.analysis_suggestion),
                'created_at': commit.created_at.isoformat(),
                'updated_at': commit.updated_at.isoformat()
            }
            
            return True, commit_data, None
            
        except GitCommitAnalysis.DoesNotExist:
            error_msg = f"提交不存在: {commit_sha[:8]}"
            logger.warning(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"查询提交失败: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    @staticmethod
    def delete_commit(commit_sha):
        """
        删除指定的提交记录
        
        Args:
            commit_sha: 提交SHA
            
        Returns:
            tuple: (success: bool, message: str)
        """
        logger.info(f"删除提交记录: {commit_sha[:8]}")
        try:
            commit = GitCommitAnalysis.objects.get(commit_sha=commit_sha)
            commit.delete()
            logger.info(f"成功删除提交 {commit_sha[:8]}")
            return True, f"已删除提交 {commit_sha[:8]}"
        except GitCommitAnalysis.DoesNotExist:
            logger.warning(f"删除失败: 未找到SHA为 '{commit_sha}' 的提交")
            return False, f"未找到SHA为 '{commit_sha}' 的提交"
        except Exception as e:
            logger.error(f"删除提交失败: {str(e)}")
            return False, f"删除失败: {str(e)}"
    
    @staticmethod
    def get_commits_by_author(author_name, limit=10):
        """
        根据作者名获取提交记录
        
        Args:
            author_name: 作者名
            limit: 限制返回的记录数量
            
        Returns:
            tuple: (success: bool, commits: list, error: str or None)
        """
        logger.info(f"根据作者查询提交记录: 作者={author_name}, 限制={limit}")
        try:
            commits = GitCommitAnalysis.objects.filter(
                author_name__icontains=author_name
            ).order_by('-commit_timestamp')[:limit]
            logger.info(f"找到 {len(commits)} 个作者 '{author_name}' 的提交记录")
            
            commit_list = []
            for commit in commits:
                commit_list.append({
                    'commit_sha': commit.commit_sha,
                    'short_sha': commit.commit_sha[:8],
                    'author_name': commit.author_name,
                    'commit_message': commit.commit_message[:100] + '...' if len(commit.commit_message) > 100 else commit.commit_message,
                    'commit_timestamp': commit.commit_timestamp.isoformat(),
                    'has_analysis': bool(commit.analysis_suggestion),
                })
            
            return True, commit_list, None
            
        except Exception as e:
            logger.error(f"根据作者查询提交失败: {str(e)}")
            return False, [], f"查询失败: {str(e)}"
    
    @staticmethod
    def get_database_stats():
        """
        获取数据库统计信息
        
        Returns:
            dict: 统计信息
        """
        logger.info("获取数据库统计信息")
        try:
            total_commits = GitCommitAnalysis.objects.count()
            analyzed_commits = GitCommitAnalysis.objects.filter(
                analysis_suggestion__isnull=False
            ).exclude(analysis_suggestion='').count()
            logger.info(f"统计信息: 总提交数={total_commits}, 已分析={analyzed_commits}")
            
            # 获取最近的提交
            latest_commit = GitCommitAnalysis.objects.first()
            
            # 按作者统计
            from django.db.models import Count
            author_stats = GitCommitAnalysis.objects.values('author_name').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            return {
                'total_commits': total_commits,
                'analyzed_commits': analyzed_commits,
                'unanalyzed_commits': total_commits - analyzed_commits,
                'analysis_rate': round((analyzed_commits / total_commits * 100), 2) if total_commits > 0 else 0,
                'latest_commit': {
                    'sha': latest_commit.commit_sha[:8] if latest_commit else None,
                    'author': latest_commit.author_name if latest_commit else None,
                    'timestamp': latest_commit.commit_timestamp.isoformat() if latest_commit else None
                } if latest_commit else None,
                'top_authors': list(author_stats)
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {
                'error': f"获取统计信息失败: {str(e)}"
            }
    
    @staticmethod
    def batch_save_commits(github_commits_data):
        """
        批量保存提交数据
        
        Args:
            github_commits_data: GitHub API返回的提交数据列表
            
        Returns:
            tuple: (success_count: int, error_count: int, messages: list)
        """
        logger.info(f"开始批量保存 {len(github_commits_data)} 个提交")
        success_count = 0
        error_count = 0
        messages = []
        
        for commit_data in github_commits_data:
            success, message, _ = DatabaseClient.save_commit_to_database(commit_data)
            if success:
                success_count += 1
            else:
                error_count += 1
            messages.append(message)
        
        logger.info(f"批量保存完成: 成功={success_count}, 失败={error_count}")
        return success_count, error_count, messages
    
    @staticmethod
    def search_commits(query, limit=10):
        """
        搜索提交记录（根据提交消息或作者名）
        
        Args:
            query: 搜索关键词
            limit: 限制返回的记录数量
            
        Returns:
            tuple: (success: bool, commits: list, error: str or None)
        """
        logger.info(f"搜索提交记录: 关键词='{query}', 限制={limit}")
        try:
            from django.db.models import Q
            
            commits = GitCommitAnalysis.objects.filter(
                Q(commit_message__icontains=query) | Q(author_name__icontains=query)
            ).order_by('-commit_timestamp')[:limit]
            logger.info(f"搜索到 {len(commits)} 个匹配的提交记录")
            
            commit_list = []
            for commit in commits:
                commit_list.append({
                    'commit_sha': commit.commit_sha,
                    'short_sha': commit.commit_sha[:8],
                    'author_name': commit.author_name,
                    'commit_message': commit.commit_message,
                    'commit_timestamp': commit.commit_timestamp.isoformat(),
                    'has_analysis': bool(commit.analysis_suggestion),
                    'match_type': 'message' if query.lower() in commit.commit_message.lower() else 'author'
                })
            
            return True, commit_list, None
            
        except Exception as e:
            logger.error(f"搜索提交记录失败: {str(e)}")
            return False, [], f"搜索失败: {str(e)}"

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
