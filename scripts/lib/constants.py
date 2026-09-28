# -*- coding: utf-8 -*-
"""Portable constants for Amazon review analysis V5 (Review Intelligence)."""
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

# Fulfillment signal types (V5)
SATISFACTION_SIGNAL_TYPES = ["满意点"]
UNMET_SIGNAL_TYPES = [
    "明确问题",
    "限制条件",
    "明确需求",
    "期望落差",
    "补偿行为",
]
OPPORTUNITY_SIGNAL_TYPES = [
    "明确需求",
    "期望落差",
    "补偿行为",
    "限制条件",
]
SIGNAL_TYPES_BY_ITEM_TYPE = {
    "用户满意": set(SATISFACTION_SIGNAL_TYPES),
    "未被满足": set(UNMET_SIGNAL_TYPES),
}
ALL_SIGNAL_TYPES = set(SATISFACTION_SIGNAL_TYPES) | set(UNMET_SIGNAL_TYPES)

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
NORMALIZE_SEMANTIC_REF_LIMIT = 3

OVERVIEW_SHEET_NAME = "评论分析总览"
DECISION_SHEET_NAME = "产品决策分析"
SEGMENT_SHEET_NAME = "消费人群深度分析"
AI_SUMMARY_SHEET_NAME = "AI总结"
RESULT_SHEET_NAME = "评论分析结果"

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

# Analysis sheets appended at end (order matters)
ANALYSIS_SHEET_NAMES = (
    OVERVIEW_SHEET_NAME,
    DECISION_SHEET_NAME,
    SEGMENT_SHEET_NAME,
    AI_SUMMARY_SHEET_NAME,
    RESULT_SHEET_NAME,
    "VOC分析结果",
    "VOC评论明细",
)

# Review Intelligence schema / prompt version (included in input hash)
INTELLIGENCE_SCHEMA_VERSION = "v5.1.0"
EXTERNAL_RESEARCH_STATUSES = ("ok", "unavailable", "skipped")
INTELLIGENCE_DIR_NAME = "review_intelligence"
SKILL_VERSION = "v5"
SKILL_VERSION_NUMBER = "5.0.0"

SEVERITY_LEVELS = ("高", "中", "低")
PRIORITY_LEVELS = ("高", "中", "低")
ATTRIBUTE_ASSESSMENTS = ("整体优势", "优劣势并存", "整体短板", "证据不足")

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
