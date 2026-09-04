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
EXTRACT_CHUNK_LIMIT = 200
REPRESENTATIVE_FEEDBACK_LIMIT = 3
RESULT_SHEET_NAME = "评论分析结果"
