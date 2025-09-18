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
    def save_commit_to_database(github_commit_data):
        """
        将GitHub提交数据保存到数据库
        
        Args:
            github_commit_data: GitHub API返回的提交数据
            
        Returns:
            tuple: (success: bool, message: str, commit_obj: GitCommitAnalysis or None)
        """
        try:
            # 使用schemas中的格式转换函数
            db_data = format_commit_for_database(github_commit_data)
            logger.info(f"开始保存提交到数据库: SHA={db_data['commit_sha'][:8]}, 作者={db_data['author_name']}")
            
            # 解析时间字符串为Django的datetime对象
            commit_timestamp = parse_datetime(db_data['commit_timestamp'])
            if not commit_timestamp:
                logger.error(f"时间格式解析失败: {db_data['commit_timestamp']}")
                return False, f"无效的时间格式: {db_data['commit_timestamp']}", None
            
            # 使用get_or_create避免重复插入
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
            
            if created:
                logger.info(f"新提交已保存到数据库: {commit_obj.commit_sha[:8]}")
                return True, f"新提交已保存: {commit_obj.commit_sha[:8]}", commit_obj
            else:
                logger.debug(f"提交已存在于数据库: {commit_obj.commit_sha[:8]}")
                return True, f"提交已存在: {commit_obj.commit_sha[:8]}", commit_obj
                
        except Exception as e:
            logger.error(f"数据库保存失败: {str(e)}")
            return False, f"数据库保存失败: {str(e)}", None
    
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
        logger.info(f"查询保存的提交记录: limit={limit}, offset={offset}")
        try:
            # 查询数据库
            total_count = GitCommitAnalysis.objects.count()
            commits = GitCommitAnalysis.objects.all()[offset:offset+limit]
            logger.info(f"成功查询到 {len(commits)} 条提交记录，总计 {total_count} 条")
            
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
                }
            }, None
            
        except Exception as e:
            logger.error(f"查询数据库失败: {str(e)}")
            return False, None, f"查询数据库失败: {str(e)}"
    
    @staticmethod
    def get_commit_by_sha(commit_sha):
        """
        根据SHA获取单个提交的详细信息
        
        Args:
            commit_sha: 提交SHA（支持短SHA）
            
        Returns:
            tuple: (success: bool, commit_obj: GitCommitAnalysis or None, error: str or None)
        """
        logger.info(f"根据SHA查询提交: {commit_sha}")
        try:
            commit = GitCommitAnalysis.objects.get(commit_sha__startswith=commit_sha)
            logger.info(f"成功找到提交: {commit.commit_sha[:8]}")
            return True, commit, None
        except GitCommitAnalysis.DoesNotExist:
            logger.warning(f"未找到SHA开头为 '{commit_sha}' 的提交")
            return False, None, f"未找到SHA开头为 '{commit_sha}' 的提交"
        except GitCommitAnalysis.MultipleObjectsReturned:
            logger.warning(f"找到多个SHA开头为 '{commit_sha}' 的提交")
            return False, None, f"找到多个SHA开头为 '{commit_sha}' 的提交，请提供更多字符"
        except Exception as e:
            logger.error(f"查询提交失败: {str(e)}")
            return False, None, f"查询失败: {str(e)}"
    
    @staticmethod
    def update_commit_analysis(commit_sha, analysis_suggestion):
        """
        更新提交的AI分析建议
        
        Args:
            commit_sha: 提交SHA
            analysis_suggestion: AI分析建议
            
        Returns:
            tuple: (success: bool, message: str)
        """
        logger.info(f"更新提交分析建议: {commit_sha[:8]}")
        try:
            commit = GitCommitAnalysis.objects.get(commit_sha=commit_sha)
            commit.analysis_suggestion = analysis_suggestion
            commit.save()
            logger.info(f"成功更新提交 {commit_sha[:8]} 的分析建议")
            return True, f"已更新提交 {commit_sha[:8]} 的分析建议"
        except GitCommitAnalysis.DoesNotExist:
            logger.warning(f"更新失败: 未找到SHA为 '{commit_sha}' 的提交")
            return False, f"未找到SHA为 '{commit_sha}' 的提交"
        except Exception as e:
            logger.error(f"更新提交分析失败: {str(e)}")
            return False, f"更新失败: {str(e)}"
    
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
