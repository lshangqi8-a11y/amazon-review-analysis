产品名称：{{product_name}}
产品类目：{{product_category}}

说明：产品名称/类目仅供本模块判定角色、产品要求与壁垒时明确产品对象；为空时显示「未提供」，不得中断。评论覆盖率仍以 Python 统计为准。

{{stats_block}}

联网能力提示：{{network_capability}}

要求：
1. segments 只能使用上方「核心购买人群」中的人群名称；若无核心人群则 segments 必须为空
2. 每人必须给出 role（最终使用者/购买决策者/照护者等，按产品与评论自适应）
3. 禁止改写评论数 / 覆盖率；禁止新增未知人群
4. review_findings 必须基于同评共现的用途/场景/动机/满意/未满足
5. ai_profile 综合描述行为/偏好/习惯/特征（联网或明确标记不可用）
6. status=ok 时每条 source 必须同时有非空 source_title / source_url / finding
7. status=skipped 或 unavailable 时 sources 必须为空
8. product_development.requirements 为结构化数组；product_moats 为 {moat, reason}，仅 2～4 条真正壁垒

必须严格按下方 Output Schema 返回合法 JSON。

Output Schema:
{"type":"object","properties":{"external_research_status":{"type":"string","enum":["ok","skipped","unavailable"]},"segments":{"type":"array","items":{"type":"object","properties":{"segment":{"type":"string"},"role":{"type":"string"},"review_findings":{"type":"array","items":{"type":"string"}},"ai_profile":{"type":"array","items":{"type":"string"}},"core_needs":{"type":"array","items":{"type":"string"}},"sources":{"type":"array","items":{"type":"object","properties":{"source_title":{"type":"string"},"source_url":{"type":"string"},"finding":{"type":"string"}},"required":["source_title","source_url","finding"]}}},"required":["segment","role","review_findings","ai_profile","core_needs","sources"]}},"product_development":{"type":"object","properties":{"requirements":{"type":"array","items":{"type":"object","properties":{"requirement":{"type":"string"},"target_segments":{"type":"array","items":{"type":"string"}},"basis":{"type":"string"}},"required":["requirement","target_segments","basis"]}},"product_moats":{"type":"array","items":{"type":"object","properties":{"moat":{"type":"string"},"reason":{"type":"string"}},"required":["moat","reason"]}}},"required":["requirements","product_moats"]}},"required":["external_research_status","segments","product_development"],"additionalProperties":false}

除 JSON 外不要输出任何内容。
