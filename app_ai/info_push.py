"""
企业微信推送模块 - 简化版本
已禁用数据库存储功能，专注于消息推送
"""

import logging
import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from django.utils import timezone
from .models import RepositoryConfig

logger = logging.getLogger(__name__)


class WeChatWorkPusher:
    """企业微信推送器 - 支持多仓库配置"""
    
    def __init__(self, repo_owner=None, repo_name=None):
        """
        初始化企业微信推送器
        
        Args:
            repo_owner: 仓库所有者用户名
            repo_name: 仓库名称
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.repo_config = None
        self.webhook_url = None
        
        # 如果提供了仓库信息，尝试从数据库获取配置
        if repo_owner and repo_name:
            try:
                self.repo_config = RepositoryConfig.objects.get(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    is_enabled=True
                )
                self.webhook_url = self.repo_config.wechat_webhook_url
                logger.info(f"✅ WeChatWorkPusher 加载仓库配置成功: {repo_owner}/{repo_name}")
            except RepositoryConfig.DoesNotExist:
                logger.warning(f"⚠️ WeChatWorkPusher 未找到仓库配置: {repo_owner}/{repo_name}")
                self.webhook_url = None
            except Exception as e:
                logger.error(f"❌ WeChatWorkPusher 加载仓库配置失败: {e}")
                self.webhook_url = None
        else:
            # 没有提供仓库信息，无法获取配置
            logger.warning("⚠️ 未提供仓库信息，无法获取企业微信配置")
            self.webhook_url = None
        
        if not self.webhook_url:
            logger.warning("⚠️ 企业微信Webhook URL未配置，推送功能将不可用")
        
        logger.info(f"企业微信推送器初始化完成 - 仓库: {repo_owner}/{repo_name if repo_owner else '无仓库信息'}")
    
    def get_unpushed_analysis_records(self, limit: int = 10) -> List:
        """
        获取未推送记录 - 功能已禁用
        """
        logger.info("数据库存储功能已禁用，返回空列表")
        return []
    
    def format_commit_message(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化提交消息 - 直接处理传入的数据
        
        Args:
            commit_data: 提交数据字典
            
        Returns:
            dict: 格式化后的消息数据
        """
        try:
            # 基本信息
            commit_sha = commit_data.get('commit_sha', 'Unknown')[:8]
            author_name = commit_data.get('author_name', 'Unknown')
            commit_message = commit_data.get('commit_message', 'No message')
            
            # 限制消息长度
            if len(commit_message) > 200:
                commit_message = commit_message[:200] + "..."
            
            # 构建消息
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"""# 🔍 代码审查结果
                    
**📝 提交信息:**
- **提交者:** {author_name}
- **SHA:** `{commit_sha}`
- **消息:** {commit_message}

**🤖 AI分析:**
{commit_data.get('analysis_suggestion', '暂无AI分析结果')}

**⏰ 推送时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                }
            }
            
            logger.info(f"✅ 消息格式化完成: {commit_sha}")
            return message
            
        except Exception as e:
            logger.error(f"❌ 消息格式化失败: {str(e)}")
            return self._create_error_message(f"消息格式化失败: {str(e)}")
    
    def _create_error_message(self, error_msg: str) -> Dict[str, Any]:
        """创建错误消息"""
        return {
            "msgtype": "text",
            "text": {
                "content": f"❌ 推送失败: {error_msg}"
            }
        }
    
    def send_to_wechat(self, message: Dict[str, Any]) -> bool:
        """
        发送消息到企业微信
        
        Args:
            message: 消息内容
            
        Returns:
            bool: 发送是否成功
        """
        if not self.webhook_url:
            logger.warning("⚠️ 企业微信Webhook URL未配置，无法发送消息")
            return False
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info("✅ 消息发送成功")
                    return True
                else:
                    logger.error(f"❌ 消息发送失败: {result}")
                    return False
            else:
                logger.error(f"❌ HTTP请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 发送消息异常: {str(e)}")
            return False
    
    def mark_as_pushed(self, commit_data: Dict[str, Any]) -> bool:
        """
        标记为已推送 - 功能已禁用
        """
        logger.info("数据库存储功能已禁用，标记推送状态功能不可用")
        return True
    
    def push_commit_analysis(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        推送单个提交的分析结果
        
        Args:
            commit_data: 提交数据字典
            
        Returns:
            dict: 推送结果
        """
        try:
            # 格式化消息
            message = self.format_commit_message(commit_data)
            
            # 发送到企业微信
            success = self.send_to_wechat(message)
            
            if success:
                # 标记为已推送（功能已禁用，总是返回True）
                self.mark_as_pushed(commit_data)
                
                return {
                    'success': True,
                    'message': '推送成功',
                    'commit_sha': commit_data.get('commit_sha', 'Unknown')[:8]
                    }
            else:
                return {
                    'success': False,
                    'message': '推送失败',
                    'commit_sha': commit_data.get('commit_sha', 'Unknown')[:8]
                }
                
        except Exception as e:
            logger.error(f"❌ 推送提交分析失败: {str(e)}")
            return {
                'success': False,
                'message': f'推送异常: {str(e)}',
                'commit_sha': commit_data.get('commit_sha', 'Unknown')[:8]
            }
    
    def batch_push_analysis(self, limit: int = 10) -> Dict[str, Any]:
        """
        批量推送分析结果 - 功能已禁用
        """
        logger.info("数据库存储功能已禁用，批量推送功能不可用")
        return {
            'success': True,
            'message': '批量推送功能已禁用',
            'pushed_count': 0,
            'failed_count': 0,
            'total_processed': 0
        }
    
    def get_push_statistics(self) -> Dict[str, Any]:
        """
        获取推送统计信息 - 功能已禁用
        """
        logger.info("数据库存储功能已禁用，统计功能不可用")
        return {
            'total_commits': 0,
            'analyzed_commits': 0,
            'pushed_commits': 0,
            'unpushed_commits': 0,
            'analysis_rate': 0.0,
            'push_rate': 0.0,
            'latest_analyzed': None,
            'latest_pushed': None,
            'message': '统计功能已禁用 - 数据库存储功能不可用'
        }
