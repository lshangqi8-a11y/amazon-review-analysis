# Amazon 评论分析 Skill V2 Beta

独立发布包：下载 → 安装到 Agent skills 目录 → `pip install -r requirements.txt` → **上传评论 Excel 即可使用**（无需填写产品名称/类目）。

不依赖本公司 Flask / AI Gateway / 数据库。语义分析由你当前 Agent 所选模型完成；读表、校验、统计、出 Excel 由本包 Python 脚本完成。

## 版本说明

| 版本 | 分支 | 说明 |
|------|------|------|
| **V1.0.2** | `main` | 稳定版 |
| **V2 `2.0.0-beta.1`** | `v2-dev` | Beta：自适应业务归一 + Excel 图表总览 |

## V2 新增

1. 自适应业务级维度归一（消费人群/使用场景颗粒度优化）
2. Excel **评论分析总览** Dashboard（上 2×2 柱状图 + 下双栏 DataBar 反馈；无可见数据表）
3. 完整 **评论分析结果**（含代表性反馈最多 5 条）
4. 对外展示「用户不满」→「未被满足」
5. 产品名称/类目可选；默认只上传 Excel 即可跑

## 安装（同事按此操作）

### 1. 获取本包

```bash
git clone -b v2-dev https://github.com/lshangqi8-a11y/amazon-review-analysis.git amazon-review-analysis-v2
```

或从 GitHub 切换到 `v2-dev` 后下载 ZIP。

### 2. 安装到 Agent 工具

文件夹名建议：`amazon-review-analysis-v2`

| 工具 | 路径示例 |
|------|----------|
| Cursor（个人） | `%USERPROFILE%\.cursor\skills\amazon-review-analysis-v2\` |
| Cursor（项目） | 项目下 `.cursor\skills\amazon-review-analysis-v2\` |
| 其他支持 Agent Skills 的工具 | 按其「导入技能 / skills」目录放置本文件夹 |

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

仅需：`openpyxl`

### 4. 使用

1. 上传 Amazon 评论 `.xlsx`（**唯一必填输入**）
2. 说明：使用 **Amazon 评论分析 V2**（产品名称、产品类目可选，不要主动索要）
3. Agent 按 `SKILL.md` 执行，返回含 **评论分析总览** + **评论分析结果** 的 Excel

## 输入 / 输出

**输入**

- `file`（必填）：xlsx
- `product_name`（可选增强，不要求填写）
- `product_category`（可选增强，最多一个）

**输出 Sheet 顺序**

```
[原始 Sheet…] → 评论分析总览 → 评论分析结果
```

- 总览 Dashboard：上 2×2 柱状图；下「未被满足 | 用户满意」DataBar 面板；辅助列隐藏
- 结果：完整维度表，无图表；类型列展示「未被满足」

## 环境要求

- Python 3.10+（推荐）
- 能运行终端命令的 Agent 环境
- Agent 已配置可用的大模型（用于提炼与归一）

## 目录说明

```
amazon-review-analysis-v2/
  SKILL.md
  README.md
  LICENSE
  VERSION
  requirements.txt
  prompts/
  scripts/
    step1_prepare_extract.py
    step2_ingest_extract.py
    step3_prepare_normalize.py
    step4_finalize.py
    lib/
```

## 版本

2.0.0-beta.1
