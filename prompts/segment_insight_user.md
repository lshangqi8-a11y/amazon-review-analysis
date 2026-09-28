产品信息：不提供产品名称/类目；仅依据下方消费人群统计与共现证据做洞察。

{{stats_block}}

联网能力提示：{{network_capability}}

要求：
1. segments 只能使用上方「核心购买人群」中的人群名称
2. 禁止改写评论数 / 覆盖率；禁止新增未知人群
3. review_observations 必须基于同评共现的用途/场景/动机/满意/未满足
4. 行为/性格/习惯/需求可结合联网公开知识，但必须写 sources
5. 按联网能力设置 external_research_status = ok / skipped / unavailable
6. product_development 只含 must_have_features 与 product_moats

必须严格按下方 Output Schema 返回合法 JSON。

Output Schema:
{"type":"object","properties":{"external_research_status":{"type":"string","enum":["ok","skipped","unavailable"]},"segments":{"type":"array","items":{"type":"object","properties":{"segment":{"type":"string"},"review_observations":{"type":"array","items":{"type":"string"}},"behavior_traits":{"type":"array","items":{"type":"string"}},"personality_traits":{"type":"array","items":{"type":"string"}},"usage_habits":{"type":"array","items":{"type":"string"}},"core_needs":{"type":"array","items":{"type":"string"}},"sources":{"type":"array","items":{"type":"object","properties":{"source_title":{"type":"string"},"source_url":{"type":"string"},"finding":{"type":"string"}},"required":["source_title","source_url","finding"]}}},"required":["segment","review_observations","behavior_traits","personality_traits","usage_habits","core_needs","sources"]}},"product_development":{"type":"object","properties":{"must_have_features":{"type":"array","items":{"type":"string"}},"product_moats":{"type":"array","items":{"type":"string"}}},"required":["must_have_features","product_moats"]}},"required":["external_research_status","segments","product_development"],"additionalProperties":false}

除 JSON 外不要输出任何内容。
