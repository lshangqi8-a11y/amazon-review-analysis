# -*- coding: utf-8 -*-
"""Local assertions for V4 Excel Dashboard (4 charts + context/fulfillment panels)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import OVERVIEW_CHART_TYPES, OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME
from lib.excel_io import (
    PORTRAIT_TYPES,
    type_display_label,
    write_analysis_workbook,
)
from lib.statistics import build_theme_insight_summary


def _row(
    item_type: str,
    dimension: str,
    count: int,
    rate: float,
    feedback: str,
) -> dict:
    item = {
        "item_type": item_type,
        "dimension": dimension,
        "mention_count": count,
        "mention_rate": rate,
        "representative_feedback": feedback,
    }
    item["theme_summary"] = build_theme_insight_summary(item)
    return item


def _full_summary(*, skip_types: set[str] | None = None) -> list[dict]:
    skip_types = skip_types or set()
    rows: list[dict] = []
    specs = [
        ("消费人群", ["家庭用户", "新手买家", "老年用户", "学生党"], 4),
        ("使用地点", ["厨房", "台面", "庭院", "车内", "室内"], 5),
        ("使用时刻", ["每天", "夜间", "早晨", "碎片时间"], 4),
        ("产品用途", ["日常切割", "厨房备菜", "清洗奶瓶", "娱乐互动"], 4),
        ("使用场景", ["日常清洁养护", "礼赠场合", "出行旅行", "夜间照护"], 4),
        ("购买动机", ["性价比", "品牌信任", "礼品", "朋友推荐"], 4),
        ("用户满意", [f"满意点{i}" for i in range(1, 6)], 5),
        ("未被满足", [f"痛点维度{i}" for i in range(1, 6)], 5),
    ]
    for item_type, dims, _n in specs:
        if item_type in skip_types:
            continue
        for i, dim in enumerate(dims):
            count = max(1, 6 - i) if i < 4 else 1
            long_fb = f"这是第1条代表性反馈，说明维度「{dim}」；这是第2条"
            rows.append(_row(item_type, dim, count, float(count), long_fb))
    return rows


def _write_source(path: Path) -> None:
    wb = Workbook()
    wb.active.title = "Reviews"
    wb.create_sheet("Summary")
    wb.create_sheet("Raw Data")
    ws = wb["Reviews"]
    ws.append(["标题", "内容"])
    ws.append(["good", "works well"])
    wb.save(path)
    wb.close()


def test_dashboard_full() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / "in.xlsx"
        out = td_path / "out.xlsx"
        _write_source(src)

        meta = write_analysis_workbook(
            src,
            out,
            summary_rows=_full_summary(),
            product_name="",
            product_category="",
            total_reviews=100,
            voc_items=40,
        )
        expected = ["Reviews", "Summary", "Raw Data", OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME]
        assert meta["sheetnames"] == expected, meta["sheetnames"]
        assert meta["chart_count"] == 4, meta["chart_count"]
        assert meta.get("feedback_start")
        assert meta.get("context_start")
        assert meta.get("summary_reserve") == "K1:S1"

        wb = load_workbook(out)
        ov = wb[OVERVIEW_SHEET_NAME]

        assert ov["A1"].value == "Amazon 评论分析总览"
        assert "评论总数：100" in str(ov.cell(row=1, column=5).value)
        # Title should not span into E (merged A1:D1)
        assert "A1:D1" in ov.merged_cells

        visible_vals = []
        for r in range(1, 220):
            for c in range(1, 20):
                v = ov.cell(row=r, column=c).value
                if v is not None:
                    visible_vals.append(str(v))
        joined = "\n".join(visible_vals)
        assert "使用地点" in joined
        assert "使用时刻" in joined
        assert "厨房" in joined  # location panel lists all dims
        assert "室内" in joined
        assert "未被满足" in joined
        assert "用户满意" in joined
        assert "需求满足分析" in joined
        assert "使用地点 / 使用时刻" in joined
        assert "用户不满" not in joined
        assert "评论洞察条目数" not in joined
        assert "标准维度数" not in joined
        assert "共 " not in joined or "共 " not in [v for v in visible_vals if "柱顶" in v]
        assert not any("柱顶=频率" in v for v in visible_vals)
        assert not any("（" in str(ch.title) and str(ch.title).endswith("）") for ch in ov._charts)
        assert any("出现在" in v and "买家反馈" in v for v in visible_vals)

        assert len(ov._charts) == 4
        for ch in ov._charts:
            assert ch.type == "col"
            assert "（" not in str(ch.title or "")

        import zipfile

        with zipfile.ZipFile(out, "r") as zf:
            chart_xml = zf.read("xl/charts/chart1.xml").decode("utf-8", errors="ignore")
        assert "datalabelsRange" in chart_xml or "showDataLabelsRange" in chart_xml

        result = wb[RESULT_SHEET_NAME]
        types = {result.cell(row=r, column=1).value for r in range(2, result.max_row + 1)}
        assert "未被满足" in types
        assert "使用地点" in types
        wb.close()


def test_empty_chart_modules() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / "in.xlsx"
        out = td_path / "out.xlsx"
        _write_source(src)
        meta = write_analysis_workbook(
            src,
            out,
            summary_rows=_full_summary(skip_types={"产品用途", "购买动机"}),
            total_reviews=100,
            voc_items=20,
        )
        empty = [m for m in meta["module_metas"] if not m.get("has_chart")]
        assert {m["type"] for m in empty} == {"产品用途", "购买动机"}
        assert meta["chart_count"] == 2


def test_display_labels() -> None:
    assert type_display_label("未被满足") == "未被满足"
    assert PORTRAIT_TYPES == list(OVERVIEW_CHART_TYPES)
    assert OVERVIEW_CHART_TYPES == [
        "消费人群",
        "产品用途",
        "使用场景",
        "购买动机",
    ]


if __name__ == "__main__":
    test_display_labels()
    test_dashboard_full()
    test_empty_chart_modules()
    print("ALL_EXCEL_TESTS_PASSED")
