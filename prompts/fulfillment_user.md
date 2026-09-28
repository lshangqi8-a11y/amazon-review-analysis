产品名称：
{{product_name}}

产品类目：
{{product_category}}

以下为本批次 Amazon 用户评论（标题+内容已合并为 review_text）。
本轮只做「需求满足」：用户满意 / 未被满足，并标注信号类型。
禁止输出消费人群、使用地点、使用时刻、产品用途、使用场景、购买动机。

评论数据：

{{reviews}}

要求：
1. 逐条分析；无满足/未被满足信息则 items 为空数组
2. 标签落在具体方面，禁止空泛质量问题；同义必须同一写法，禁止微标签爆炸
3. 不适配/易脏/故障归「未被满足」，不要写成人群或地点/场景
4. 每个 item 必须填写信号类型：
   - 用户满意 → 满意点
   - 未被满足 → 明确问题 / 限制条件 / 明确需求 / 期望落差 / 补偿行为
5. 便于审计与产品改进落地

必须严格按下方 Output Schema 返回合法 JSON。
顶层键必须是 results。
每个 item 必须使用中文字段：类型、单条提炼、原始维度、信号类型。

Output Schema:
{"type":"object","properties":{"results":{"type":"array","items":{"type":"object","properties":{"review_id":{"type":"string"},"items":{"type":"array","items":{"type":"object","properties":{"类型":{"type":"string","enum":["用户满意","未被满足"]},"单条提炼":{"type":"string"},"原始维度":{"type":"string"},"信号类型":{"type":"string","enum":["满意点","明确问题","限制条件","明确需求","期望落差","补偿行为"]}},"required":["类型","单条提炼","原始维度","信号类型"],"additionalProperties":false}}},"required":["review_id","items"],"additionalProperties":false}}},"required":["results"],"additionalProperties":false}

除 JSON 外不要输出任何内容。
