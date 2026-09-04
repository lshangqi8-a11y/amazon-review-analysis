# Amazon 评论分析 Skill

独立发布包：下载 → 安装到 Agent skills 目录 → `pip install -r requirements.txt` → 上传评论 Excel 即可使用。

不依赖本公司 Flask / AI Gateway / 数据库。语义分析由你当前 Agent 所选模型完成；读表、校验、统计、出 Excel 由本包 Python 脚本完成。

## 安装（同事按此操作）

### 1. 获取本包

- 从 GitHub 下载 ZIP，或 `git clone` 本仓库  
- 解压后应看到：`SKILL.md`、`prompts/`、`scripts/`、`requirements.txt`

### 2. 安装到 Agent 工具

把整个文件夹放到 skills 目录，文件夹名保持为 `amazon-review-analysis`：

| 工具 | 路径示例 |
|------|----------|
| Cursor（个人） | `%USERPROFILE%\.cursor\skills\amazon-review-analysis\` |
| Cursor（项目） | 项目下 `.cursor\skills\amazon-review-analysis\` |
| 其他支持 Agent Skills 的工具 | 按其「导入技能 / skills」目录放置本文件夹 |

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

仅需：`openpyxl`

### 4. 使用

在 Agent 对话中：

1. 上传 Amazon 评论 `.xlsx`
2. 说明：使用 **Amazon 评论分析**（可选填写产品名称、产品类目）
3. Agent 按 `SKILL.md` 执行脚本 + 模型两步，返回带 **评论分析结果** Sheet 的 Excel

## 输入 / 输出

**输入**

- `file`（必填）：xlsx
- `product_name`（可选）
- `product_category`（可选，最多一个）

**输出**

- 保留原表 Sheet
- 新增 Sheet：`评论分析结果`  
  列：类型 | 具体维度 | 提及评论数 | 提及频率 | 代表性反馈

## 环境要求

- Python 3.10+（推荐）
- 能运行终端命令的 Agent 环境
- Agent 已配置可用的大模型（用于提炼与归一）

## 目录说明

```
amazon-review-analysis/
  SKILL.md              # Agent 执行说明（安装后自动被工具加载）
  README.md             # 给人看的安装与使用说明
  LICENSE
  requirements.txt
  prompts/              # 提炼 / 归一 Prompt（自包含）
  scripts/              # 确定性 Python 步骤
    step1_prepare_extract.py
    step2_ingest_extract.py
    step3_prepare_normalize.py
    step4_finalize.py
    lib/
```

## 版本

1.0.0
