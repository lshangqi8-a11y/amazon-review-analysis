产品名称：
{{product_name}}

产品类目：
{{product_category}}

下面是第一阶段已经完成结构化提炼的 VOC 维度：

{{voc_items}}

请完成：

1. 按一级类型隔离处理
2. 将语义真正一致的原始维度归一
3. 不同业务含义禁止强行合并
4. 每个输入原始维度必须返回一个标准维度
5. 不生成任何总结、核心描述或产品建议

必须严格按下方 Output Schema 返回合法 JSON。
顶层键必须是 mappings（禁止使用 归一结果、dimensions 或其他键名）。
每个映射对象必须使用中文字段名：类型、原始维度、标准维度。

Output Schema：
{"type":"object","properties":{"mappings":{"type":"array","items":{"type":"object","properties":{"类型":{"type":"string","enum":["消费人群","产品用途","使用场景","购买动机","用户满意","用户不满"]},"原始维度":{"type":"string"},"标准维度":{"type":"string"}},"required":["类型","原始维度","标准维度"],"additionalProperties":false}}},"required":["mappings"],"additionalProperties":false}

除 JSON 外不要输出其他内容。
