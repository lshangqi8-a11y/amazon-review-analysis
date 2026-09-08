# -*- coding: utf-8 -*-
"""Portable constants for Amazon review analysis skill scripts."""
from __future__ import annotations

VOC_TYPES = [
    "消费人群",
    "产品用途",
    "使用场景",
    "购买动机",
    "用户满意",
    "用户不满",
]

ALLOWED_TYPES = set(VOC_TYPES)
EXTRACT_CHUNK_LIMIT = 50
REPRESENTATIVE_FEEDBACK_LIMIT = 5
OVERVIEW_SHEET_NAME = "评论分析总览"
RESULT_SHEET_NAME = "评论分析结果"
# Overview: None = no Top-N cut.
OVERVIEW_TOP_N = None
# Overview min mention filter. 0 = show all dimensions (no threshold).
OVERVIEW_MIN_MENTIONS = 0
# Overview / result sheet display labels (internal type keys unchanged)
TYPE_DISPLAY_LABELS = {
    "用户不满": "未被满足",
}
# Overview module blurbs (consumer persona + need fulfillment)
MODULE_DESCRIPTIONS = {
    "消费人群": "分析评论中提及的主要用户类型及占比（可重叠；下表含提及数/评论总数与代表反馈）。",
    "产品用途": "分析评论中提及的产品用途和使用任务及占比（可重叠；下表含提及数/评论总数与代表反馈）。",
    "使用场景": "分析评论中提及的产品使用环境及占比（可重叠；下表含提及数/评论总数与代表反馈）。",
    "购买动机": "分析买前「因…而买」类原因及占比。评论文体较少写动机，条数偏少属正常；下表含提及数/评论总数与代表反馈。",
    "用户满意": "汇总评论中的正面体验及其提及占比（展示为 频率（提及数/评论总数）），快速识别产品优势。",
    "用户不满": "汇总评论中的负面体验及其提及占比（展示为 频率（提及数/评论总数）），快速识别核心问题与改进方向。",
}
NEED_FULFILLMENT_SECTION_DESC = (
    "汇总本品评论中的正面与负面体验及其提及占比，快速识别产品优势、核心问题和改进方向。"
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
