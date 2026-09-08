产品名称：
{{product_name}}

产品类目：
{{product_category}}

以下为本批次 Amazon 用户评论（标题+内容已合并为 review_text）。
本轮只做「消费者画像」六维：消费人群 / 使用地点 / 使用时刻 / 产品用途 / 使用场景 / 购买动机。
禁止输出用户满意、未被满足。

评论数据：

{{reviews}}

要求：
1. 逐条分析；无画像信息则 items 为空数组
2. 地点/时刻/场景/用途严格互斥；一句话可拆多条
3. 人群不要混入适合/不适合；场景不要混入故障/体验词
4. 购买动机必须有买前因果，否则不写
5. 标签短、可读、便于产品形态讨论

必须严格按下方 Output Schema 返回合法 JSON。
顶层键必须是 results。
每个 item 必须使用中文字段：类型、单条提炼、原始维度。

Output Schema:
{"type":"object","properties":{"results":{"type":"array","items":{"type":"object","properties":{"review_id":{"type":"string"},"items":{"type":"array","items":{"type":"object","properties":{"类型":{"type":"string","enum":["消费人群","使用地点","使用时刻","产品用途","使用场景","购买动机"]},"单条提炼":{"type":"string"},"原始维度":{"type":"string"}},"required":["类型","单条提炼","原始维度"],"additionalProperties":false}}},"required":["review_id","items"],"additionalProperties":false}}},"required":["results"],"additionalProperties":false}

除 JSON 外不要输出任何内容。
