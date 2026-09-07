产品名称：
{{product_name}}

产品类目：
{{product_category}}

下面是第一阶段已结构化提炼的 VOC 维度：

{{voc_items}}

请按 system 规则完成自适应业务归一：
1. 按一级类型隔离
2. 按判断顺序：同义近义 → 清晰上位概念 → 是否影响产品开发决策 → 不确定时人群/场景可适度上位、满意/不满优先保留
3. 区分「新增事实」（禁止）与「上位业务抽象」（允许且须可靠）
4. 偏强归一不等于强制极少数大类；禁止为减行生成过宽标签
5. 每个输入原始维度必须返回一个标准维度
6. 不生成总结、核心描述或产品建议

必须严格按下方 Output Schema 返回合法 JSON。
顶层键必须是 mappings。
每个映射对象必须使用中文字段：类型、原始维度、标准维度。

Output Schema：
{"type":"object","properties":{"mappings":{"type":"array","items":{"type":"object","properties":{"类型":{"type":"string","enum":["消费人群","产品用途","使用场景","购买动机","用户满意","用户不满"]},"原始维度":{"type":"string"},"标准维度":{"type":"string"}},"required":["类型","原始维度","标准维度"],"additionalProperties":false}}},"required":["mappings"],"additionalProperties":false}

除 JSON 外不要输出其他内容。
