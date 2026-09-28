# -*- coding: utf-8 -*-
"""V6 unit tests: percentages, AI summary cells, consumer segment insight."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import (
    AI_SUMMARY_SHEET_NAME,
    EXCEL_PERCENT_FORMAT,
    OVERVIEW_SHEET_NAME,
    RESULT_SHEET_NAME,
    SEGMENT_INSIGHT_SHEET_NAME,
    VOC_TYPES,
)
from lib.excel_io import write_analysis_workbook
from lib.segment_insight_codec import (
    format_segment_insight_digest,
    parse_segment_insight_output,
    validate_segment_insight_payload,
)
from lib.segment_stats import (
    build_core_segments,
    build_segment_combinations,
    build_segment_stats_payload,
)
from lib.statistics import aggregate_statistics
from lib.summary_codec import format_summary_sections, validate_summary_payload


def _item(item_type: str, dim: str, review_row: int, summary: str = "x") -> dict:
    return {
        "item_type": item_type,
        "dimension": dim,
        "merged_dimension": dim,
        "review_row": review_row,
        "extracted_summary": summary,
    }


def _sample_items() -> list[dict]:
    # review 2: 幼犬 + 小型犬
    # review 3: 幼犬
    # review 4: 小型犬 + 多犬家庭
    # review 5: 老年用户
    # review 6: 学生党
    # review 7: 家庭用户
    return [
        _item("消费人群", "幼犬", 2, "幼犬在用"),
        _item("消费人群", "小型犬", 2, "小型犬"),
        _item("产品用途", "消耗精力", 2, "耗精力"),
        _item("消费人群", "幼犬", 3, "幼犬2"),
        _item("使用场景", "日常陪伴", 3, "陪伴"),
        _item("消费人群", "小型犬", 4, "小型"),
        _item("消费人群", "多犬家庭", 4, "两只狗"),
        _item("购买动机", "口碑/推荐", 4, "推荐"),
        _item("消费人群", "老年用户", 5, "老人"),
        _item("消费人群", "学生党", 6, "学生"),
        _item("消费人群", "家庭用户", 7, "家庭"),
        _item("用户满意", "耐用", 2, "耐用"),
        _item("未被满足", "易损坏", 4, "坏了"),
    ]


def test_v4_eight_dims_unchanged() -> None:
    assert len(VOC_TYPES) == 8
    assert VOC_TYPES[:6] == [
        "消费人群",
        "使用地点",
        "使用时刻",
        "产品用途",
        "使用场景",
        "购买动机",
    ]
    assert VOC_TYPES[6:] == ["用户满意", "未被满足"]
    rows = aggregate_statistics(_sample_items(), total_reviews=10, consolidate=False)
    types = {r["item_type"] for r in rows}
    assert "消费人群" in types and "用户满意" in types


def test_unique_review_and_coverage() -> None:
    core = build_core_segments(_sample_items(), analyzed_reviews=10, top_n=5)
    by_name = {c["segment"]: c for c in core}
    # 幼犬 appears in reviews 2 and 3 → count 2, coverage 20%
    assert by_name["幼犬"]["review_count"] == 2
    assert by_name["幼犬"]["coverage_rate"] == 20.0
    # duplicate mention same review must not double-count
    dup = _sample_items() + [_item("消费人群", "幼犬", 2, "again")]
    core2 = build_core_segments(dup, analyzed_reviews=10, top_n=5)
    assert {c["segment"]: c["review_count"] for c in core2}["幼犬"] == 2


def test_top5_and_under5() -> None:
    core = build_core_segments(_sample_items(), analyzed_reviews=10, top_n=5)
    assert len(core) == 5
    assert [c["rank"] for c in core] == [1, 2, 3, 4, 5]
    # sorted by coverage desc: 幼犬/小型犬 both 2, then others 1
    assert core[0]["review_count"] >= core[-1]["review_count"]

    few = [
        _item("消费人群", "A", 2),
        _item("消费人群", "B", 3),
        _item("消费人群", "C", 4),
    ]
    core_few = build_core_segments(few, analyzed_reviews=5, top_n=5)
    assert len(core_few) == 3


def test_no_segments_ok() -> None:
    payload = build_segment_stats_payload(
        [_item("产品用途", "消耗精力", 2)],
        analyzed_reviews=5,
        top_n=5,
    )
    assert payload["segment_count"] == 0
    assert payload["core_segments"] == []
    err = validate_segment_insight_payload(
        {
            "external_research_status": "skipped",
            "segments": [],
            "product_development": {"must_have_features": [], "product_moats": []},
        },
        allowed_segments=[],
    )
    assert err is None


def test_combination_same_review_only() -> None:
    core = build_core_segments(_sample_items(), analyzed_reviews=10, top_n=5)
    combos = build_segment_combinations(_sample_items(), core)
    # 幼犬 + 小型犬 co-occur in review 2
    assert any("幼犬 + 小型犬" == x or "小型犬 + 幼犬" == x for x in combos.get("幼犬", []))
    # fabricated combo must not appear
    flat = "｜".join("｜".join(v) for v in combos.values())
    assert "幼犬 + 学生党" not in flat


def test_ai_rejects_unknown_segment() -> None:
    err = validate_segment_insight_payload(
        {
            "external_research_status": "unavailable",
            "segments": [
                {
                    "segment": "外星用户",
                    "review_observations": ["x"],
                    "behavior_traits": ["x"],
                    "personality_traits": ["x"],
                    "usage_habits": ["x"],
                    "core_needs": ["x"],
                    "sources": [],
                }
            ],
            "product_development": {"must_have_features": ["a"], "product_moats": ["b"]},
        },
        allowed_segments=["幼犬"],
    )
    assert err and "不在核心人群" in err


def test_external_sources_and_offline_degrade() -> None:
    ok = {
        "external_research_status": "ok",
        "segments": [
            {
                "segment": "幼犬",
                "review_observations": ["评论表现"],
                "behavior_traits": ["行为"],
                "personality_traits": ["性格"],
                "usage_habits": ["习惯"],
                "core_needs": ["需求"],
                "sources": [
                    {
                        "source_title": "Example",
                        "source_url": "https://example.com",
                        "finding": "幼犬主人重视陪伴",
                    }
                ],
            }
        ],
        "product_development": {
            "must_have_features": ["安全"],
            "product_moats": ["耐久结构体系"],
        },
    }
    assert validate_segment_insight_payload(ok, allowed_segments=["幼犬"]) is None

    # status=ok requires non-empty source_url
    missing_url = json.loads(json.dumps(ok))
    missing_url["segments"][0]["sources"][0]["source_url"] = "  "
    err_url = validate_segment_insight_payload(missing_url, allowed_segments=["幼犬"])
    assert err_url and "source_url" in err_url

    missing_title = json.loads(json.dumps(ok))
    missing_title["segments"][0]["sources"][0]["source_title"] = ""
    err_title = validate_segment_insight_payload(missing_title, allowed_segments=["幼犬"])
    assert err_title and "source_title" in err_title

    offline = json.loads(json.dumps(ok))
    offline["external_research_status"] = "unavailable"
    offline["segments"][0]["sources"] = []
    assert validate_segment_insight_payload(offline, allowed_segments=["幼犬"]) is None

    forged = json.loads(json.dumps(ok))
    forged["external_research_status"] = "unavailable"
    # still has sources → reject
    err = validate_segment_insight_payload(forged, allowed_segments=["幼犬"])
    assert err and "不得填写 sources" in err

    skipped_with_src = json.loads(json.dumps(ok))
    skipped_with_src["external_research_status"] = "skipped"
    err_skip = validate_segment_insight_payload(skipped_with_src, allowed_segments=["幼犬"])
    assert err_skip and "不得填写 sources" in err_skip

    text, err2 = parse_segment_insight_output(
        json.dumps(offline, ensure_ascii=False),
        allowed_segments=["幼犬"],
    )
    assert err2 is None and text is not None
    digest = format_segment_insight_digest(text)
    assert "消费人群洞察总结" in digest


def test_empty_allowed_segments_rejects_invented() -> None:
    invented = {
        "external_research_status": "unavailable",
        "segments": [
            {
                "segment": "AI自造人群",
                "review_observations": ["x"],
                "behavior_traits": ["x"],
                "personality_traits": ["x"],
                "usage_habits": ["x"],
                "core_needs": ["x"],
                "sources": [],
            }
        ],
        "product_development": {"must_have_features": [], "product_moats": []},
    }
    err = validate_segment_insight_payload(invented, allowed_segments=[])
    assert err and "不在核心人群" in err

    empty_ok = {
        "external_research_status": "skipped",
        "segments": [],
        "product_development": {"must_have_features": [], "product_moats": []},
    }
    assert validate_segment_insight_payload(empty_ok, allowed_segments=[]) is None


def test_excel_percent_and_ai_summary_cells() -> None:
    payload = {
        "sections": [{"title": t, "bullets": [f"{t}要点"]} for t in VOC_TYPES]
    }
    assert validate_summary_payload(payload) is None
    sections = format_summary_sections(payload)
    assert len(sections) == 8

    insight = {
        "external_research_status": "unavailable",
        "segments": [
            {
                "segment": "幼犬",
                "review_observations": ["共现用途"],
                "behavior_traits": ["互动"],
                "personality_traits": ["陪伴导向"],
                "usage_habits": ["每天"],
                "core_needs": ["耐用"],
                "sources": [],
            }
        ],
        "product_development": {
            "must_have_features": ["安全"],
            "product_moats": ["长续航"],
        },
    }
    core = build_core_segments(_sample_items(), analyzed_reviews=10, top_n=5)
    combos = build_segment_combinations(_sample_items(), core)
    for row in core:
        row["combination_personas"] = combos.get(row["segment"]) or []

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / "in.xlsx"
        out = td_path / "out.xlsx"
        wb = Workbook()
        wb.active.title = "Reviews"
        wb["Reviews"].append(["标题", "内容"])
        wb["Reviews"].append(["a", "b"])
        wb.save(src)
        wb.close()

        summary_rows = aggregate_statistics(_sample_items(), total_reviews=10)
        meta = write_analysis_workbook(
            src,
            out,
            summary_rows=summary_rows,
            total_reviews=10,
            overview_summary="AI总结（全量）",
            summary_sections=sections,
            core_segments=core,
            segment_insight=insight,
            segment_insight_digest=format_segment_insight_digest(insight),
        )
        assert AI_SUMMARY_SHEET_NAME in meta["sheetnames"]
        assert SEGMENT_INSIGHT_SHEET_NAME in meta["sheetnames"]
        assert OVERVIEW_SHEET_NAME in meta["sheetnames"]
        assert RESULT_SHEET_NAME in meta["sheetnames"]
        assert "产品决策分析" not in meta["sheetnames"]

        wb2 = load_workbook(out)
        result = wb2[RESULT_SHEET_NAME]
        # mention_rate column D stores fraction with 0.0% format
        assert result.cell(row=2, column=4).number_format == EXCEL_PERCENT_FORMAT
        assert isinstance(result.cell(row=2, column=4).value, float)
        assert 0 <= float(result.cell(row=2, column=4).value) <= 1

        ai = wb2[AI_SUMMARY_SHEET_NAME]
        assert ai["A1"].value == "AI评论洞察总结"
        for r in range(2, 10):
            val = str(ai.cell(row=r, column=1).value or "")
            assert val.endswith("总结") or "总结" in val.split("\n", 1)[0]
            assert "要点" in val or "证据不足" in val
        assert "消费人群洞察总结" in str(ai["A11"].value or "")
        assert not ai.merged_cells.ranges

        seg = wb2[SEGMENT_INSIGHT_SHEET_NAME]
        assert "01 核心购买人群" in str(seg["A1"].value or "")
        # coverage rate percent format
        assert seg.cell(row=3, column=3).number_format == EXCEL_PERCENT_FORMAT

        ov = wb2[OVERVIEW_SHEET_NAME]
        assert len(ov._charts) >= 1
        # hidden chart value cells use percent format
        found_pct = False
        for col in range(24, 40):
            cell = ov.cell(row=2, column=col)
            if cell.number_format == EXCEL_PERCENT_FORMAT and isinstance(cell.value, float):
                found_pct = True
                break
        assert found_pct
        wb2.close()


def run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok: {t.__name__}")
    print(f"V6_PIPELINE_TESTS_PASSED ({len(tests)})")


if __name__ == "__main__":
    run_all()
