产品名称：
{{product_name}}

产品类目：
{{product_category}}

以下为本批次 Amazon 用户评论。

每个 review_text 已由评论标题和评论内容合并，
请把它作为一条完整评论统一分析。

评论数据：

{{reviews}}

请逐条完成：

1. 识别明确、具体的 VOC 信息
2. 判断是否属于：
   - 消费人群
   - 产品用途
   - 使用场景
   - 购买动机
   - 用户满意
   - 用户不满
3. 生成“单条提炼”
4. 生成“原始维度”

没有明确产品信息的评论：

items 返回空数组。

禁止为了覆盖六类而强行打标。

必须严格按下方 Output Schema 返回合法 JSON。
顶层键必须是 results（数组）。
每个 item 必须使用中文字段名：类型、单条提炼、原始维度。
禁止使用 type / dimension / statement / items 作为顶层结构替代 results。

Output Schema：
{"type":"object","properties":{"results":{"type":"array","items":{"type":"object","properties":{"review_id":{"type":"string"},"items":{"type":"array","items":{"type":"object","properties":{"类型":{"type":"string","enum":["消费人群","产品用途","使用场景","购买动机","用户满意","用户不满"]},"单条提炼":{"type":"string"},"原始维度":{"type":"string"}},"required":["类型","单条提炼","原始维度"],"additionalProperties":false}}},"required":["review_id","items"],"additionalProperties":false}}},"required":["results"],"additionalProperties":false}

除 JSON 外不要输出任何内容。
