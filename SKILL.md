---
name: amazon-review-analysis-v3
description: >-
  Amazon review analysis V3: dual-pass pipeline — (1) consumer persona
  (audience/usage/scene/motive) then (2) need fulfillment (satisfied/unmet).
  Reuses Excel overview dashboard. Use for 评论分析 / 消费者画像 / 未被满足 /
  用户满意 / Amazon review analysis V3.
---

# Amazon 评论分析 V3

独立新版本。目标：支撑**消费者画像** + **满意/未被满足**，输出可审计、可支撑产品形态落地。

> V1 / V2 为旧版；本包为 **V3**（分支 `v3-dev`）。不要用 V2「六类一次抽」思维。

## 业务目标（默认由专业方案执行，无需用户选题）

1. **消费者画像**：谁、干什么、在哪、为何买  
2. **用户满意**：可保留的优势  
3. **未被满足**：改进方向  
4. Excel 总览图表沿用已验证样式（柱顶 `频率%（n/总数）`）

## 与 V2 的关键差异

| | V2 | V3 |
|--|----|----|
| 抽取 | 六类一次抽 | **两轮**：先画像，再满足 |
| 归一 AI | 有 | **无**（标签在抽取中约束 + 代码门禁） |
| 动机为空 | 常被当成失败 | **允许**（无买前证据不上图） |
| 输出 | 总览+结果 | 同左（复用 excel 层） |

## 默认使用

**上传评论 Excel → 按下方步骤跑通。**  
不要因缺少产品名称/类目而中断。

## 执行流程

设 `SKILL_ROOT=d:\amazon_review_analysis_v3`，`WORKDIR` 为新建空目录。

### 1) 准备双轮批次

```bash
python "$SKILL_ROOT/scripts/step1_prepare.py" --input "reviews.xlsx" --workdir "$WORKDIR"
```

生成：`persona_batches/`、`fulfillment_batches/`、`meta.json`、`reviews.json`。

### 2) AI 第一轮：消费者画像

对每个 `persona_batches/batch_XXXX/`：读 `system.md` + `user.md`，写入 `MODEL_OUTPUT.json`。  
类型仅限：消费人群 / 产品用途 / 使用场景 / 购买动机。

### 3) 入库画像

```bash
python "$SKILL_ROOT/scripts/step2_ingest_persona.py" --workdir "$WORKDIR"
```

### 4) AI 第二轮：需求满足

对每个 `fulfillment_batches/batch_XXXX/`：写入 `MODEL_OUTPUT.json`。  
类型仅限：用户满意 / 用户不满。

### 5) 入库满足

```bash
python "$SKILL_ROOT/scripts/step3_ingest_fulfillment.py" --workdir "$WORKDIR"
```

### 6) 出 Excel

```bash
python "$SKILL_ROOT/scripts/step4_finalize.py" --workdir "$WORKDIR" --output "评论洞察分析结果.xlsx"
```

## 输出

保留原 Sheet，末尾追加：

1. **评论分析总览** — 画像 2×2 + 满意/未被满足  
2. **评论分析结果** — 明细可审计  

## Prompt

- `prompts/persona_system.md` / `persona_user.md`  
- `prompts/fulfillment_system.md` / `fulfillment_user.md`  

## 硬约束

- JSON 错误不能当成功  
- review_id 缺失不能补空  
- 画像轮禁止出现满意/不满类型；满足轮禁止出现画像四类  
- 不要因缺少产品名称/类目询问用户  
