# Amazon 评论分析 V5 — Review Intelligence

WorkBuddy / Cursor 可用的独立技能包：
**8 维双轮抽取 → AI 维度归一 → Python 统计 → 一次 Review Intelligence → Excel**。

在基础评论洞察之上输出产品决策分析（属性表现、痛点优先级、产品机会、改进建议）。
不要求产品名称/类目。

## 快速开始

1. 下载或 clone 本仓库，将根目录作为 `SKILL_ROOT`
2. `pip install -r requirements.txt`
3. 按 [SKILL.md](SKILL.md) 的 7 步流程执行（Agent 串行填写各批 `MODEL_OUTPUT.json`）

## 版本

见 [VERSION](VERSION)。许可证见 [LICENSE](LICENSE)。

## 不要提交

任务产物（`_workdir/`）、本地 Agent 记忆（`.workbuddy/`）已在 `.gitignore` 中排除。
