"""测试 GitHub API 连接和 Token 有效性"""
from dotenv import load_dotenv
import os
import requests

load_dotenv()

repo_owner = os.getenv('REPO_OWNER', '')
repo_name = os.getenv('REPO_NAME', '')
github_token = os.getenv('GITHUB_TOKEN', '')

print("="*60)
print("GitHub API 连接测试")
print("="*60)
print(f"\n仓库: {repo_owner}/{repo_name}")
print(f"Token: {github_token[:10]}...{github_token[-4:] if len(github_token) > 14 else ''}\n")

headers = {
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'CodeReview-Test/1.0'
}

if github_token:
    headers['Authorization'] = f'token {github_token}'

# 测试 1: 验证 Token 有效性
print("📡 测试 1: 验证 Token 有效性...")
try:
    response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
    print(f"   状态码: {response.status_code}")
    
    if response.status_code == 200:
        user_data = response.json()
        print(f"   ✅ Token 有效！当前用户: {user_data.get('login', 'Unknown')}")
        print(f"   剩余 API 请求: {response.headers.get('X-RateLimit-Remaining', 'unknown')}/{response.headers.get('X-RateLimit-Limit', 'unknown')}")
    elif response.status_code == 401:
        print(f"   ❌ Token 无效或已过期")
        print(f"   响应: {response.text[:200]}")
    else:
        print(f"   ⚠️ 未知错误: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ 请求失败: {e}")

# 测试 2: 检查仓库访问权限
print(f"\n📡 测试 2: 检查仓库访问权限 ({repo_owner}/{repo_name})...")
try:
    url = f'https://api.github.com/repos/{repo_owner}/{repo_name}'
    response = requests.get(url, headers=headers, timeout=10)
    print(f"   状态码: {response.status_code}")
    
    if response.status_code == 200:
        repo_data = response.json()
        print(f"   ✅ 仓库访问成功！")
        print(f"   仓库全名: {repo_data.get('full_name', 'Unknown')}")
        print(f"   私有仓库: {'是' if repo_data.get('private') else '否'}")
        print(f"   默认分支: {repo_data.get('default_branch', 'Unknown')}")
    elif response.status_code == 404:
        print(f"   ❌ 仓库不存在或无访问权限")
        print(f"   请检查仓库名称是否正确，或 Token 是否有 repo 权限")
    elif response.status_code == 401:
        print(f"   ❌ Token 无效")
    else:
        print(f"   ⚠️ 未知错误: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ 请求失败: {e}")

# 测试 3: 获取仓库内容
print(f"\n📡 测试 3: 获取仓库根目录内容...")
try:
    url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/contents'
    response = requests.get(url, headers=headers, timeout=10)
    print(f"   状态码: {response.status_code}")
    
    if response.status_code == 200:
        contents = response.json()
        print(f"   ✅ 成功获取内容！共 {len(contents)} 个项目")
        print(f"   前 5 个项目:")
        for item in contents[:5]:
            icon = "📁" if item.get('type') == 'dir' else "📄"
            print(f"      {icon} {item.get('name', 'Unknown')}")
    elif response.status_code == 404:
        print(f"   ❌ 内容不存在")
    elif response.status_code == 401:
        print(f"   ❌ Token 无效")
        print(f"   响应: {response.text[:200]}")
    else:
        print(f"   ⚠️ 未知错误: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ 请求失败: {e}")

print("\n" + "="*60)
print("测试完成")
print("="*60 + "\n")

