产品名称：
{{product_name}}

产品类目：
{{product_category}}

下面是第一阶段已结构化提炼的评论洞察维度：

{{voc_items}}

请按 system 规则完成业务聚合归一，使结果可直接给业务阅读，无需使用者再人工合并：
1. 按一级类型隔离（禁止跨类型改类；错放类型只能在同类型内把近义合并干净）
2. 按判断顺序：同义近义/同方面措辞 → 叠词归主方面 → 清晰上位 → 是否影响产品决策 → 不确定时同方面优先合并
3. 消费人群强制：「X使用」=「适合X」；用户满意/不满偏强聚合（同优势/同痛点并成一条）；禁止保留大量近义细行
4. 区分「新增事实」（禁止）与「上位业务抽象」（允许且须可靠）
5. 禁止为减行生成过宽空标签（质量问题/综合问题等）
6. 每个输入原始维度必须返回一个标准维度；同类型同标准维度字符串必须一致
7. 不生成总结、核心描述或产品建议

必须严格按下方 Output Schema 返回合法 JSON。
顶层键必须是 mappings。
每个映射对象必须使用中文字段：类型、原始维度、标准维度。

Output Schema：
{"type":"object","properties":{"mappings":{"type":"array","items":{"type":"object","properties":{"类型":{"type":"string","enum":["消费人群","产品用途","使用场景","购买动机","用户满意","用户不满"]},"原始维度":{"type":"string"},"标准维度":{"type":"string"}},"required":["类型","原始维度","标准维度"],"additionalProperties":false}}},"required":["mappings"],"additionalProperties":false}

除 JSON 外不要输出其他内容。
