# -*- coding: utf-8 -*-
"""Portable constants for Amazon review analysis V3."""
from __future__ import annotations

PERSONA_TYPES = [
    "消费人群",
    "产品用途",
    "使用场景",
    "购买动机",
]

FULFILLMENT_TYPES = [
    "用户满意",
    "用户不满",
]

VOC_TYPES = PERSONA_TYPES + FULFILLMENT_TYPES
ALLOWED_TYPES = set(VOC_TYPES)
PERSONA_ALLOWED = set(PERSONA_TYPES)
FULFILLMENT_ALLOWED = set(FULFILLMENT_TYPES)

EXTRACT_CHUNK_LIMIT = 50
REPRESENTATIVE_FEEDBACK_LIMIT = 5
OVERVIEW_SHEET_NAME = "评论分析总览"
RESULT_SHEET_NAME = "评论分析结果"
OVERVIEW_TOP_N = None
OVERVIEW_MIN_MENTIONS = 0

TYPE_DISPLAY_LABELS = {
    "用户不满": "未被满足",
}

MODULE_DESCRIPTIONS = {
    "消费人群": "消费者画像：谁在使用/为谁购买（柱顶=频率与提及数/评论总数；可重叠）。",
    "产品用途": "消费者画像：产品被拿来做什么（柱顶=频率与提及数/评论总数；可重叠）。",
    "使用场景": "消费者画像：在哪里/什么时机使用（柱顶=频率与提及数/评论总数；可重叠）。",
    "购买动机": "消费者画像：买前为何选择（无买前证据可为空；柱顶=频率与提及数/评论总数）。",
    "用户满意": "需求满足：正面体验及占比（频率=提及数/评论总数），识别可保留优势。",
    "用户不满": "需求满足：负面体验及占比（频率=提及数/评论总数），识别改进方向。",
}

NEED_FULFILLMENT_SECTION_DESC = (
    "汇总正面与负面体验及提及占比，支撑产品优势确认与改进落地（与消费者画像分开阅读）。"
)

ANALYSIS_SHEET_NAMES = (
    OVERVIEW_SHEET_NAME,
    RESULT_SHEET_NAME,
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
