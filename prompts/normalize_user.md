下面是已完成结构化提炼的维度清单（按一级类型隔离；可能仅含本批类型）。
语义参考最多 3 条，优先来自不同评论。

{{voc_items}}

请完成：
1. 只在同一「类型」内归一；禁止跨类型合并
2. 仅当业务含义一致且改进动作一致时才合并
3. 禁止合并相反问题（尺寸偏大≠尺寸偏小、太硬≠太软、太紧≠太松、太重≠太轻、太长≠太短、太亮≠太暗、安装过松≠安装过紧）
4. 禁止把相反问题归并为「尺寸问题 / 硬度问题 / 安装问题」等空泛属性
5. 优先把高频写法（提及次数更高）定为标准维度名
6. 每个输入原始维度必须返回一个标准维度
7. 不生成任何总结、核心描述或产品建议

必须严格按下方 Output Schema 返回合法 JSON。
顶层键必须是 mappings（禁止使用 归一结果、dimensions 或其他键名）。
每个映射对象必须使用中文字段名：类型、原始维度、标准维度。

Output Schema:
{"type":"object","properties":{"mappings":{"type":"array","items":{"type":"object","properties":{"类型":{"type":"string","enum":["消费人群","使用地点","使用时刻","产品用途","使用场景","购买动机","用户满意","未被满足"]},"原始维度":{"type":"string"},"标准维度":{"type":"string"}},"required":["类型","原始维度","标准维度"],"additionalProperties":false}}},"required":["mappings"],"additionalProperties":false}

除 JSON 外不要输出其他内容。
