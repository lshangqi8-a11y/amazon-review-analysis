产品信息：不提供产品名称/类目；仅依据下方统计做 Review Intelligence。

原始总行数：{{total_reviews}}
有效分析评论数（百分比分母）：{{analyzed_reviews}}

以下为八维统计摘要（各维 Top 维度 + 提及率 + 代表反馈节选）。
提及率分母 = 有效分析评论数。禁止自行改算或编造百分比。

{{stats_block}}

{{signal_block}}

{{segment_block}}

要求：
1. sections 必须覆盖全部八维（无数据写证据不足）
2. attribute / pain / opportunity / segment 只能引用上方已出现的标准维度与人群
3. 禁止输出任何自己计算的百分比字段；Python 会按维度重算
4. 禁止依赖或编造具体产品名/类目
5. 禁止提出没有评论证据的新功能
6. segment_intelligence 必须把【评论数据事实】【外部研究】【产品开发推论】分开；无法联网则 external_research_status=unavailable 且 external_research=[]

必须严格按下方 Output Schema 返回合法 JSON。

Output Schema:
{"type":"object","properties":{"sections":{"type":"array","items":{"type":"object","properties":{"title":{"type":"string","enum":["消费人群","使用地点","使用时刻","产品用途","使用场景","购买动机","用户满意","未被满足"]},"bullets":{"type":"array","items":{"type":"string"}}},"required":["title","bullets"],"additionalProperties":false}},"attribute_performance":{"type":"array","items":{"type":"object","properties":{"attribute":{"type":"string"},"positive_dimensions":{"type":"array","items":{"type":"string"}},"negative_dimensions":{"type":"array","items":{"type":"string"}},"assessment":{"type":"string","enum":["整体优势","优劣势并存","整体短板","证据不足"]}},"required":["attribute","positive_dimensions","negative_dimensions","assessment"],"additionalProperties":false}},"pain_priorities":{"type":"array","items":{"type":"object","properties":{"dimension":{"type":"string"},"severity":{"type":"string","enum":["高","中","低"]},"priority":{"type":"string","enum":["高","中","低"]},"reason":{"type":"string"}},"required":["dimension","severity","priority","reason"],"additionalProperties":false}},"opportunities":{"type":"array","items":{"type":"object","properties":{"opportunity":{"type":"string"},"source_dimensions":{"type":"array","items":{"type":"string"}},"reason":{"type":"string"}},"required":["opportunity","source_dimensions","reason"],"additionalProperties":false}},"recommendations":{"type":"object","properties":{"priority_improvements":{"type":"array","items":{"type":"object","properties":{"action":{"type":"string"},"evidence":{"type":"string"},"source_dimensions":{"type":"array","items":{"type":"string"}}},"required":["action","evidence"],"additionalProperties":false}},"keep_strengths":{"type":"array","items":{"type":"object","properties":{"action":{"type":"string"},"evidence":{"type":"string"},"source_dimensions":{"type":"array","items":{"type":"string"}}},"required":["action","evidence"],"additionalProperties":false}},"explore_opportunities":{"type":"array","items":{"type":"object","properties":{"action":{"type":"string"},"evidence":{"type":"string"},"source_dimensions":{"type":"array","items":{"type":"string"}}},"required":["action","evidence"],"additionalProperties":false}}},"required":["priority_improvements","keep_strengths","explore_opportunities"],"additionalProperties":false},"segment_intelligence":{"type":"object","properties":{"segments":{"type":"array","items":{"type":"object","properties":{"segment":{"type":"string"},"summary":{"type":"string"},"important_attributes":{"type":"array","items":{"type":"string"}},"development_implications":{"type":"array","items":{"type":"string"}}},"required":["segment","summary","important_attributes","development_implications"],"additionalProperties":false}},"comparisons":{"type":"array","items":{"type":"object","properties":{"segment_a":{"type":"string"},"segment_b":{"type":"string"},"finding":{"type":"string"},"external_research_needed":{"type":"boolean"}},"required":["segment_a","segment_b","finding"],"additionalProperties":false}},"external_research_status":{"type":"string","enum":["ok","unavailable","skipped"]},"external_research":{"type":"array","items":{"type":"object","properties":{"topic":{"type":"string"},"finding":{"type":"string"},"source_title":{"type":"string"},"source_url":{"type":"string"},"supports":{"type":"string"}},"required":["topic","finding","source_title","source_url","supports"],"additionalProperties":false}},"segment_product_opportunities":{"type":"array","items":{"type":"object","properties":{"segment":{"type":"string"},"opportunity":{"type":"string"},"review_evidence":{"type":"array","items":{"type":"string"}},"external_evidence":{"type":"array","items":{"type":"string"}},"recommendation":{"type":"string"}},"required":["segment","opportunity","review_evidence","recommendation"],"additionalProperties":false}}},"required":["segments","comparisons","external_research_status","external_research","segment_product_opportunities"],"additionalProperties":false}},"required":["sections","attribute_performance","pain_priorities","opportunities","recommendations","segment_intelligence"],"additionalProperties":false}

除 JSON 外不要输出任何内容。
