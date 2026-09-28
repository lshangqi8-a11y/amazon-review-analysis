# Amazon 评论分析 V6

WorkBuddy / Cursor 可用的独立技能包：  
**V4 八维双轮抽取 → AI 维度归一 → AI 总结 + 消费人群洞察 → Excel**。

在 V4 稳定分析之上，优化百分比展示与 AI 总结复制体验，并新增「消费人群洞察」模块。  
不要求产品名称/类目。不含 V5 产品决策分析。

## 快速开始

1. 下载或 clone 本仓库（建议 tag `v6.0.0`），将根目录作为 `SKILL_ROOT`
2. `pip install -r requirements.txt`
3. 按 [SKILL.md](SKILL.md) 流程执行（Agent 串行填写各批 `MODEL_OUTPUT.json`）

## 版本

见 [VERSION](VERSION)。许可证见 [LICENSE](LICENSE)。

## 不要提交

任务产物（`_workdir/`）、本地 Agent 记忆（`.workbuddy/`）已在 `.gitignore` 中排除。
