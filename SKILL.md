---
name: amazon-review-analysis-v2
description: >-
  Amazon review analysis V2 Beta: adaptive business-level dimension normalization,
  six-type statistics, Excel overview dashboard with column charts (2×3 grid), and a
  full 评论分析结果 sheet with representative feedback. Default: upload reviews xlsx
  and run — product_name / product_category are optional. Use when the user uploads
  Amazon reviews xlsx, asks for 评论分析 / VOC / Amazon review analysis V2, or wants
  评论分析总览 with charts.
---

# Amazon 评论分析 V2 Beta

通用 Agent Skill：语义由当前 Agent 模型完成，确定性结构由 Python 脚本完成。

> V1.0.2（`main`）为稳定版；本包为 **V2 Beta**（分支 `v2-dev`）。

## 默认使用方式

**上传 Amazon 评论 Excel → 直接运行。**

- 不要求用户填写产品名称、产品类目。
- 不得因缺少 `product_name` / `product_category` 询问用户或中断流程。
- 二者为可选增强：用户主动提供时使用；或从 Excel 中可靠读取到单一值时自动填入；否则保持为空，直接基于评论文本分析。
- 禁止为补产品名称/类目新增 AI 调用。

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| file | 是 | Amazon 评论 xlsx |
| product_name | 否 | 可选增强；不填也可跑 |
| product_category | 否 | 可选增强；最多一个类目 |

ASIN 若存在于原表，仅保留原列，不参与分组/统计。

## 输出

保留用户原始 Sheet（名称/顺序/数据/格式不变），在**工作簿末尾**追加两张分析 Sheet：

1. **评论分析总览**（Dashboard）
   - 基础信息（标题下单行）：有产品名称/类目才显示；评论总数、评论洞察条目数、标准维度数
   - 上半 2×2：消费人群 / 产品用途 / 使用场景 / 购买动机（可读命名；柱=%；图下明细含 提及数/评论总数 + 代表反馈；可重叠）
   - **需求满足分析**（下半两栏）：用户满意 / 未被满足——频率展示为 `x%（n/总数）`
   - 无数据模块显示「暂无足够评论证据」，不画空坐标图
   - 图表数据源写入隐藏列（X:AE）
2. **评论分析结果**
   - 列：`类型` | `具体维度` | `提及评论数` | `提及频率` | `代表性反馈`
   - 完整维度（含提及=1 的长尾，便于审计）；代表性反馈最多 5 条
   - 类型列对外展示：「用户不满」显示为「未被满足」

Sheet 顺序（强制）：

```
[所有用户原始 Sheet，原顺序] → 评论分析总览 → 评论分析结果
```

若输入已含旧分析 Sheet（评论分析总览 / 评论分析结果 / VOC分析结果 / VOC评论明细），先删除再重新追加到末尾。

排序（结果 Sheet）：
1. 六类固定顺序：消费人群 → 产品用途 → 使用场景 → 购买动机 → 用户满意 → 用户不满（展示为未被满足）
2. 同类型内按提及评论数从高到低
3. 同频再按具体维度名称

表头冻结 + 自动筛选已开启。不输出评论明细 Sheet。

## 分工

- **AI（Agent 当前模型）**：`提炼`、`维度聚合归一`（reasoning 关闭；V2 以「业务可直接使用、无需再人工聚合」为目标）
- **Python**：读表、拼 `review_text`、校验 JSON、统计、写 Excel（含总览图表）

> 对外统称 **评论洞察**。若结果仍明显碎散、需要使用者再合并，视为归一失败，应加强同方面聚合后重跑，而不是接受细碎清单。

## 六类一级类型（固定）

内部键：消费人群 / 产品用途 / 使用场景 / 购买动机 / 用户满意 / 用户不满  

对外展示：用户不满 → **未被满足**（仅展示层；Prompt / 统计口径不变）

具体维度动态产生，禁止用固定类目标签库限制分析。

质量边界（全类目通用；抽取守类型，归一只做同类型合并）：

- **消费人群 / 使用场景**：强聚合 + 可读命名（可用通用大类前缀）；总览图下含提及数/总数与代表反馈
- **产品用途 / 购买动机**：细粒度；动机接受买前句偏少；总览同样展示分子分母与代表反馈
- **用途 vs 满意**：有「用来做什么」必须提用途；效果好另算满意，不能互相替代
- **购买动机**：买前因果；购后正负评价分别进满意/不满
- **满意 / 不满**：同一业务轴偏强合并；总览频率为 `x%（n/总数）`

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
  --workdir "$WORKDIR"
```

可选增强（不要主动向用户索要）：

```bash
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
- 不要因缺少产品名称/类目而询问用户  

## Prompt 文件

- `prompts/extract_system.md` / `extract_user.md`  
- `prompts/normalize_system.md` / `normalize_user.md`  

不要改写 Prompt 业务逻辑；Agent 只负责按文件调用模型。
