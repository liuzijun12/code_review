# 代码分析任务配置指南

本文档说明如何在 Django Admin 中配置代码仓库的自动分析任务。

---

## 📋 前置准备

在配置任务之前，请确保以下信息已在 Django Admin 中配置：

1. **仓库配置**（Repository Config）
   - 路径：`http://your-domain/admin/app_ai/repositoryconfig/`
   - 必需字段：
     - `repo_owner`: GitHub 仓库所有者（如：`liuzijun12`）
     - `repo_name`: GitHub 仓库名称（如：`ai-detection`）
     - `github_token`: GitHub 个人访问令牌（需要 `repo` 权限）
     - `wechat_webhook_url`: 企业微信群机器人 Webhook URL（可选）

---

## ⚙️ 配置定时任务

### 1. 进入 Periodic Tasks 管理页面

访问：`http://your-domain/admin/django_celery_beat/periodictask/`

点击 **"ADD PERIODIC TASK"** 按钮。

---

### 2. 填写任务基本信息

#### **Name（任务名称）**
```
night_analyse
```
自定义名称，用于标识该任务。

#### **Task (registered)（注册的任务）**
从下拉列表中选择：
```
app_ai.analyze_repository_summary
```

---

### 3. 配置任务参数 ⭐（重要）

#### **Positional Arguments（位置参数）**

**格式：** JSON 数组，包含两个字符串参数

```json
["repo_owner", "repo_name"]
```

**示例：**
```json
["liuzijun12", "ai-detection"]
```

**说明：**
- 第一个参数：仓库所有者（GitHub username 或 organization）
- 第二个参数：仓库名称

---

#### **Keyword Arguments（关键字参数）** - 可选

**格式：** JSON 对象

**⭐ 默认配置（推荐）：**
```json
{}
```
留空表示使用所有默认值：
- ✅ **分析全部文件类型**（不限制文件类型）
- ✅ 单个文件最大 100KB
- ✅ 使用环境变量中配置的 Ollama 服务

---

**可选参数：**

```json
{
  "file_types": [".py", ".java", ".js"],
  "max_size_kb": 100,
  "ollama_url": "http://ollama:11434",
  "model_name": "llama3.1:8B"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `file_types` | Array | `null` | 要分析的文件类型。<br>**`null` 或留空 = 分析全部文件**<br>指定如 `[".py", ".java"]` = 只分析指定类型 |
| `max_size_kb` | Integer | `100` | 单个文件最大大小（KB），超过此大小的文件会被跳过 |
| `ollama_url` | String | 从环境变量读取 | Ollama 服务地址（通常不需要修改） |
| `model_name` | String | 从环境变量读取 | 使用的 AI 模型名称（通常不需要修改） |

**常用配置示例：**

**1. 分析全部文件（推荐，使用默认值）** ⭐
```json
{}
```
**说明：** 留空即可，会自动分析仓库中的所有文件（.py, .java, .js, .md, .txt 等全部类型）

---

**2. 只分析 Python 文件**
```json
{
  "file_types": [".py"]
}
```

**3. 分析多种语言文件**
```json
{
  "file_types": [".py", ".java", ".js", ".ts", ".go"]
}
```

**4. 分析全部文件，但提高文件大小限制**
```json
{
  "max_size_kb": 500
}
```

**5. 完整自定义配置**
```json
{
  "file_types": [".py", ".java"],
  "max_size_kb": 200
}
```

---

### 4. 设置执行时间

选择以下方式之一：

#### **选项 A：Crontab Schedule（推荐）**

创建一个 Crontab：
- 点击 "Crontab" 旁边的 "+" 按钮
- 填写 Crontab 表达式

**常用示例：**

```
0 2 * * *     # 每天凌晨 2:00 执行
0 */6 * * *   # 每 6 小时执行一次
0 0 * * 1     # 每周一凌晨执行
0 3 * * 1-5   # 工作日凌晨 3:00 执行
```

#### **选项 B：Interval Schedule**

创建一个 Interval：
- 选择间隔周期（如：`every 1 days`）

---

### 5. 其他设置

- **Enabled**: ✅ 勾选（启用任务）
- **One-off Task**: ⬜ 不勾选（如果只想执行一次则勾选）
- **Start Datetime**: 可选，任务开始时间
- **Expires**: 可选，任务过期时间

---

## 📝 完整配置示例

### 示例 1：每天夜间分析全部文件（推荐）⭐

```
Name: night_analyse_all_files
Task: app_ai.analyze_repository_summary

Positional Arguments:
["liuzijun12", "ai-detection"]

Keyword Arguments:
{}

说明: 留空表示分析所有类型的文件

Crontab: 0 2 * * *  (每天凌晨 2:00)
Enabled: ✅
```

### 示例 2：每 6 小时只分析 Python 文件

```
Name: python_code_check
Task: app_ai.analyze_repository_summary

Positional Arguments:
["username", "repo-name"]

Keyword Arguments:
{
  "file_types": [".py"]
}

Crontab: 0 */6 * * *
Enabled: ✅
```

### 示例 3：工作日分析多种代码文件

```
Name: workday_code_review
Task: app_ai.analyze_repository_summary

Positional Arguments:
["username", "repo-name"]

Keyword Arguments:
{
  "file_types": [".py", ".java", ".js", ".ts"],
  "max_size_kb": 200
}

Crontab: 0 9 * * 1-5  (工作日早上 9:00)
Enabled: ✅
```

---

## ✅ 保存并验证

1. 点击 **"SAVE"** 保存任务
2. 返回 Periodic Tasks 列表，确认任务已启用
3. 检查 Celery Beat 日志：
   ```bash
   docker-compose logs -f celery_beat
   ```
4. 等待任务执行或手动触发测试

---

## 🧪 手动测试任务

### 方法 1：在 Django Shell 中测试

```bash
docker exec -it code_review_django python manage.py shell
```

```python
from app_ai.get_all_tasks import analyze_repository_summary_from_db

# 同步执行
result = analyze_repository_summary_from_db('liuzijun12', 'ai-detection')
print(result)

# 异步执行
task = analyze_repository_summary_from_db.delay('liuzijun12', 'ai-detection')
print(f"Task ID: {task.id}")
```

### 方法 2：在 Admin 界面手动运行

1. 进入 Periodic Tasks 页面
2. 勾选要测试的任务
3. 选择 Action: **"Run selected tasks"**
4. 点击 **"Go"**

---

## 📱 查看执行结果

任务执行后会自动：

1. ✅ 分析代码仓库
2. ✅ 生成中文分析报告
3. ✅ 发送到企业微信群（如果配置了 webhook）

**查看日志：**
```bash
# Celery Worker 日志
docker-compose logs -f celery_worker

# Celery Beat 日志
docker-compose logs -f celery_beat
```

---

## ❓ 常见问题

### Q1: 任务不执行？

**检查清单：**
- [ ] Celery Beat 服务是否运行？
- [ ] 任务是否启用（Enabled ✅）？
- [ ] Crontab 时间是否正确？
- [ ] 查看 Beat 日志是否有错误

### Q2: GitHub Token 401 错误？

**解决方案：**
1. 访问 https://github.com/settings/tokens
2. 生成新的 Personal Access Token
3. 权限勾选：`repo`（完整仓库访问）
4. 在 Django Admin 更新 Repository Config 的 `github_token` 字段

### Q3: 企业微信没收到消息？

**检查清单：**
- [ ] Webhook URL 是否正确？
- [ ] 机器人是否已添加到群组？
- [ ] 查看 Worker 日志中的 WeChat notification 状态

### Q4: 如何修改分析提示词？

**编辑文件：** `app_ai/get_all_tasks/tasks.py`  
**位置：** 第 91-125 行

修改后重启服务：
```bash
docker-compose restart celery_worker celery_beat
```

---

## 📚 相关文档

- Celery Beat 文档：https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html
- Django Celery Beat：https://django-celery-beat.readthedocs.io/
- Crontab 表达式：https://crontab.guru/

---

## 🎯 快速开始模板

**复制粘贴配置（分析全部文件）：**

```
Task Name: repo_analysis_all_files
Task: app_ai.analyze_repository_summary

Positional Arguments:
["YOUR_GITHUB_USERNAME", "YOUR_REPO_NAME"]

Keyword Arguments:
{}

说明：留空 {} 表示分析所有文件类型

Schedule (Crontab): 0 2 * * *
Enabled: ✅
```

**使用步骤：**
1. 替换 `YOUR_GITHUB_USERNAME` 为你的 GitHub 用户名
2. 替换 `YOUR_REPO_NAME` 为你的仓库名称
3. 保存即可！

**示例：**
```
["liuzijun12", "ai-detection"]
```

---

## 📊 默认值说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `file_types` | `null`（空） | ✅ **分析全部文件类型**（.py, .java, .js, .md, .txt 等所有文件） |
| `max_size_kb` | `100` | 单个文件最大 100KB，超过会跳过 |
| `ollama_url` | 从环境变量读取 | Ollama 服务地址 |
| `model_name` | 从环境变量读取 | AI 模型名称（如 llama3.1:8B） |

**💡 重要提示：**
- **`Keyword Arguments` 留空 `{}`** = 使用全部默认值 = **分析所有文件**
- 如果只想分析特定文件类型，才需要添加 `"file_types": [".py"]`

---

**配置完成！** 🎉 任务将按照设定的时间自动执行，分析结果会自动发送到企业微信群。
