import os
import requests
from dotenv import load_dotenv

if os.path.exists('.env'):
    load_dotenv('.env')
else:
    print("❌ 错误：未找到 .env 文件")
    exit(1)

GITHUB_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')

if not GITHUB_TOKEN:
    print("❌ 错误：未找到 GITHUB_ACCESS_TOKEN 环境变量")
    exit(1)

REPO_OWNER = 'liuzijun12'
REPO_NAME = 'code_review'

commits_url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits'

headers = {
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'Python-GitHub-Client'
}

try:
    print(f"📂 正在获取仓库信息: {REPO_OWNER}/{REPO_NAME}")
    response = requests.get(commits_url + '?per_page=5', headers=headers)
    response.raise_for_status()

    commits = response.json()
    
    if commits:
        print(f"\n✅ 成功获取 {len(commits)} 条最新提交记录：")
        print("=" * 80)
        
        for i, commit in enumerate(commits, 1):
            sha = commit['sha']
            author = commit['commit']['author']['name']
            date = commit['commit']['author']['date']
            message = commit['commit']['message'].split('\n')[0]
            
            print(f"\n📌 提交 #{i}")
            print(f"   SHA: {sha}")
            print(f"   作者: {author}")
            print(f"   日期: {date}")
            print(f"   信息: {message}")
            
            # 获取并显示文件变更信息
            commit_detail_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{sha}"
            detail_response = requests.get(commit_detail_url, headers=headers)
            detail_response.raise_for_status()
            commit_details = detail_response.json()
            
            files_changed = commit_details.get('files', [])
            if files_changed:
                print(f"   变更文件: {len(files_changed)} 个文件")
                for file in files_changed:
                    print(f"     - {file['filename']} ({file['status']})")
                    # 打印文件的代码 diff 内容
                    if 'patch' in file:
                        print("\n" + "="*40 + " 代码变更 (Diff) " + "="*40)
                        print(file['patch'])
                        print("="*90)
    else:
        print("⚠️ 未找到任何提交记录")

except requests.exceptions.HTTPError as http_err:
    print(f"❌ HTTP 错误发生：{http_err}")
    print(f"状态码: {http_err.response.status_code}")
    print(f"错误信息: {http_err.response.text}")
except requests.exceptions.RequestException as err:
    print(f"❌ 网络请求错误: {err}")

print("\n" + "="*80)
print("脚本执行完毕。")