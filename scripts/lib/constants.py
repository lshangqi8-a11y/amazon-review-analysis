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
ANALYSIS_SHEET_NAMES = (
    OVERVIEW_SHEET_NAME,
    RESULT_SHEET_NAME,
    "VOC分析结果",
    "VOC评论明细",
)