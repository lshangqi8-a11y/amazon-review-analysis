# -*- coding: utf-8 -*-
"""Portable constants for Amazon review analysis V6 (V4 core + segment insight)."""
from __future__ import annotations

# Pass1 — consumer persona (6)
PERSONA_TYPES = [
    "消费人群",
    "使用地点",
    "使用时刻",
    "产品用途",
    "使用场景",
    "购买动机",
]

# Pass2 — need fulfillment (2); display name = type name
FULFILLMENT_TYPES = [
    "用户满意",
    "未被满足",
]

VOC_TYPES = PERSONA_TYPES + FULFILLMENT_TYPES
ALLOWED_TYPES = set(VOC_TYPES)
PERSONA_ALLOWED = set(PERSONA_TYPES)
FULFILLMENT_ALLOWED = set(FULFILLMENT_TYPES)

# Overview: column charts (auditable list for place/time instead of crowded bars)
OVERVIEW_CHART_TYPES = [
    "消费人群",
    "产品用途",
    "使用场景",
    "购买动机",
]
OVERVIEW_CONTEXT_PANEL_TYPES = [
    "使用地点",
    "使用时刻",
]
OVERVIEW_PANEL_TYPES = list(FULFILLMENT_TYPES)

EXTRACT_CHUNK_LIMIT = 50
REPRESENTATIVE_FEEDBACK_LIMIT = 5
OVERVIEW_SHEET_NAME = "评论分析总览"
RESULT_SHEET_NAME = "评论分析结果"
SEGMENT_INSIGHT_SHEET_NAME = "消费人群洞察"

# Excel percentage display (true percent values, e.g. 0.194 → 19.4%)
EXCEL_PERCENT_FORMAT = "0.0%"

# Overview charts/panels: cap bars for reviewability after AI normalize
OVERVIEW_TOP_N = {
    "消费人群": 10,
    "产品用途": 10,
    "使用场景": 10,
    "购买动机": 8,
    "使用地点": 8,
    "使用时刻": 8,
    "用户满意": 12,
    "未被满足": 12,
}
OVERVIEW_MIN_MENTIONS = 1

# Optional heuristic fallback only (AI normalize is primary)
LABEL_MIN_MENTIONS = 3
LABEL_MIN_RATE = 0.6
LABEL_KEEP_TOP = 8
LABEL_OTHER = "其他（低频）"

# Identity map kept for API compatibility (types are already display names)
TYPE_DISPLAY_LABELS: dict[str, str] = {}

# Short blurbs only — no chart-formula jargon on the dashboard
MODULE_DESCRIPTIONS = {
    "消费人群": "谁在使用 / 为谁购买",
    "使用地点": "在哪里使用（空间场所）",
    "使用时刻": "什么时候使用（时间节律）",
    "产品用途": "产品被拿来做什么",
    "使用场景": "在什么事务 / 场合中使用",
    "购买动机": "买前为何选择（无证据可为空）",
    "用户满意": "用后正面体验，识别可保留优势",
    "未被满足": "用后负面缺口，识别改进方向",
}

NEED_FULFILLMENT_SECTION_DESC = "正面与负面体验及提及占比，支撑优势确认与改进落地。"
CONTEXT_SECTION_DESC = "地点与时刻分列展示，便于对照原文审计（完整条目见「评论分析结果」）。"

# Consumer segment insight (V6)
SEGMENT_TYPE = "消费人群"
SEGMENT_TOP_N = 5
SEGMENT_RELATED_TYPES = [
    "产品用途",
    "使用场景",
    "购买动机",
    "用户满意",
    "未被满足",
]
SEGMENT_COMBO_TOP_N = 5
SEGMENT_RELATED_TOP_N = 5

ANALYSIS_SHEET_NAMES = (
    OVERVIEW_SHEET_NAME,
    RESULT_SHEET_NAME,
    SEGMENT_INSIGHT_SHEET_NAME,
    "AI总结",  # legacy V6 sheet — remove if present
    "VOC分析结果",
    "VOC评论明细",
)

PRODUCT_NAME_HEADER_CANDIDATES = [
    "产品名称",
    "商品名称",
    "品名",
    "product name",
    "product",
    "item name",
]

PRODUCT_CATEGORY_HEADER_CANDIDATES = [
    "产品类目",
    "商品类目",
    "类目",
    "品类",
    "category",
    "product category",
    "product type",
]
