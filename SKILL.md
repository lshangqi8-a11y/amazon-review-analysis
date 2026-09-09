---
name: amazon-review-analysis-v4
description: >-
  Amazon review analysis V4: 8-dim dual-pass, AI dimension normalize, then
  one-shot AI overview summary. Left charts/panels, right summary.
  No product name/category required.
  Use for 评论分析 V4 / 八维 / 维度归一 / AI总结 / 未被满足.
---

# Amazon 评论分析 V4

**八维双轮抽取 → AI 维度归一 → 一次全量 AI 总结**。  
**不要求、不展示产品名称/类目**。版本见 `VERSION`。

将本仓库根目录作为 `SKILL_ROOT`（WorkBuddy / Cursor Skill 下载后的技能包路径）。

## ⛔ 硬性约束（不可违反）

1. **禁止使用子代理 / 并行 Agent** 处理任何批次。全程仅由主会话串行执行：逐个批次「读 `user.md` → 写 `MODEL_OUTPUT.json`」。
2. 中断后必须用 `--allow-partial` 续跑，**不得**开子代理补跑缺失批次。
3. 抽取与归一都依赖同一会话串行统一标签；任何并行都会导致标签碎片化，一律视为执行错误。

## 八维

| 轮次 | 类型 |
|------|------|
| Pass1 画像 | 消费人群 · 使用地点 · 使用时刻 · 产品用途 · 使用场景 · 购买动机 |
| Pass2 满足 | 用户满意 · **未被满足** |
| Pass3 **归一** | 按类型将近义「原始维度」合并为「标准维度」（通用、偏合并） |
| Pass4 总结 | 基于归一后的 `summary.json` 一次生成八维总览文案 |

## 为何需要 AI 归一

抽取阶段即使提示「同义复用」，跨批次仍易产生近义微标签。  
**全局通用做法**：在统计出表前加一轮模型归一（按一级类型隔离、大胆合并），而不是维护品类同义词表。

总览仍限制各维 Top N 柱图，避免审查页过载。

## 总览布局

- **左侧 A–N**：柱图（人群/用途/场景/动机）+ 地点|时刻列表 + 未被满足|满意列表  
- **右侧 O–U**：AI总结（全量）  
- 页眉仅「评论总数」

## 依赖

```bash
pip install -r requirements.txt
```

## 执行流程

```bash
SKILL_ROOT="<本技能包根目录>"
WORKDIR="<任务工作目录>"

python "$SKILL_ROOT/scripts/step1_prepare.py" --input "reviews.xlsx" --workdir "$WORKDIR"
# AI → persona_batches/*/MODEL_OUTPUT.json
python "$SKILL_ROOT/scripts/step2_ingest_persona.py" --workdir "$WORKDIR"
# AI → fulfillment_batches/*/MODEL_OUTPUT.json
python "$SKILL_ROOT/scripts/step3_ingest_fulfillment.py" --workdir "$WORKDIR"

python "$SKILL_ROOT/scripts/step4_prepare_normalize.py" --workdir "$WORKDIR"
# AI → normalize_batches/*/MODEL_OUTPUT.json（按类型串行归一，禁止并行）
python "$SKILL_ROOT/scripts/step5_ingest_normalize.py" --workdir "$WORKDIR"

python "$SKILL_ROOT/scripts/step6_prepare_summary.py" --workdir "$WORKDIR"
# AI → overview_summary/MODEL_OUTPUT.json
python "$SKILL_ROOT/scripts/step7_finalize.py" --workdir "$WORKDIR" --output "评论洞察分析结果.xlsx"
```

不要因缺少产品名称/类目而中断。JSON 错误不能当成功。

重跑 `step4_prepare_normalize` / `step6_prepare_summary` 时，**已填写的 `MODEL_OUTPUT.json` 默认保留**；只有占位符会被刷新。若要强制清空重填，加 `--force-reset`。

## 大批量与断点续跑

1. **切小批次**：`step1_prepare.py --chunk-size 15`（默认 50）。
2. **抽取续跑**：`step2` / `step3 --allow-partial`。
3. **归一续跑**：`step5_ingest_normalize.py --allow-partial`（未完成类型暂时保持原维度名）。

**加速只能靠调小 `--chunk-size` 或分会话，禁止开子代理并行。**

## 本地冒烟（可选）

```bash
python "$SKILL_ROOT/scripts/_e2e_fake.py" --input reviews.xlsx --workdir ./tmp_v4_e2e --output ./out.xlsx --force
python "$SKILL_ROOT/scripts/test_v4_pipeline.py"
```
