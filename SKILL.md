---
name: amazon-review-analysis-v6
description: >-
  Amazon review analysis V6: V4 8-dim dual-pass + AI normalize + overview summary,
  plus consumer segment insight (who buys / persona / product direction) with
  optional web research. Excel percentages + copyable AI summary sheet.
  No product name/category required.
  Use for 评论分析 V6 / 八维 / 维度归一 / 消费人群洞察 / AI总结.
---

# Amazon 评论分析 V6 — 消费人群洞察

**V4 稳定主流程 + 总览构成占比柱图 + 一次消费人群洞察**。  
不要求、不展示产品名称/类目（仅消费人群洞察模块可注入产品上下文）。版本见 `VERSION`。

将本仓库根目录作为 `SKILL_ROOT`（WorkBuddy / Cursor Skill 下载后的技能包路径）。

## ⛔ 硬性约束（不可违反）

1. **禁止使用子代理 / 并行 Agent** 处理任何批次。全程仅由主会话串行执行：逐个批次「读 `user.md` → 写 `MODEL_OUTPUT.json`」。
2. 中断后必须用 `--allow-partial` 续跑，**不得**开子代理补跑缺失批次。
3. 抽取与归一都依赖同一会话串行统一标签；任何并行都会导致标签碎片化，一律视为执行错误。
4. **不要引入 V5 产品决策分析**（属性表现 / 痛点优先级 / 产品机会 / 改进建议那套）。
5. 消费人群洞察中的评论覆盖率由 Python 计算；AI 不得改数字、不得发明未知人群。

## 八维（与 V4 相同，一级类型冻结）

| 轮次 | 类型 |
|------|------|
| Pass1 画像 | 消费人群 · 使用地点 · 使用时刻 · 产品用途 · 使用场景 · 购买动机 |
| Pass2 满足 | 用户满意 · **未被满足** |
| Pass3 **归一** | 按类型将近义「原始维度」合并为「标准维度」 |
| Pass4 总结 | 基于归一后的 `summary.json` 一次生成八维总览文案 |
| Pass5 人群洞察 | Python 核心人群统计 + **一次**消费人群洞察（可联网） |

## 消费人群洞察（唯一新增业务模块）

只回答：谁在买？这些人是什么样的人？产品应该怎么做？

1. **核心购买人群**（Python）：Top 5（不足则全出），评论数 / 评论覆盖率 / 高频组合画像  
2. **核心人群画像洞察**（AI）：评论中表现 + 行为/性格/习惯/需求 + 外部来源  
3. **产品开发方向**（AI）：必须具备的功能点 + 应建立的产品壁垒  

### 联网研究（硬要求）

当存在核心消费人群且运行环境**可联网**时：Agent **应主动**检索公开资料，填写 `sources`，`external_research_status=ok`。  
外部知识不得修改评论统计。无联网时：`unavailable` 且不得伪造来源，主流程继续。

## 百分比规则

```text
评论分析总览柱状图（模块内部构成占比）=
该维度提及评论数 / 当前模块展示维度提及评论数之和

评论分析结果 / 人群覆盖率 =
unique reviews / analyzed_reviews × 100%
```

两种口径不要混用。Excel 百分比存分数（如 `0.833`），`number_format = 0.0%`。

## Excel 结构

1. 评论分析总览 — 左图（模块内部构成占比）右文（AI总结，可局部复制）
2. 消费人群洞察 — 核心消费人群 / 核心人群画像 / 产品开发方向
3. 评论分析结果 — 评论覆盖率审计（unique / analyzed_reviews）

不再输出独立「AI总结」Sheet。

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

python "$SKILL_ROOT/scripts/step6b_prepare_segment_insight.py" --workdir "$WORKDIR"
# AI → consumer_segment_insight/MODEL_OUTPUT.json（可联网则必须外部研究）

python "$SKILL_ROOT/scripts/step7_finalize.py" --workdir "$WORKDIR" --output "评论洞察分析结果.xlsx"
```

不要因缺少产品名称/类目而中断。JSON 错误不能当成功。

重跑 `step4_prepare_normalize` / `step6_prepare_summary` / `step6b_prepare_segment_insight` 时，**已填写的 `MODEL_OUTPUT.json` 默认保留**；强制清空加 `--force-reset`。

## 大批量与断点续跑

1. **切小批次**：`step1_prepare.py --chunk-size 15`（默认 50）。
2. **抽取续跑**：`step2` / `step3 --allow-partial`。
3. **归一续跑**：`step5_ingest_normalize.py --allow-partial`（未完成类型暂时保持原维度名）。

**加速只能靠调小 `--chunk-size` 或分会话，禁止开子代理并行。**

## 本地冒烟（可选）

```bash
python "$SKILL_ROOT/scripts/_e2e_fake.py" --input reviews.xlsx --workdir ./tmp_v6_e2e --output ./out.xlsx --force
python "$SKILL_ROOT/scripts/test_v4_pipeline.py"
python "$SKILL_ROOT/scripts/test_v6_pipeline.py"
```
