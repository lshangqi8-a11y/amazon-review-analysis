# Amazon 评论分析 V6

WorkBuddy / Cursor **独立技能包**（与 V4 并存，不要覆盖 V4 目录）：  
**V4 八维双轮抽取 → AI 维度归一 → Overview AI 总结 + 消费人群洞察 → Excel**。

在 V4 稳定分析之上，优化总览构成占比柱图，并新增「消费人群洞察」模块。  
不要求产品名称/类目（仅消费人群洞察可注入产品上下文）。不含 V5 产品决策分析。

## WorkBuddy 安装（独立于 V4）

1. 下载正式技能包 zip（根目录名必须是 `amazon-review-analysis-v6`）
2. 解压到 skills 目录，得到独立文件夹：
   `.../skills/amazon-review-analysis-v6/`
3. **不要**解压进 / 覆盖 `amazon-review-analysis` 或 `amazon-review-analysis-v4`
4. 确认该目录下有：`SKILL.md`、`VERSION(=6.0.0)`、`scripts/`、`prompts/`
5. `pip install -r requirements.txt`
6. 触发技能名：`amazon-review-analysis-v6`

## 快速开始

1. 将本技能根目录作为 `SKILL_ROOT`
2. `pip install -r requirements.txt`
3. 按 [SKILL.md](SKILL.md) 流程执行（Agent 串行填写各批 `MODEL_OUTPUT.json`）

## 版本

见 [VERSION](VERSION)。许可证见 [LICENSE](LICENSE)。

## 不要提交

任务产物（`_workdir/`）、本地 Agent 记忆（`.workbuddy/`）已在 `.gitignore` 中排除。
