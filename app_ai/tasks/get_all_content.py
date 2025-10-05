"""
获取仓库所有内容的任务模块
通过 GitHub API 递归获取仓库的完整文件树结构和内容
"""
import os
import logging
import requests
from typing import Dict, List, Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


class RepositoryContentFetcher:
    """
    GitHub 仓库内容获取器
    支持递归获取整个仓库的文件树和内容
    """
    
    def __init__(self, repo_owner: Optional[str] = None, repo_name: Optional[str] = None, github_token: Optional[str] = None):
        """
        初始化仓库内容获取器
        
        Args:
            repo_owner: 仓库所有者（优先使用传入值，否则从环境变量读取）
            repo_name: 仓库名称（优先使用传入值，否则从环境变量读取）
            github_token: GitHub 访问令牌（优先使用传入值，否则从环境变量读取）
        """
        self.repo_owner = repo_owner or os.getenv('REPO_OWNER', '').strip()
        self.repo_name = repo_name or os.getenv('REPO_NAME', '').strip()
        self.github_token = github_token or os.getenv('GITHUB_TOKEN', '').strip()
        self.base_url = 'https://api.github.com'
        
        if not self.repo_owner or not self.repo_name:
            logger.error("❌ 仓库信息未配置，请在 .env 文件中设置 REPO_OWNER 和 REPO_NAME")
            raise ValueError("Repository owner and name are required")
        
        if not self.github_token:
            logger.warning("⚠️ GitHub Token 未配置，API 调用将受到更严格的速率限制")
        
        logger.info(f"✅ 初始化仓库内容获取器: {self.repo_owner}/{self.repo_name}")
    
    def get_headers(self) -> Dict[str, str]:
        """
        获取 GitHub API 请求头
        
        Returns:
            包含必要头信息的字典
        """
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'CodeReview-ContentFetcher/1.0'
        }
        
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        return headers
    
    def _make_request(self, url: str) -> Optional[Dict]:
        """
        发起 GitHub API 请求
        
        Args:
            url: API 端点 URL
            
        Returns:
            API 响应的 JSON 数据，失败时返回 None
        """
        try:
            logger.debug(f"📡 请求 GitHub API: {url}")
            response = requests.get(url, headers=self.get_headers(), timeout=30)
            
            # 检查响应状态
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.error(f"❌ 资源不存在 (404): {url}")
                return None
            elif response.status_code == 403:
                logger.error(f"❌ API 速率限制 (403): {url}")
                logger.error(f"   剩余请求次数: {response.headers.get('X-RateLimit-Remaining', 'unknown')}")
                return None
            else:
                logger.error(f"❌ API 请求失败 ({response.status_code}): {url}")
                logger.error(f"   响应: {response.text[:200]}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ API 请求超时: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API 请求异常: {str(e)}")
            return None
    
    def get_content(self, path: str = "") -> Optional[List[Dict]]:
        """
        获取指定路径的内容列表
        
        Args:
            path: 仓库中的路径，空字符串表示根目录
            
        Returns:
            内容列表，每个元素包含文件/目录的信息
        """
        # 构建 API URL
        if path:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{path}"
        else:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents"
        
        logger.info(f"📂 获取路径内容: {path or '(根目录)'}")
        return self._make_request(url)
    
    def get_file_content(self, path: str) -> Optional[str]:
        """
        获取单个文件的内容（解码后的文本）
        
        Args:
            path: 文件路径
            
        Returns:
            文件内容的字符串，失败时返回 None
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{path}"
        data = self._make_request(url)
        
        if data and data.get('type') == 'file':
            import base64
            try:
                # GitHub API 返回 base64 编码的内容
                content = base64.b64decode(data['content']).decode('utf-8')
                logger.info(f"📄 成功获取文件内容: {path} ({len(content)} 字符)")
                return content
            except Exception as e:
                logger.error(f"❌ 解码文件内容失败: {path}, 错误: {str(e)}")
                return None
        
        return None
    
    def get_all_files_recursive(self, path: str = "", max_depth: int = 10, current_depth: int = 0) -> List[Dict]:
        """
        递归获取仓库所有文件的信息
        
        Args:
            path: 起始路径，空字符串表示根目录
            max_depth: 最大递归深度，防止无限递归
            current_depth: 当前递归深度（内部使用）
            
        Returns:
            包含所有文件信息的列表，每个元素格式：
            {
                'path': '文件路径',
                'name': '文件名',
                'type': 'file' 或 'dir',
                'size': 文件大小（字节），
                'sha': Git SHA 值,
                'url': GitHub API URL,
                'html_url': GitHub 网页 URL,
                'download_url': 下载 URL（仅文件）
            }
        """
        # 检查递归深度
        if current_depth >= max_depth:
            logger.warning(f"⚠️ 达到最大递归深度 {max_depth}，停止遍历: {path}")
            return []
        
        all_items = []
        contents = self.get_content(path)
        
        if not contents:
            return []
        
        # 处理每个项目
        for item in contents:
            item_type = item.get('type')
            item_path = item.get('path', '')
            item_name = item.get('name', '')
            
            # 添加当前项目信息
            item_info = {
                'path': item_path,
                'name': item_name,
                'type': item_type,
                'size': item.get('size', 0),
                'sha': item.get('sha', ''),
                'url': item.get('url', ''),
                'html_url': item.get('html_url', ''),
                'download_url': item.get('download_url', '')
            }
            
            all_items.append(item_info)
            
            # 如果是目录，递归获取其内容
            if item_type == 'dir':
                logger.info(f"📁 进入目录: {item_path} (深度: {current_depth + 1})")
                sub_items = self.get_all_files_recursive(
                    path=item_path,
                    max_depth=max_depth,
                    current_depth=current_depth + 1
                )
                all_items.extend(sub_items)
        
        return all_items
    
    def get_repository_tree(self, include_content: bool = False, file_extensions: Optional[List[str]] = None) -> Dict:
        """
        获取仓库的完整文件树结构
        
        Args:
            include_content: 是否包含文件内容（仅文本文件）
            file_extensions: 只获取指定扩展名的文件内容，如 ['.py', '.js', '.md']
            
        Returns:
            包含仓库结构和统计信息的字典：
            {
                'repository': '仓库全名',
                'total_files': 文件总数,
                'total_dirs': 目录总数,
                'total_size': 总大小（字节），
                'files': [文件列表],
                'dirs': [目录列表],
                'tree': [完整树结构]
            }
        """
        logger.info(f"🌲 开始获取仓库完整文件树: {self.repo_owner}/{self.repo_name}")
        
        # 获取所有项目
        all_items = self.get_all_files_recursive()
        
        if not all_items:
            logger.error("❌ 未能获取任何内容")
            return {
                'repository': f"{self.repo_owner}/{self.repo_name}",
                'total_files': 0,
                'total_dirs': 0,
                'total_size': 0,
                'total_size_mb': 0.0,
                'files': [],
                'dirs': [],
                'tree': []
            }
        
        # 分离文件和目录
        files = [item for item in all_items if item['type'] == 'file']
        dirs = [item for item in all_items if item['type'] == 'dir']
        
        # 计算统计信息
        total_size = sum(file['size'] for file in files)
        
        # 如果需要获取文件内容
        if include_content:
            logger.info(f"📥 开始获取文件内容（共 {len(files)} 个文件）")
            for file_info in files:
                file_path = file_info['path']
                
                # 如果指定了文件扩展名过滤
                if file_extensions:
                    file_ext = os.path.splitext(file_path)[1].lower()
                    if file_ext not in file_extensions:
                        logger.debug(f"⏭️ 跳过文件（扩展名不匹配）: {file_path}")
                        continue
                
                # 获取文件内容
                content = self.get_file_content(file_path)
                file_info['content'] = content if content else None
        
        result = {
            'repository': f"{self.repo_owner}/{self.repo_name}",
            'total_files': len(files),
            'total_dirs': len(dirs),
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'files': files,
            'dirs': dirs,
            'tree': all_items
        }
        
        logger.info(f"✅ 仓库树获取完成:")
        logger.info(f"   📁 目录数: {len(dirs)}")
        logger.info(f"   📄 文件数: {len(files)}")
        logger.info(f"   💾 总大小: {result['total_size_mb']} MB")
        
        return result
    
    def print_tree(self, max_items: int = 100):
        """
        打印仓库文件树结构（用于调试）
        
        Args:
            max_items: 最多打印的项目数
        """
        all_items = self.get_all_files_recursive()
        
        print(f"\n{'='*60}")
        print(f"📦 仓库: {self.repo_owner}/{self.repo_name}")
        print(f"{'='*60}\n")
        
        for i, item in enumerate(all_items[:max_items]):
            icon = "📁" if item['type'] == 'dir' else "📄"
            size_info = f"({item['size']} bytes)" if item['type'] == 'file' else ""
            print(f"{icon} {item['path']} {size_info}")
        
        if len(all_items) > max_items:
            print(f"\n... 还有 {len(all_items) - max_items} 个项目未显示")
        
        print(f"\n{'='*60}")
        print(f"总计: {len([x for x in all_items if x['type'] == 'file'])} 个文件, "
              f"{len([x for x in all_items if x['type'] == 'dir'])} 个目录")
        print(f"{'='*60}\n")


def get_repository_content(
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    github_token: Optional[str] = None,
    include_content: bool = False,
    file_extensions: Optional[List[str]] = None
) -> Dict:
    """
    便捷函数：获取仓库的完整内容
    
    Args:
        repo_owner: 仓库所有者
        repo_name: 仓库名称
        github_token: GitHub Token
        include_content: 是否包含文件内容
        file_extensions: 只获取指定扩展名的文件内容
        
    Returns:
        仓库树结构字典
        
    Example:
        # 基本使用（从环境变量读取配置）
        tree = get_repository_content()
        
        # 指定仓库
        tree = get_repository_content(
            repo_owner='octocat',
            repo_name='Hello-World'
        )
        
        # 获取所有 Python 文件的内容
        tree = get_repository_content(
            include_content=True,
            file_extensions=['.py', '.txt', '.md']
        )
    """
    try:
        fetcher = RepositoryContentFetcher(repo_owner, repo_name, github_token)
        return fetcher.get_repository_tree(include_content, file_extensions)
    except Exception as e:
        logger.error(f"❌ 获取仓库内容失败: {str(e)}")
        return {
            'error': str(e),
            'repository': f"{repo_owner}/{repo_name}" if repo_owner and repo_name else "Unknown",
            'total_files': 0,
            'total_dirs': 0,
            'total_size': 0,
            'files': [],
            'dirs': [],
            'tree': []
        }


# ==================== 使用示例 ====================
if __name__ == '__main__':
    """
    直接运行此文件进行测试
    
    使用方法:
    1. 确保 .env 文件中配置了 REPO_OWNER, REPO_NAME, GITHUB_TOKEN
    2. 运行: python app_ai/tasks/get_all_content.py
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    # 加载 .env 文件中的环境变量
    from dotenv import load_dotenv
    load_dotenv()  # 这会自动查找并加载项目根目录的 .env 文件
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("🚀 GitHub 仓库内容获取器 - 测试模式")
    print("="*60 + "\n")
    
    try:
        # 方式 1: 使用类
        fetcher = RepositoryContentFetcher()
        
        # 打印文件树（仅前 50 项）
        fetcher.print_tree(max_items=50)
        
        # 获取完整树结构
        tree = fetcher.get_repository_tree()
        
        # 显示统计信息
        print(f"\n📊 统计信息:")
        print(f"   仓库: {tree['repository']}")
        print(f"   文件数: {tree['total_files']}")
        print(f"   目录数: {tree['total_dirs']}")
        print(f"   总大小: {tree['total_size_mb']} MB")
        
        # 方式 2: 使用便捷函数
        # tree = get_repository_content(include_content=True, file_extensions=['.py', '.md'])
        
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        sys.exit(1)
    
    print("\n✅ 测试完成\n")

