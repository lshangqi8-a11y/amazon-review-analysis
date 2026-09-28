# -*- coding: utf-8 -*-
"""Tests for AI normalize codec (primary merge path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.normalize_codec import (
    apply_mappings,
    build_normalize_input_rows,
    parse_and_validate_normalize,
    validate_normalize_mappings,
)
from lib.statistics import aggregate_statistics


def test_build_rows_dedup_and_count() -> None:
    items = [
        {"item_type": "用户满意", "dimension": "易清洗", "extracted_summary": "很好洗", "review_row": 2},
        {"item_type": "用户满意", "dimension": "易清洗", "extracted_summary": "洗碗机也行", "review_row": 5},
        {"item_type": "用户满意", "dimension": "耐用", "extracted_summary": "用很久", "review_row": 1},
    ]
    rows = build_normalize_input_rows(items)
    assert len(rows) == 2
    easy = next(r for r in rows if r["原始维度"] == "易清洗")
    assert easy["提及次数"] == 2
    assert isinstance(easy["语义参考"], list)
    assert len(easy["语义参考"]) == 2


def test_validate_and_apply() -> None:
    expected = {("用户满意", "容易清洁"), ("用户满意", "易清洗"), ("用户满意", "耐用")}
    raw = json.dumps(
        {
            "mappings": [
                {"类型": "用户满意", "原始维度": "容易清洁", "标准维度": "易清洗"},
                {"类型": "用户满意", "原始维度": "易清洗", "标准维度": "易清洗"},
                {"类型": "用户满意", "原始维度": "耐用", "标准维度": "耐用"},
            ]
        },
        ensure_ascii=False,
    )
    mappings = parse_and_validate_normalize(raw, expected)
    assert validate_normalize_mappings(mappings, expected) == ""
    items = [
        {"item_type": "用户满意", "dimension": "容易清洁", "extracted_summary": "a", "review_row": 1},
        {"item_type": "用户满意", "dimension": "易清洗", "extracted_summary": "b", "review_row": 2},
        {"item_type": "用户满意", "dimension": "耐用", "extracted_summary": "c", "review_row": 3},
    ]
    out = apply_mappings(items, mappings)
    assert {it["merged_dimension"] for it in out} == {"易清洗", "耐用"}
    rows = aggregate_statistics(out, analyzed_reviews=10, consolidate=False)
    sat = [r for r in rows if r["item_type"] == "用户满意"]
    assert len(sat) == 2
    top = next(r for r in sat if r["dimension"] == "易清洗")
    assert top["mention_count"] == 2


def test_reject_vague_std() -> None:
    expected = {("未被满足", "坏了")}
    err = validate_normalize_mappings(
        [{"类型": "未被满足", "原始维度": "坏了", "标准维度": "质量问题"}],
        expected,
    )
    assert err and "空泛" in err


if __name__ == "__main__":
    test_build_rows_dedup_and_count()
    test_validate_and_apply()
    test_reject_vague_std()
    print("NORMALIZE_CODEC_OK")
