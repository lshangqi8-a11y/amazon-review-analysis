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
OVERVIEW_TOP_N = {
    "消费人群": 5,
    "产品用途": 5,
    "使用场景": 5,
    "购买动机": 5,
    "用户满意": 10,
    "用户不满": 10,
}
# Overview / result sheet display labels (internal type keys unchanged)
TYPE_DISPLAY_LABELS = {
    "用户不满": "未被满足",
}
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
