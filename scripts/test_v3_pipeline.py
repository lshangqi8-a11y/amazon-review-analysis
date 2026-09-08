# -*- coding: utf-8 -*-
"""Smoke tests for V3 dual-pass helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import FULFILLMENT_ALLOWED, PERSONA_ALLOWED, VOC_TYPES
from lib.extract_codec import validate_extract_payload
from lib.gatekeep import gatekeep_fulfillment_items, gatekeep_persona_items


def test_type_sets() -> None:
    assert PERSONA_ALLOWED == {"消费人群", "产品用途", "使用场景", "购买动机"}
    assert FULFILLMENT_ALLOWED == {"用户满意", "用户不满"}
    assert set(VOC_TYPES) == PERSONA_ALLOWED | FULFILLMENT_ALLOWED


def test_persona_gatekeep() -> None:
    items = [
        {
            "item_type": "消费人群",
            "dimension": "不适合大型犬",
            "extracted_summary": "不适合大型强壮犬",
        },
        {
            "item_type": "使用场景",
            "dimension": "户外易脏",
            "extracted_summary": "户外使用很快变脏",
        },
        {
            "item_type": "购买动机",
            "dimension": "性价比低",
            "extracted_summary": "用后觉得不值后悔了",
        },
        {
            "item_type": "消费人群",
            "dimension": "幼犬",
            "extracted_summary": "我家幼犬在用",
        },
    ]
    kept, dropped = gatekeep_persona_items(items)
    assert len(kept) == 1
    assert kept[0]["dimension"] == "幼犬"
    assert len(dropped) == 3


def test_fulfillment_gatekeep() -> None:
    items = [
        {"item_type": "用户满意", "dimension": "耐用", "extracted_summary": "很耐用"},
        {"item_type": "用户不满", "dimension": "质量问题", "extracted_summary": "质量不行"},
        {"item_type": "产品用途", "dimension": "消耗精力", "extracted_summary": "用来耗精力"},
    ]
    kept, dropped = gatekeep_fulfillment_items(items)
    assert len(kept) == 1
    assert kept[0]["dimension"] == "耐用"
    assert len(dropped) == 2


def test_validate_persona_rejects_fulfillment_type() -> None:
    payload = {
        "results": [
            {
                "review_id": "R1",
                "items": [
                    {"类型": "用户满意", "单条提炼": "很好", "原始维度": "耐用"},
                ],
            }
        ]
    }
    err = validate_extract_payload(payload, {"R1"}, allowed_types=PERSONA_ALLOWED)
    assert err and "非法类型" in err


if __name__ == "__main__":
    test_type_sets()
    test_persona_gatekeep()
    test_fulfillment_gatekeep()
    test_validate_persona_rejects_fulfillment_type()
    # Excel dashboard still works
    import test_excel_export as tex

    tex.test_display_labels()
    tex.test_dashboard_full()
    print("ALL_V3_TESTS_PASSED")
