---
name: amazon-review-analysis-v5
description: >-
  Amazon review analysis V5 Review Intelligence: 8-dim dual-pass, AI normalize,
  one-shot intelligence (attribute / pain / opportunity / recommendations),
  Excel overview + decision + copyable AI summary.
  No product name/category required.
  Use for 评论分析 V5 / Review Intelligence / 八维 / 维度归一 / 产品决策 / 痛点优先级.
---

# Amazon 评论分析 V5 — Review Intelligence

**八维双轮抽取 → AI 维度归一 → Python 统计 → 一次 Review Intelligence → Excel**。
在基础评论洞察之上增加产品决策分析。不要求、不展示产品名称/类目。版本见 `VERSION`。

将本仓库根目录作为 `SKILL_ROOT`（WorkBuddy / Cursor Skill 下载后的技能包路径）。

## ⛔ 硬性约束（不可违反）

1. **禁止使用子代理 / 并行 Agent** 处理任何批次。全程仅由主会话串行执行：逐个批次「读 `user.md` → 写 `MODEL_OUTPUT.json`」。
2. 中断后必须用 `--allow-partial` 续跑，**不得**开子代理补跑缺失批次。
3. 抽取与归一都依赖同一会话串行统一标签；任何并行都会导致标签碎片化，一律视为执行错误。
4. **不要为四个决策模块分别调用 AI**；只在最后一次 `review_intelligence` 一次输出。

## 八维（一级类型冻结）

| 轮次 | 类型 |
|------|------|
| Pass1 画像 | 消费人群 · 使用地点 · 使用时刻 · 产品用途 · 使用场景 · 购买动机 |
| Pass2 满足 | 用户满意 · **未被满足**（含信号类型） |
| Pass3 **归一** | 按类型将近义「原始维度」合并为「标准维度」（业务含义+改进动作一致才合并） |
| Pass4 Intelligence | 八维总结 + 属性表现 + 痛点优先级 + 产品机会 + 改进建议 |

尺寸/包装/价格/材质等属于属性层，**不**新增为一级维度。

## 消费人群深度分析（Python + Step6 解释）

流程保持简单：

```text
消费人群发现 → n / 占比 → 人群内部用途·场景·动机·满意·未满足·属性
→ 人群间百分比差异 pp →（可选）联网解释 → 产品开发启发
```

规则：
- n≥1 即可分析；Excel 展示 n，由使用者自行判断样本量
- **不做** Fisher / χ² / p value / 显著性门槛
- 人群产品机会的 `review_evidence` 必须与该人群共现于同一条评论
- 禁止把全 ASIN 痛点随意归给某人群

### 联网研究（仍在 Step6 一次 Intelligence 内完成，不新增 AI Pass）

当运行环境**具有联网搜索能力**时：
- 主 Agent 在填写 `review_intelligence/MODEL_OUTPUT.json` 时，可根据人群差异主动检索公开资料
- 用途：解释消费人群差异、辅助产品开发假设
- 必须保存 `source_title` / `source_url` / `finding`
- 外部资料**不得**修改 Review 内部统计数字

当运行环境**没有联网能力**时：
- `external_research_status = "unavailable"`
- `external_research = []`
- **不得**因此中断整个 Skill，也不得伪造来源

## 百分比规则

```text
mention_rate = 命中该维度的唯一有效评论数 / analyzed_reviews × 100%
```

- 分母 = `analyzed_reviews`（实际参与 AI 分析的有效评论）
- `total_reviews` 仅作审计
- 同一 Review 对同一标准维度只计 1 次

## Excel 结构

分析 Sheet 放在最后：

1. 评论分析总览 — 八维图表/面板 + AI 概览
2. 产品决策分析 — 属性 / 痛点 / 机会 / 建议
3. 消费人群深度分析 — 人群发现 / 差异 / 外部研究 / 细分开发方向
4. AI总结 — A2 纯文本可一键复制
5. 评论分析结果 — 命中数审计

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
# AI → fulfillment_batches/*/MODEL_OUTPUT.json（含信号类型）
python "$SKILL_ROOT/scripts/step3_ingest_fulfillment.py" --workdir "$WORKDIR"

python "$SKILL_ROOT/scripts/step4_prepare_normalize.py" --workdir "$WORKDIR"
# AI → normalize_batches/*/MODEL_OUTPUT.json（按类型串行归一，禁止并行）
python "$SKILL_ROOT/scripts/step5_ingest_normalize.py" --workdir "$WORKDIR"

python "$SKILL_ROOT/scripts/step6_prepare_summary.py" --workdir "$WORKDIR"
# AI → review_intelligence/MODEL_OUTPUT.json
python "$SKILL_ROOT/scripts/step7_finalize.py" --workdir "$WORKDIR" --output "评论洞察分析结果.xlsx"
```

不要因缺少产品名称/类目而中断。JSON 错误不能当成功。

重跑 `step4_prepare_normalize` / `step6_prepare_summary` 时，**已填写的 `MODEL_OUTPUT.json` 默认保留**；若 Intelligence 输入 hash 变化则自动失效。强制清空加 `--force-reset`。

`review_intelligence` 的 `input_hash` = `SHA256(system_prompt + user_prompt + schema_version)`，即基于实际送给 AI 的内容。

`step1`：workdir 非空时默认拒绝覆盖，必须显式 `--force`。

## 大批量与断点续跑

1. **切小批次**：`step1_prepare.py --chunk-size 15`（默认 50）。
2. **抽取续跑**：`step2` / `step3 --allow-partial`。
3. **归一续跑**：`step5_ingest_normalize.py --allow-partial`（未完成类型暂时保持原维度名）。

**加速只能靠调小 `--chunk-size` 或分会话，禁止开子代理并行。**

## 本地冒烟（可选）

```bash
python "$SKILL_ROOT/scripts/_e2e_fake.py" --input reviews.xlsx --workdir ./tmp_v5_e2e --output ./out.xlsx --force
python "$SKILL_ROOT/scripts/test_v5_pipeline.py"
```
