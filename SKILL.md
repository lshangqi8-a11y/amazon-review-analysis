---
name: amazon-review-analysis-v4
description: >-
  Amazon review analysis V4: 8-dimension dual-pass — persona
  (audience/location/time/purpose/scene/motive) then fulfillment
  (satisfied/unmet). Same Excel column-chart style for all 8 dims.
  Use for 评论分析 V4 / 八维 / 使用地点 / 使用时刻 / 未被满足.
---

# Amazon 评论分析 V4

独立版本（分支 `v4-dev`）。在 V3 双轮基础上升为 **8 维**，总览八图统一柱状样式。

> V3（`amazon_review_analysis_v3`）保留对照；本包为 V4。

## 八维

| 轮次 | 类型 |
|------|------|
| Pass1 画像 | 消费人群 · 使用地点 · 使用时刻 · 产品用途 · 使用场景 · 购买动机 |
| Pass2 满足 | 用户满意 · **未被满足** |

互斥要点：地点=空间，时刻=时间，场景=事务场合，用途=任务动作。动机无买前证据可空。

## 图表

- 画像六维：总览 **3×2** 柱状图（标题如 `消费人群（8）`，柱顶 `n%（n/总数）`）
- **用户满意 / 未被满足**：双栏可审计列表（维度 | 色条 | 频率 | 主题摘要），不用细柱图

## 执行流程

`SKILL_ROOT=d:\amazon_review_analysis_v4`

```bash
python "$SKILL_ROOT/scripts/step1_prepare.py" --input "reviews.xlsx" --workdir "$WORKDIR"
# 若 workdir 已存在且非本流水线目录，需加 --force；本流水线旧目录可直接覆盖
# AI → persona_batches/*/MODEL_OUTPUT.json
python "$SKILL_ROOT/scripts/step2_ingest_persona.py" --workdir "$WORKDIR"
# AI → fulfillment_batches/*/MODEL_OUTPUT.json
python "$SKILL_ROOT/scripts/step3_ingest_fulfillment.py" --workdir "$WORKDIR"
python "$SKILL_ROOT/scripts/step4_finalize.py" --workdir "$WORKDIR" --output "评论洞察分析结果.xlsx"
```

不要因缺少产品名称/类目而中断。JSON 错误或 review_id 缺失不能当成功。
