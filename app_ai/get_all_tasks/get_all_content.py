"""
GitHub Repository Content Fetcher Module

Features:
1. Collect file information (recursively get file list)
2. Fetch file content (read files into variables)
3. Get repository configuration from database
"""
import os
import logging
import requests
import base64
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


# ==================== Database Configuration ====================

def get_repo_config_from_db(repo_owner: str, repo_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get repository configuration from database
    
    Args:
        repo_owner: Repository owner
        repo_name: Repository name
    
    Returns:
        (github_token, error_message)
        - If found: (token, None)
        - If not found or error: (None, error_message)
    """
    try:
        from app_ai.models import RepositoryConfig
        
        # Query repository configuration
        repo_config = RepositoryConfig.objects.filter(
            repo_owner=repo_owner,
            repo_name=repo_name,
            is_enabled=True
        ).first()
        
        if not repo_config:
            return None, f"Repository '{repo_owner}/{repo_name}' not found in database or is disabled"
        
        if not repo_config.github_token:
            return None, f"GitHub token not configured for repository '{repo_owner}/{repo_name}'"
        
        logger.info(f"Found repository config in database: {repo_owner}/{repo_name}")
        return repo_config.github_token, None
        
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        return None, f"Database error: {str(e)}"


class RepositoryContentFetcher:
    """GitHub Repository Content Fetcher"""
    
    def __init__(
        self, 
        repo_owner: Optional[str] = None, 
        repo_name: Optional[str] = None, 
        github_token: Optional[str] = None,
        use_database: bool = True  # 默认使用数据库
    ):
        """
        Initialize from database or parameters
        
        Args:
            repo_owner: Repository owner
            repo_name: Repository name  
            github_token: GitHub token (optional if use_database=True)
            use_database: If True, fetch config from database (default: True)
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = 'https://api.github.com'
        
        # 如果没有提供仓库信息，抛出错误
        if not self.repo_owner or not self.repo_name:
            raise ValueError("repo_owner and repo_name are required")
        
        # Get token from database or parameters
        if use_database:
            token, error = get_repo_config_from_db(self.repo_owner, self.repo_name)
            if error:
                raise ValueError(error)
            self.github_token = token
        else:
            if not github_token:
                raise ValueError("github_token is required when use_database=False")
            self.github_token = github_token
    
    def _request(self, url: str) -> Optional[Dict]:
        """Make API request"""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'CodeReview/1.0'
        }
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                # Log detailed error information
                logger.error(f"GitHub API error: {response.status_code} - {url}")
                logger.error(f"Response: {response.text[:500]}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def get_files_list(self, path: str = "", max_depth: int = 10, depth: int = 0) -> List[Dict]:
        """
        Recursively get all files list
        
        Returns:
            [{'path': 'path', 'name': 'filename', 'size': size, 'type': 'file/dir'}, ...]
        """
        if depth >= max_depth:
            return []
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{path}"
        
        # Log API request details on first call
        if depth == 0:
            logger.info(f"Requesting GitHub API: {url}")
            logger.info(f"Token configured: {'Yes' if self.github_token else 'No'}")
        
        contents = self._request(url)
        
        if not contents:
            if depth == 0:
                logger.warning(f"No contents returned from GitHub API for root path")
            return []
        
        items = []
        for item in contents:
            items.append({
                'path': item.get('path', ''),
                'name': item.get('name', ''),
                'size': item.get('size', 0),
                'type': item.get('type', '')
            })
            
            # Recursively enter directories
            if item.get('type') == 'dir':
                items.extend(self.get_files_list(item['path'], max_depth, depth + 1))
        
        return items
    
    def get_file_content(self, path: str) -> Optional[str]:
        """
        Get single file content
        
        Returns:
            File content (string) or None
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{path}"
        data = self._request(url)
        
        if data and data.get('type') == 'file':
            try:
                return base64.b64decode(data['content']).decode('utf-8')
            except:
                return None
        return None


# ==================== Main Functions ====================

def collect_files_info(
    file_types: Optional[List[str]] = None,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    use_database: bool = True  # 默认使用数据库
) -> Dict:
    """
    [Function 1] Collect file information
    
    Args:
        file_types: File type list, e.g. ['.py', '.java'], None for all files
        repo_owner: Repository owner (required)
        repo_name: Repository name (required)
        use_database: If True, fetch config from database (default: True)
    
    Returns:
        {
            'status': 'success',
            'files': [
                {'path': 'file_path', 'name': 'filename', 'size': size, 'extension': 'ext'},
                ...
            ]
        }
    
    Example:
        # Get all Python files information from database
        info = collect_files_info(
            file_types=['.py'],
            repo_owner='username',
            repo_name='repo'
        )
    """
    try:
        fetcher = RepositoryContentFetcher(repo_owner, repo_name, use_database=use_database)
        logger.info(f"Collecting file info: {fetcher.repo_owner}/{fetcher.repo_name}")
        
        # Get all files
        all_items = fetcher.get_files_list()
        files = [item for item in all_items if item['type'] == 'file']
        
        # Filter file types
        if file_types:
            file_types_lower = [ext.lower() for ext in file_types]
            files = [f for f in files if os.path.splitext(f['path'])[1].lower() in file_types_lower]
        
        # Add extension info
        for file in files:
            file['extension'] = os.path.splitext(file['path'])[1].lower()
        
        logger.info(f"Found {len(files)} files")
        
        return {
            'status': 'success',
            'repository': f"{fetcher.repo_owner}/{fetcher.repo_name}",
            'file_count': len(files),
            'files': files
        }
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'files': []
        }


def fetch_files_content(
    file_types: Optional[List[str]] = None,
    max_size_kb: int = 500,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    use_database: bool = True  # 默认使用数据库
) -> Dict:
    """
    [Function 2] Fetch file content into variables
    
    Args:
        file_types: File types, e.g. ['.py', '.java']
        max_size_kb: Max file size (KB), default 500KB
        repo_owner: Repository owner (required)
        repo_name: Repository name (required) 
        use_database: If True, fetch config from database (default: True)
    
    Returns:
        {
            'status': 'success',
            'content_map': {
                'file_path': 'file_content',
                ...
            },
            'file_count': file count,
            'total_size': total characters
        }
    
    Example:
        # Get content from database config
        result = fetch_files_content(
            file_types=['.py'],
            repo_owner='username',
            repo_name='repo'
        )
    """
    try:
        # 1. First collect file info
        logger.info(f"Starting to fetch file content...")
        files_info = collect_files_info(file_types, repo_owner, repo_name, use_database)
        
        if files_info['status'] != 'success':
            return files_info
        
        # 2. Fetch file content
        fetcher = RepositoryContentFetcher(repo_owner, repo_name, use_database=use_database)
        content_map = {}
        max_size_bytes = max_size_kb * 1024
        
        files = files_info['files']
        logger.info(f"Fetching {len(files)} files content...")
        
        for i, file in enumerate(files, 1):
            # Check size
            if file['size'] > max_size_bytes:
                logger.warning(f"Skip large file ({file['size']/1024:.1f}KB): {file['path']}")
                continue
            
            # Fetch content
            logger.info(f"[{i}/{len(files)}] {file['path']}")
            content = fetcher.get_file_content(file['path'])
            
            if content:
                content_map[file['path']] = content
        
        total_size = sum(len(c) for c in content_map.values())
        logger.info(f"Successfully fetched {len(content_map)} files, total {total_size:,} chars")
        
        return {
            'status': 'success',
            'repository': files_info['repository'],
            'file_count': len(content_map),
            'total_size': total_size,
            'content_map': content_map  # Core data
        }
        
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'content_map': {}
        }


# ==================== Shortcut Functions ====================

def get_python_files(repo_owner: str, repo_name: str):
    """Quick fetch all Python files content"""
    return fetch_files_content(file_types=['.py'], repo_owner=repo_owner, repo_name=repo_name)


def get_java_files(repo_owner: str, repo_name: str):
    """Quick fetch all Java files content"""
    return fetch_files_content(file_types=['.java'], repo_owner=repo_owner, repo_name=repo_name)


def get_code_files(languages: List[str], repo_owner: str, repo_name: str):
    """
    Get code files by programming languages
    
    Args:
        languages: ['python', 'java', 'javascript', ...]
        repo_owner: Repository owner
        repo_name: Repository name
    
    Supported languages:
        python, java, javascript, typescript, go, rust, cpp, csharp
    """
    lang_map = {
        'python': ['.py'],
        'java': ['.java'],
        'javascript': ['.js', '.jsx'],
        'typescript': ['.ts', '.tsx'],
        'go': ['.go'],
        'rust': ['.rs'],
        'cpp': ['.cpp', '.c', '.h'],
        'csharp': ['.cs']
    }
    
    extensions = []
    for lang in languages:
        if lang.lower() in lang_map:
            extensions.extend(lang_map[lang.lower()])
    
    return fetch_files_content(file_types=extensions, repo_owner=repo_owner, repo_name=repo_name) if extensions else {'status': 'error', 'error': 'Unknown language'}


def build_directory_tree(files: List[Dict]) -> str:
    """
    Build a directory tree structure from file list
    
    Args:
        files: List of file dicts with 'path' key
    
    Returns:
        Formatted directory tree string
    """
    if not files:
        return "(empty)"
    
    # Build tree structure
    tree = {}
    for file in files:
        parts = file['path'].split('/')
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # File
                if '__files__' not in current:
                    current['__files__'] = []
                current['__files__'].append(part)
            else:  # Directory
                if part not in current:
                    current[part] = {}
                current = current[part]
    
    # Format tree
    def format_tree(node: Dict, prefix: str = "", is_last: bool = True) -> str:
        lines = []
        items = [(k, v) for k, v in node.items() if k != '__files__']
        files = node.get('__files__', [])
        
        # Directories first
        for i, (name, subtree) in enumerate(items):
            is_last_item = (i == len(items) - 1) and not files
            connector = "└── " if is_last_item else "├── "
            lines.append(f"{prefix}{connector}{name}/")
            
            extension = "    " if is_last_item else "│   "
            lines.append(format_tree(subtree, prefix + extension, is_last_item))
        
        # Files
        for i, filename in enumerate(files):
            is_last_file = (i == len(files) - 1)
            connector = "└── " if is_last_file else "├── "
            lines.append(f"{prefix}{connector}{filename}")
        
        return "\n".join(lines)
    
    return format_tree(tree)


def format_content_with_structure(
    file_types: Optional[List[str]] = None,
    max_size_kb: int = 500,
    include_tree: bool = True,
    separator: str = "=" * 80,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    use_database: bool = True  # 默认使用数据库
) -> str:
    """
    [Function 3] Get repository content with directory structure in a formatted string
    
    This function combines directory tree and file contents into a single string variable,
    perfect for code review, AI analysis, or documentation.
    
    Args:
        file_types: File types to include, e.g. ['.py', '.java']
        max_size_kb: Max file size (KB), default 500KB  
        include_tree: Whether to include directory tree at the beginning
        separator: Separator line between files
        repo_owner: Repository owner (optional)
        repo_name: Repository name (optional)
    
    Returns:
        Formatted string containing directory tree and all file contents
    
    Example:
        # Get all Python files with directory structure
        content_str = format_content_with_structure(file_types=['.py'])
        
        # Save to file
        with open('repo_content.txt', 'w', encoding='utf-8') as f:
            f.write(content_str)
        
        # Or use in AI prompt
        ai_prompt = f"Review this code:\n\n{content_str}"
    """
    result = fetch_files_content(file_types, max_size_kb, repo_owner, repo_name, use_database)
    
    if result['status'] != 'success':
        return f"Error: {result.get('error', 'Unknown error')}"
    
    output_lines = []
    
    # Header
    output_lines.append(separator)
    output_lines.append(f"Repository: {result['repository']}")
    output_lines.append(f"Files: {result['file_count']}")
    output_lines.append(f"Total Size: {result['total_size']:,} characters")
    output_lines.append(separator)
    output_lines.append("")
    
    # Directory tree
    if include_tree and result['file_count'] > 0:
        files_info = collect_files_info(file_types, repo_owner, repo_name, use_database)
        if files_info['status'] == 'success':
            output_lines.append("Directory Structure:")
            output_lines.append("")
            output_lines.append(build_directory_tree(files_info['files']))
            output_lines.append("")
            output_lines.append(separator)
            output_lines.append("")
    
    # File contents
    content_map = result['content_map']
    sorted_paths = sorted(content_map.keys())
    
    for i, path in enumerate(sorted_paths, 1):
        content = content_map[path]
        lines_count = content.count('\n') + 1
        
        output_lines.append(f"File {i}/{result['file_count']}: {path}")
        output_lines.append(f"Lines: {lines_count}")
        output_lines.append(separator)
        output_lines.append("")
        output_lines.append(content)
        output_lines.append("")
        
        if i < result['file_count']:  # Not the last file
            output_lines.append(separator)
            output_lines.append("")
    
    return "\n".join(output_lines)


# ==================== Test Code ====================

if __name__ == '__main__':
    """
    Test Usage:
    1. Configure repository info in database (Django Admin)
    2. Run: python app_ai/get_all_tasks/get_all_content.py
    """
    import sys
    from dotenv import load_dotenv
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("GitHub Repository Content Fetcher - Test")
    print("="*60 + "\n")
    
    # Test repository info (replace with your actual repository)
    test_repo_owner = "your-repo-owner"
    test_repo_name = "your-repo-name"
    
    print(f"Note: This test uses repository: {test_repo_owner}/{test_repo_name}")
    print("Make sure this repository is configured in the database.\n")
    
    try:
        # Test 1: Collect file information
        print("[Test 1] Collect Python files information...")
        info = collect_files_info(
            file_types=['.py'], 
            repo_owner=test_repo_owner, 
            repo_name=test_repo_name
        )
        
        if info['status'] == 'success':
            print(f"[OK] Found {info['file_count']} Python files")
            for file in info['files'][:5]:  # Show first 5
                print(f"   - {file['path']} ({file['size']} bytes)")
        else:
            print(f"[ERROR] {info.get('error', 'Unknown error')}")
        
        # Test 2: Fetch file content
        print(f"\n{'='*60}")
        print("[Test 2] Fetch Python files content...")
        result = get_python_files(test_repo_owner, test_repo_name)
        
        if result['status'] == 'success':
            print(f"[OK] Success")
            print(f"   Files: {result['file_count']}")
            print(f"   Total size: {result['total_size']:,} chars")
            
            content_map = result['content_map']
            print(f"\n   First 3 files preview:")
            for i, (path, content) in enumerate(list(content_map.items())[:3], 1):
                lines = len(content.split('\n'))
                print(f"   {i}. {path} - {lines} lines")
        else:
            print(f"[ERROR] {result.get('error', 'Unknown error')}")
        
        # Test 3: Format content with directory structure
        print(f"\n{'='*60}")
        print("[Test 3] Format content with directory structure...")
        content_str = format_content_with_structure(
            file_types=['.py'], 
            max_size_kb=100,
            repo_owner=test_repo_owner,
            repo_name=test_repo_name
        )
        
        # Show preview (first 2000 chars)
        preview_length = 2000
        if len(content_str) > preview_length:
            print(f"[OK] Generated formatted string ({len(content_str):,} chars)")
            print(f"\nPreview (first {preview_length} chars):")
            print("-" * 60)
            print(content_str[:preview_length])
            print(f"\n... ({len(content_str) - preview_length:,} more chars)")
        else:
            print(f"[OK] Generated formatted string:")
            print("-" * 60)
            print(content_str)
        
        print(f"\n{'='*60}")
        print("[Tips] Usage Examples:")
        print("="*60)
        print(f"""
# Method 1: Collect file info (requires repo_owner and repo_name)
info = collect_files_info(
    file_types=['.py', '.java'],
    repo_owner='{test_repo_owner}',
    repo_name='{test_repo_name}'
)

# Method 2: Fetch file content to variables
result = fetch_files_content(
    file_types=['.py'],
    repo_owner='{test_repo_owner}',
    repo_name='{test_repo_name}'
)
content_map = result['content_map']  # {{path: content}}

# Method 3: Shortcut functions
py_files = get_python_files('{test_repo_owner}', '{test_repo_name}')
java_files = get_java_files('{test_repo_owner}', '{test_repo_name}')
code_files = get_code_files(['python', 'java'], '{test_repo_owner}', '{test_repo_name}')

# Method 4: Format with directory structure
content_str = format_content_with_structure(
    file_types=['.py'],
    repo_owner='{test_repo_owner}',
    repo_name='{test_repo_name}'
)
# Now you have everything in one string variable with directory tree!

# Save to file
with open('repo_content.txt', 'w', encoding='utf-8') as f:
    f.write(content_str)

# Or use directly
print(content_str)
        """)
        
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n[OK] Test completed\n")