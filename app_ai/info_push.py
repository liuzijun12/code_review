"""
企业微信消息推送模块
用于将Git提交分析结果推送到企业微信群
"""
import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone
from .models import GitCommitAnalysis

logger = logging.getLogger(__name__)


class WeChatWorkPusher:
    """企业微信消息推送器"""
    
    def __init__(self):
        """初始化企业微信推送器"""
        self.webhook_url = os.getenv('WX_WEBHOOK_URL')
        if not self.webhook_url:
            logger.error("环境变量 WX_WEBHOOK_URL 未设置")
            raise ValueError("WX_WEBHOOK_URL environment variable is required")
        
        logger.info("企业微信推送器初始化完成")
    
    def get_unpushed_analysis_records(self, limit: int = 10) -> List[GitCommitAnalysis]:
        """
        获取所有字段都不为空且未推送的分析记录
        
        Args:
            limit: 获取记录数量限制
            
        Returns:
            list: 未推送的完整分析记录列表
        """
        try:
            # 查询所有字段都不为空且is_push=0的记录
            records = GitCommitAnalysis.objects.filter(
                commit_sha__isnull=False,
                author_name__isnull=False,
                commit_timestamp__isnull=False,
                code_diff__isnull=False,
                commit_message__isnull=False,
                analysis_suggestion__isnull=False,
                is_push=0  # 只获取未推送的记录
            ).exclude(
                commit_sha='',
                author_name='',
                code_diff='',
                commit_message='',
                analysis_suggestion=''
            ).order_by('-commit_timestamp')[:limit]
            
            logger.info(f"获取到 {len(records)} 条未推送的完整分析记录")
            return list(records)
            
        except Exception as e:
            logger.error(f"获取未推送分析记录失败: {e}")
            return []
    
    def format_commit_message(self, record: GitCommitAnalysis) -> Dict[str, Any]:
        """
        格式化提交记录为企业微信消息格式
        
        Args:
            record: Git提交分析记录
            
        Returns:
            dict: 企业微信消息格式
        """
        try:
            # 截取提交消息和分析建议的长度
            commit_msg = record.commit_message[:100] + '...' if len(record.commit_message) > 100 else record.commit_message
            analysis = record.analysis_suggestion[:500] + '...' if len(record.analysis_suggestion) > 500 else record.analysis_suggestion
            
            # 格式化提交时间
            commit_time = record.commit_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            # 构造Markdown格式消息
            markdown_content = f"""
## 代码审查报告

**提交信息**: {commit_msg}
**提交人**: {record.author_name}  
**提交时间**: {commit_time}
**提交SHA**: `{record.commit_sha[:8]}`

###AI分析建议:
{analysis}

---
*由AI自动分析生成 | {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
            
            # 企业微信Markdown消息格式
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": markdown_content.strip()
                }
            }
            
            return message
            
        except Exception as e:
            logger.error(f"格式化消息失败: {e}")
            return {}
    
    def send_message(self, message: Dict[str, Any]) -> bool:
        """
        发送消息到企业微信
        
        Args:
            message: 消息内容
            
        Returns:
            bool: 发送是否成功
        """
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            
            logger.info("正在发送消息到企业微信...")
            response = requests.post(
                self.webhook_url,
                headers=headers,
                data=json.dumps(message, ensure_ascii=False).encode('utf-8'),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info("消息发送成功")
                    return True
                else:
                    logger.error(f"企业微信返回错误: {result}")
                    return False
            else:
                logger.error(f"HTTP请求失败: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("发送消息超时")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"发送消息异常: {e}")
            return False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    def mark_as_pushed(self, record: GitCommitAnalysis) -> bool:
        """
        标记记录为已推送
        
        Args:
            record: Git提交分析记录
            
        Returns:
            bool: 标记是否成功
        """
        try:
            record.is_push = 1
            record.save()
            logger.info(f"提交 {record.commit_sha[:8]} 已标记为已推送")
            return True
        except Exception as e:
            logger.error(f"标记提交 {record.commit_sha[:8]} 为已推送失败: {e}")
            return False

    def push_unpushed_analysis(self, limit: int = 3) -> Dict[str, Any]:
        """
        推送未推送的分析结果到企业微信（每条记录单独发送一个消息，最多3条）
        
        Args:
            limit: 推送记录数量限制，默认最多3条
            
        Returns:
            dict: 推送结果统计
        """
        logger.info("开始推送未推送的分析结果到企业微信")
        
        try:
            # 限制最多推送3条记录
            actual_limit = min(limit, 3)
            logger.info(f"本次最多推送 {actual_limit} 条记录")
            
            # 获取未推送的分析记录
            records = self.get_unpushed_analysis_records(actual_limit)
            
            if not records:
                logger.info("没有需要推送的未推送分析记录")
                return {
                    'status': 'success',
                    'message': '没有需要推送的记录',
                    'total_count': 0,
                    'success_count': 0,
                    'error_count': 0
                }
            
            success_count = 0
            error_count = 0
            
            # 逐个推送记录（每条记录单独发送一个消息）
            for record in records:
                try:
                    logger.info(f"推送提交: {record.commit_sha[:8]} - {record.author_name}")
                    
                    # 格式化消息
                    message = self.format_commit_message(record)
                    if not message:
                        error_count += 1
                        continue
                    
                    # 发送单个消息
                    if self.send_message(message):
                        # 推送成功，标记为已推送
                        if self.mark_as_pushed(record):
                            success_count += 1
                            logger.info(f"提交 {record.commit_sha[:8]} 推送成功并已标记")
                        else:
                            error_count += 1
                            logger.error(f"提交 {record.commit_sha[:8]} 推送成功但标记失败")
                    else:
                        error_count += 1
                        logger.error(f"提交 {record.commit_sha[:8]} 推送失败")
                    
                    # 避免发送过快，每条消息间隔1秒
                    import time
                    time.sleep(1)
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"推送提交 {record.commit_sha[:8]} 异常: {e}")
            
            result = {
                'status': 'success' if error_count == 0 else 'partial_success',
                'message': f'推送完成: 成功 {success_count}, 失败 {error_count}',
                'total_count': len(records),
                'success_count': success_count,
                'error_count': error_count,
                'push_time': timezone.now().isoformat()
            }
            
            logger.info(f"企业微信推送完成: {result['message']}")
            return result
            
        except Exception as e:
            error_msg = f"推送过程异常: {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'message': error_msg,
                'total_count': 0,
                'success_count': 0,
                'error_count': 0
            }
    
    def push_single_commit(self, commit_sha: str) -> bool:
        """
        推送单个提交的分析结果（如果未推送）
        
        Args:
            commit_sha: 提交SHA
            
        Returns:
            bool: 推送是否成功
        """
        try:
            logger.info(f"推送单个提交: {commit_sha[:8]}")
            
            # 获取指定提交记录（只获取未推送的）
            record = GitCommitAnalysis.objects.filter(
                commit_sha=commit_sha,
                analysis_suggestion__isnull=False,
                is_push=0  # 只推送未推送的记录
            ).exclude(analysis_suggestion='').first()
            
            if not record:
                logger.warning(f"未找到提交 {commit_sha[:8]} 的未推送完整分析记录")
                return False
            
            # 格式化并发送消息
            message = self.format_commit_message(record)
            if message and self.send_message(message):
                # 推送成功，标记为已推送
                return self.mark_as_pushed(record)
            else:
                logger.error(f"格式化或发送提交 {commit_sha[:8]} 消息失败")
                return False
                
        except Exception as e:
            logger.error(f"推送单个提交异常: {e}")
            return False
    
    def push_single_commit_data(self, commit_data: dict) -> dict:
        """
        推送单个提交的分析结果（接受字典数据）
        
        Args:
            commit_data: 包含提交信息的字典
            
        Returns:
            dict: 推送结果
        """
        try:
            commit_sha = commit_data.get('commit_sha')
            if not commit_sha:
                return {
                    'success': False,
                    'message': '缺少commit_sha字段'
                }
            
            logger.info(f"推送单个提交数据: {commit_sha[:8]}")
            
            # 获取指定提交记录（只获取未推送的）
            record = GitCommitAnalysis.objects.filter(
                commit_sha=commit_sha,
                analysis_suggestion__isnull=False,
                is_push=0  # 只推送未推送的记录
            ).exclude(analysis_suggestion='').first()
            
            if not record:
                logger.warning(f"未找到提交 {commit_sha[:8]} 的未推送完整分析记录")
                return {
                    'success': False,
                    'message': f'未找到提交 {commit_sha[:8]} 的未推送完整分析记录'
                }
            
            # 格式化并发送消息
            message = self.format_commit_message(record)
            if not message:
                return {
                    'success': False,
                    'message': '消息格式化失败'
                }
            
            # 发送消息
            if self.send_message(message):
                # 推送成功，标记为已推送
                if self.mark_as_pushed(record):
                    return {
                        'success': True,
                        'message': f'提交 {commit_sha[:8]} 推送成功'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'提交 {commit_sha[:8]} 推送成功但标记失败'
                    }
            else:
                return {
                    'success': False,
                    'message': f'提交 {commit_sha[:8]} 消息发送失败'
                }
                
        except Exception as e:
            logger.error(f"推送单个提交异常: {e}")
            return {
                'success': False,
                'message': f'推送异常: {str(e)}'
            }
    
    def send_summary_report(self) -> bool:
        """
        发送分析总结报告
        
        Returns:
            bool: 发送是否成功
        """
        try:
            logger.info("生成并发送分析总结报告")
            
            # 统计数据
            total_commits = GitCommitAnalysis.objects.count()
            analyzed_commits = GitCommitAnalysis.objects.filter(
                analysis_suggestion__isnull=False
            ).exclude(analysis_suggestion='').count()
            pushed_commits = GitCommitAnalysis.objects.filter(is_push=1).count()
            unpushed_commits = GitCommitAnalysis.objects.filter(
                analysis_suggestion__isnull=False,
                is_push=0
            ).exclude(analysis_suggestion='').count()
            
            unanalyzed_commits = total_commits - analyzed_commits
            analysis_rate = (analyzed_commits / total_commits * 100) if total_commits > 0 else 0
            push_rate = (pushed_commits / analyzed_commits * 100) if analyzed_commits > 0 else 0
            
            # 最近分析的提交
            latest_analyzed = GitCommitAnalysis.objects.filter(
                analysis_suggestion__isnull=False
            ).exclude(analysis_suggestion='').order_by('-updated_at').first()
            
            # 构造总结报告
            summary_content = f"""
## 📊 代码审查系统状态报告

### 📈 统计数据
- **总提交数**: {total_commits}
- **已分析数**: {analyzed_commits}  
- **未分析数**: {unanalyzed_commits}
- **分析率**: {analysis_rate:.1f}%

### 📤 推送统计
- **已推送数**: {pushed_commits}
- **待推送数**: {unpushed_commits}
- **推送率**: {push_rate:.1f}%

### 🕐 最近活动
"""
            
            if latest_analyzed:
                summary_content += f"- **最新分析**: {latest_analyzed.commit_sha[:8]} ({latest_analyzed.author_name})\n"
                summary_content += f"- **分析时间**: {latest_analyzed.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            else:
                summary_content += "- **最新分析**: 暂无记录\n"
            
            summary_content += f"""
---
*系统自动生成 | {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
            
            message = {
                "msgtype": "markdown", 
                "markdown": {
                    "content": summary_content.strip()
                }
            }
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"发送总结报告失败: {e}")
            return False


# 创建全局推送器实例
try:
    wechat_pusher = WeChatWorkPusher()
except Exception as e:
    logger.warning(f"企业微信推送器初始化失败: {e}")
    wechat_pusher = None
