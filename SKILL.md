---
name: amazon-review-analysis-v2
description: >-
  Amazon review analysis V2 Beta: adaptive business-level dimension normalization,
  six-type statistics, Excel overview dashboard with horizontal bar charts, and a
  full 评论分析结果 sheet with representative feedback. Use when the user uploads
  Amazon reviews xlsx, asks for 评论分析 / VOC / Amazon review analysis V2, or wants
  评论分析总览 with charts.
---

# Amazon 评论分析 V2 Beta

通用 Agent Skill：语义由当前 Agent 模型完成，确定性结构由 Python 脚本完成。

> V1.0.2（`main`）为稳定版；本包为 **V2 Beta**（分支 `v2-dev`）。

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| file | 是 | Amazon 评论 xlsx |
| product_name | 否 | 产品名称 |
| product_category | 否 | 最多一个类目 |

ASIN 若存在于原表，仅保留原列，不参与分组/统计。

## 输出

保留用户原始 Sheet，仅新增两张分析 Sheet：

1. **评论分析总览**
   - 基础信息：产品名称/类目、评论总数、VOC提炼条目数、标准维度数
   - 六模块 Top：消费人群/产品用途/使用场景/购买动机 Top5；用户满意/用户不满 Top10
   - Excel 原生横向条形图（提及频率）
2. **评论分析结果**
   - 列：`类型` | `具体维度` | `提及评论数` | `提及频率` | `代表性反馈`
   - 完整维度；代表性反馈最多 5 条（真实单条提炼，不改写）

排序（结果 Sheet）：
1. 六类固定顺序：消费人群 → 产品用途 → 使用场景 → 购买动机 → 用户满意 → 用户不满
2. 同类型内按提及评论数从高到低
3. 同频再按具体维度名称

表头冻结 + 自动筛选已开启。不输出评论明细 Sheet。

## 分工

- **AI（Agent 当前模型）**：`提炼`、`维度归一`（reasoning 关闭；V2 自适应业务级归一）
- **Python**：读表、拼 `review_text`、校验 JSON、统计、写 Excel（含总览图表）

## 六类一级类型（固定）

消费人群 / 产品用途 / 使用场景 / 购买动机 / 用户满意 / 用户不满

具体维度动态产生，禁止用固定类目标签库限制分析。

## 安装

见 [README.md](README.md)。将本目录整体放入 Agent 的 skills 路径，并执行 `pip install -r requirements.txt`。

建议文件夹名：`amazon-review-analysis-v2`

## 执行流程（必须按序）

设本技能根目录为 `SKILL_ROOT`，工作目录为 `WORKDIR`（新建空目录）。

### Windows（PowerShell）示例

```powershell
$SKILL_ROOT = "$env:USERPROFILE\.cursor\skills\amazon-review-analysis-v2"
$WORKDIR = Join-Path $PWD "review_run"
python "$SKILL_ROOT\scripts\step1_prepare_extract.py" --input ".\reviews.xlsx" --workdir $WORKDIR
```

### 1) Python：准备提炼批次（每批最多 50 条）

```bash
python "$SKILL_ROOT/scripts/step1_prepare_extract.py" \
  --input "/path/to/reviews.xlsx" \
  --workdir "$WORKDIR" \
  --product-name "可选" \
  --product-category "可选"
```

### 2) AI：逐批提炼

对 `$WORKDIR/extract_batches/batch_XXXX/`：读取 `system.md` + `user.md`，调用模型，将严格 JSON 写入 `MODEL_OUTPUT.json`。

### 3) Python：校验合并提炼结果

```bash
python "$SKILL_ROOT/scripts/step2_ingest_extract.py" --workdir "$WORKDIR"
```

### 4) Python：准备归一（一口气一次）

```bash
python "$SKILL_ROOT/scripts/step3_prepare_normalize.py" --workdir "$WORKDIR"
```

### 5) AI：维度归一（仅一次）

对 `$WORKDIR/normalize/`：使用 `system.md` + `user.md` 调用模型一次，写入 `MODEL_OUTPUT.json`（顶层 `mappings`）。

### 6) Python：统计并写出 Excel（总览 + 结果）

```bash
python "$SKILL_ROOT/scripts/step4_finalize.py" \
  --workdir "$WORKDIR" \
  --output "/path/to/评论分析结果.xlsx"
```

将结果文件返回给用户。

## 统计口径（Python）

- 键：类型 + 标准维度（具体维度 = 标准维度）  
- 提及评论数：该维度对应的不同评论数（同评论同维度最多计 1）  
- 提及频率：提及评论数 / **上传评论总数** × 100%（空评、`items=[]` 计入分母）  
- 代表性反馈：从模块1真实「单条提炼」取最多 **5** 条，不改写，去重，优先不同评论，按原表顺序，用「；」拼接

## 硬约束

- JSON 错误不能当成功  
- review_id 缺失不能自动补空  
- 归一 mapping 缺失不能 identity fallback  
- 输出截断不能当成功  

## Prompt 文件

- `prompts/extract_system.md` / `extract_user.md`  
- `prompts/normalize_system.md` / `normalize_user.md`  

不要改写 Prompt 业务逻辑；Agent 只负责按文件调用模型。
