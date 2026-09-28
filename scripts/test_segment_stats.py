# -*- coding: utf-8 -*-
"""Tests for consumer segment deep analysis."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openpyxl import Workbook, load_workbook

from lib.constants import (
    AI_SUMMARY_SHEET_NAME,
    DECISION_SHEET_NAME,
    OVERVIEW_SHEET_NAME,
    RESULT_SHEET_NAME,
    SEGMENT_SHEET_NAME,
    VOC_TYPES,
)
from lib.excel_io import write_analysis_workbook
from lib.intelligence_codec import parse_intelligence_output, validate_intelligence_payload
from lib.segment_stats import (
    MIN_DIRECTIONAL_N,
    build_segment_analysis,
    compare_metric,
    discover_segments,
    fisher_exact_2x2,
)


def _items_two_segments() -> list[dict]:
    """
    Segment A 大型犬主人: reviews 1-12
    Segment B 小型犬主人: reviews 13-20
    Shared / distinct associations.
    """
    items = []
    for rid in range(1, 13):
        items.append(
            {
                "item_type": "消费人群",
                "dimension": "大型犬主人",
                "merged_dimension": "大型犬主人",
                "extracted_summary": f"large-{rid}",
                "review_row": rid,
            }
        )
        items.append(
            {
                "item_type": "产品用途",
                "dimension": "高强度撕咬",
                "merged_dimension": "高强度撕咬",
                "extracted_summary": f"chew-{rid}",
                "review_row": rid,
            }
        )
    for rid in range(13, 21):
        items.append(
            {
                "item_type": "消费人群",
                "dimension": "小型犬主人",
                "merged_dimension": "小型犬主人",
                "extracted_summary": f"small-{rid}",
                "review_row": rid,
            }
        )
        items.append(
            {
                "item_type": "产品用途",
                "dimension": "日常陪伴",
                "merged_dimension": "日常陪伴",
                "extracted_summary": f"compan-{rid}",
                "review_row": rid,
            }
        )
    # A few large-dog reviews also mention durability pain
    for rid in (1, 2, 3, 4, 5, 6):
        items.append(
            {
                "item_type": "未被满足",
                "dimension": "不耐咬",
                "merged_dimension": "不耐咬",
                "extracted_summary": f"pain-{rid}",
                "review_row": rid,
                "signal_type": "明确问题",
            }
        )
    # Same review hits multiple dims — should not double-count segment
    items.append(
        {
            "item_type": "消费人群",
            "dimension": "大型犬主人",
            "merged_dimension": "大型犬主人",
            "extracted_summary": "dup",
            "review_row": 1,
        }
    )
    return items


def test_unique_review_and_share() -> None:
    items = _items_two_segments()
    analyzed = 30
    segs = discover_segments(items, analyzed)
    by = {s["segment"]: s for s in segs}
    assert by["大型犬主人"]["mention_count"] == 12
    assert by["小型犬主人"]["mention_count"] == 8
    assert by["大型犬主人"]["mention_rate"] == 40.0  # 12/30
    assert by["小型犬主人"]["mention_rate"] == round(8 * 100 / 30, 2)


def test_dedup_same_review() -> None:
    items = _items_two_segments()
    segs = discover_segments(items, 30)
    large = next(s for s in segs if s["segment"] == "大型犬主人")
    assert large["mention_count"] == 12  # not 13


def test_pp_and_fisher_inputs() -> None:
    items = _items_two_segments()
    analysis = build_segment_analysis(items, 30)
    comps = analysis["comparisons"]
    assert comps
    # Find chew metric comparison
    chew = [
        c
        for c in comps
        if c["dimension"] == "高强度撕咬" and {c["segment_a"], c["segment_b"]} == {"大型犬主人", "小型犬主人"}
    ]
    assert chew
    c = chew[0]
    if c["segment_a"] == "大型犬主人":
        assert c["rate_a"] == 100.0
        assert c["rate_b"] == 0.0
        assert c["pp_diff"] == 100.0
        assert c["hit_a"] == 12 and c["hit_b"] == 0
        assert c["n_a"] == 12 and c["n_b"] == 8
    else:
        assert c["rate_b"] == 100.0
        assert abs(c["pp_diff"]) == 100.0
    # Fisher table should match hits
    table = c["test"]["fisher"]["table"]
    assert table[0][0] + table[0][1] in (12, 8)
    assert c["test"]["fisher"]["applicable"] is True
    assert c["p_value"] is not None


def test_fisher_known_table() -> None:
    # Classic 2x2
    r = fisher_exact_2x2(1, 9, 11, 3)
    assert r["applicable"] is True
    assert 0.0 <= r["p_value"] <= 1.0
    assert r["odds_ratio"] is not None


def test_small_n_no_strong_conclusion() -> None:
    items = []
    for rid in range(1, 6):
        items.append(
            {
                "item_type": "消费人群",
                "dimension": "新手",
                "merged_dimension": "新手",
                "extracted_summary": "n",
                "review_row": rid,
            }
        )
        items.append(
            {
                "item_type": "用户满意",
                "dimension": "易用",
                "merged_dimension": "易用",
                "extracted_summary": "e",
                "review_row": rid,
            }
        )
    for rid in range(6, 10):
        items.append(
            {
                "item_type": "消费人群",
                "dimension": "资深用户",
                "merged_dimension": "资深用户",
                "extracted_summary": "p",
                "review_row": rid,
            }
        )
    analysis = build_segment_analysis(items, 20)
    for s in analysis["segments"]:
        assert s["sample_status"] == "样本不足"
        assert s["mention_count"] < MIN_DIRECTIONAL_N
    for c in analysis["comparisons"]:
        assert c["allow_strong_conclusion"] is False
        assert "样本不足" in (c.get("note") or c.get("sample_status") or "")


def test_external_research_unavailable_ok() -> None:
    summary = [
        {"item_type": t, "dimension": f"{t}维", "mention_count": 2, "mention_rate": 10.0}
        for t in VOC_TYPES
    ]
    summary[0]["dimension"] = "新手"
    payload = {
        "sections": [{"title": t, "bullets": ["ok"]} for t in VOC_TYPES],
        "attribute_performance": [],
        "pain_priorities": [],
        "opportunities": [],
        "recommendations": {
            "priority_improvements": [],
            "keep_strengths": [],
            "explore_opportunities": [],
        },
        "segment_intelligence": {
            "segments": [
                {
                    "segment": "新手",
                    "summary": "样本有限",
                    "important_attributes": [],
                    "development_implications": ["先观察"],
                }
            ],
            "comparisons": [],
            "external_research_status": "unavailable",
            "external_research": [],
            "segment_product_opportunities": [
                {
                    "segment": "新手",
                    "opportunity": "简化上手",
                    "review_evidence": ["新手维"],
                    "recommendation": "验证引导流程",
                }
            ],
        },
    }
    # Fix review_evidence to known dim
    payload["segment_intelligence"]["segment_product_opportunities"][0]["review_evidence"] = ["新手"]
    # 消费人群 dim is 新手 — put in known_dims via summary
    items = [
        {
            "item_type": "消费人群",
            "merged_dimension": "新手",
            "dimension": "新手",
            "review_row": 1,
            "extracted_summary": "x",
        }
    ]
    seg = build_segment_analysis(items, 10)
    enriched, text, err = parse_intelligence_output(
        json.dumps(payload, ensure_ascii=False),
        summary_rows=summary,
        items=items,
        analyzed_reviews=10,
        segment_analysis=seg,
    )
    assert err is None, err
    assert enriched["segment_intelligence"]["external_research_status"] == "unavailable"
    assert "消费人群深度分析" in text


def test_reject_unknown_segment() -> None:
    summary = [
        {"item_type": t, "dimension": "维", "mention_count": 1, "mention_rate": 5.0}
        for t in VOC_TYPES
    ]
    payload = {
        "sections": [{"title": t, "bullets": ["ok"]} for t in VOC_TYPES],
        "attribute_performance": [],
        "pain_priorities": [],
        "opportunities": [],
        "recommendations": {
            "priority_improvements": [],
            "keep_strengths": [],
            "explore_opportunities": [],
        },
        "segment_intelligence": {
            "segments": [
                {
                    "segment": "火星用户",
                    "summary": "x",
                    "important_attributes": [],
                    "development_implications": ["y"],
                }
            ],
            "comparisons": [],
            "external_research_status": "skipped",
            "external_research": [],
            "segment_product_opportunities": [],
        },
    }
    err = validate_intelligence_payload(
        payload,
        known_dims={t: {"维"} for t in VOC_TYPES},
        known_segments={"新手"},
    )
    assert err and "未知人群" in err


def test_excel_segment_sheet_and_ai_summary() -> None:
    items = _items_two_segments()
    analysis = build_segment_analysis(items, 30)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.xlsx"
        out = Path(td) / "out.xlsx"
        wb = Workbook()
        wb.active.title = "Reviews"
        wb["Reviews"].append(["标题", "内容"])
        wb.save(src)
        wb.close()
        text = (
            "AI评论洞察总结\n\n【消费人群】\n· x\n\n"
            "【消费人群深度分析】\n· 主要人群：\n  - 大型犬主人\n· 人群差异：\n  - a vs b\n"
            "· 外部研究解释：\n  - unavailable\n· 人群细分产品开发方向：\n  - 验证耐咬"
        )
        intel = {
            "attribute_performance": [],
            "pain_priorities": [],
            "opportunities": [],
            "recommendations": {},
            "segment_intelligence": {
                "segments": [
                    {
                        "segment": "大型犬主人",
                        "summary": "主群",
                        "important_attributes": ["耐咬性"],
                        "development_implications": ["加强结构"],
                        "mention_count": 12,
                        "mention_rate": 40.0,
                    }
                ],
                "comparisons": [
                    {
                        "segment_a": "大型犬主人",
                        "segment_b": "小型犬主人",
                        "finding": "用途差异明显",
                    }
                ],
                "external_research_status": "unavailable",
                "external_research": [],
                "segment_product_opportunities": [],
            },
        }
        meta = write_analysis_workbook(
            src,
            out,
            summary_rows=[
                {
                    "item_type": "消费人群",
                    "dimension": "大型犬主人",
                    "mention_count": 12,
                    "mention_rate": 40.0,
                    "representative_feedback": "x",
                    "theme_summary": "「大型犬主人」提及率 40.0%。",
                }
            ],
            total_reviews=30,
            analyzed_reviews=30,
            overview_summary=text,
            intelligence=intel,
            segment_analysis=analysis,
        )
        assert SEGMENT_SHEET_NAME in meta["sheetnames"]
        assert meta["sheetnames"][-5:] == [
            OVERVIEW_SHEET_NAME,
            DECISION_SHEET_NAME,
            SEGMENT_SHEET_NAME,
            AI_SUMMARY_SHEET_NAME,
            RESULT_SHEET_NAME,
        ]
        wb2 = load_workbook(out)
        assert SEGMENT_SHEET_NAME in wb2.sheetnames
        ai = wb2[AI_SUMMARY_SHEET_NAME]
        assert "消费人群深度分析" in str(ai["A2"].value)
        assert not list(ai.merged_cells.ranges)
        ws = wb2[SEGMENT_SHEET_NAME]
        assert ws["A1"].value == "消费人群深度分析"
        wb2.close()


def run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok: {t.__name__}")
    print(f"SEGMENT_TESTS_PASSED ({len(tests)})")


if __name__ == "__main__":
    run_all()
