---
name: amazon-review-analysis-v4
description: >-
  Amazon review analysis V4: 8-dim dual-pass then one-shot AI overview summary.
  Left charts/panels, right summary. No product name/category required.
  Use for 评论分析 V4 / 八维 / AI总结 / 未被满足.
---

# Amazon 评论分析 V4

独立版本（分支 `v4-dev`）。八维双轮抽取 + **一次全量 AI 总结**。  
**不要求、不展示产品名称/类目**；只做八维汇总与总结。

## 八维

| 轮次 | 类型 |
|------|------|
| Pass1 画像 | 消费人群 · 使用地点 · 使用时刻 · 产品用途 · 使用场景 · 购买动机 |
| Pass2 满足 | 用户满意 · **未被满足** |
| Pass3 总结 | 基于 `summary.json` 一次生成八维总览文案 |

## 总览布局

- **左侧 A–M**：柱图（人群/用途/场景/动机）+ 地点|时刻列表 + 未被满足|满意列表  
- **右侧 O–S**：AI总结（全量）  
- 页眉仅「评论总数」；无洞察条目数/标准维度数/产品名字段  

## 执行流程

`SKILL_ROOT=d:\amazon_review_analysis_v4`

```bash
python "$SKILL_ROOT/scripts/step1_prepare.py" --input "reviews.xlsx" --workdir "$WORKDIR"
# AI → persona_batches/*/MODEL_OUTPUT.json
python "$SKILL_ROOT/scripts/step2_ingest_persona.py" --workdir "$WORKDIR"
# AI → fulfillment_batches/*/MODEL_OUTPUT.json
python "$SKILL_ROOT/scripts/step3_ingest_fulfillment.py" --workdir "$WORKDIR"
python "$SKILL_ROOT/scripts/step4_prepare_summary.py" --workdir "$WORKDIR"
# AI → overview_summary/MODEL_OUTPUT.json（八维全量总结，无需产品名）
python "$SKILL_ROOT/scripts/step5_finalize.py" --workdir "$WORKDIR" --output "评论洞察分析结果.xlsx"
```

不要因缺少产品名称/类目而中断。JSON 错误不能当成功。
