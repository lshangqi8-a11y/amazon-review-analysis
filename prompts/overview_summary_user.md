产品信息：不提供产品名称/类目；仅依据下方八维统计做总结。

评论总数：{{total_reviews}}

以下为八维统计摘要（各维 Top 维度 + 提及率 + 代表反馈节选）。
请据此写一次全量 AI 总结。

{{stats_block}}

要求：
1. 八维都要有对应 section（无数据可写证据不足）
2. 禁止编造未出现的维度或比例
3. 禁止依赖或编造具体产品名/类目
4. 面向产品形态 / 改进落地

必须严格按下方 Output Schema 返回合法 JSON。

Output Schema:
{"type":"object","properties":{"sections":{"type":"array","items":{"type":"object","properties":{"title":{"type":"string","enum":["消费人群","使用地点","使用时刻","产品用途","使用场景","购买动机","用户满意","未被满足"]},"bullets":{"type":"array","items":{"type":"string"}}},"required":["title","bullets"],"additionalProperties":false}}},"required":["sections"],"additionalProperties":false}

除 JSON 外不要输出任何内容。
