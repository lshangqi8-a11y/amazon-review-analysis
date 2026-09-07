# -*- coding: utf-8 -*-
"""Local assertions for V2 Excel Dashboard export."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME
from lib.excel_io import (
    PORTRAIT_TYPES,
    guess_product_fields,
    type_display_label,
    write_analysis_workbook,
)


def _row(
    item_type: str,
    dimension: str,
    count: int,
    rate: float,
    feedback: str,
) -> dict:
    return {
        "item_type": item_type,
        "dimension": dimension,
        "mention_count": count,
        "mention_rate": rate,
        "representative_feedback": feedback,
    }


def _full_summary(*, skip_types: set[str] | None = None) -> list[dict]:
    skip_types = skip_types or set()
    rows: list[dict] = []
    specs = [
        ("消费人群", ["家庭用户", "新手买家", "老年用户", "学生党", "专业厨师"], 5),
        ("产品用途", ["日常切割", "厨房备菜", "户外野餐", "精细加工", "开箱拆封"], 5),
        ("使用场景", ["家中厨房", "露营", "办公室", "旅行途中", "餐厅后厨"], 5),
        ("购买动机", ["性价比", "品牌信任", "礼品", "促销吸引", "朋友推荐"], 5),
        (
            "用户满意",
            [f"满意点{i}" for i in range(1, 11)],
            10,
        ),
        (
            "用户不满",
            [f"很长很长的痛点维度名称用于截断与换行测试{i}" for i in range(1, 11)],
            10,
        ),
    ]
    for item_type, dims, _n in specs:
        if item_type in skip_types:
            continue
        for i, dim in enumerate(dims):
            long_fb = (
                f"这是第1条代表性反馈，说明维度「{dim}」的真实用户表述，内容偏长用于换行测试；"
                f"这是第2条；这是第3条"
            )
            rows.append(
                _row(
                    item_type,
                    dim,
                    20 - i,
                    float(20 - i),
                    long_fb,
                )
            )
    return rows


def _write_source(path: Path) -> None:
    wb = Workbook()
    wb.active.title = "Reviews"
    wb.create_sheet("Summary")
    wb.create_sheet("Raw Data")
    wb.create_sheet("评论分析总览")
    wb.create_sheet("VOC分析结果")
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
        assert meta["chart_titles"] == [
            "消费人群 TOP 5",
            "产品用途 TOP 5",
            "使用场景 TOP 5",
            "购买动机 TOP 5",
        ], meta["chart_titles"]

        wb = load_workbook(out)
        assert wb.sheetnames == expected
        ov = wb[OVERVIEW_SHEET_NAME]

        # No visible classic table headers in dashboard area A:S
        visible_vals = []
        for r in range(1, 60):
            for c in range(1, 20):
                v = ov.cell(row=r, column=c).value
                if v is not None:
                    visible_vals.append(str(v))
        assert "具体维度" not in visible_vals
        assert "提及评论数" not in visible_vals
        joined = "\n".join(visible_vals)
        assert "产品名称" not in joined
        assert "产品类目" not in joined
        assert "未被满足" in joined
        assert "用户满意" in joined
        assert "用户不满" not in joined

        assert len(ov._charts) == 4
        for ch in ov._charts:
            assert ch.type == "col"
            assert ch.dataLabels is not None
            assert ch.dataLabels.showVal is True

        # Hidden helper columns X:AE (24-31)
        from openpyxl.utils import get_column_letter

        for col in range(24, 32):
            assert ov.column_dimensions[get_column_letter(col)].hidden is True

        # DataBars present on feedback panels
        assert len(ov.conditional_formatting._cf_rules) >= 1

        # First feedback only (split on ；)
        # Find a cell containing only first feedback fragment
        found_first = False
        found_second = False
        for r in range(1, 80):
            for c in (5, 15):  # feedback cols E / O
                v = ov.cell(row=r, column=c).value
                if not v:
                    continue
                if "这是第1条代表性反馈" in str(v):
                    found_first = True
                if "这是第2条" in str(v):
                    found_second = True
        assert found_first
        assert not found_second

        # Metric text visible without hover
        metric_ok = any(
            isinstance(ov.cell(row=r, column=c).value, str)
            and "% (" in str(ov.cell(row=r, column=c).value)
            for r in range(1, 80)
            for c in (4, 14)
        )
        assert metric_ok

        result = wb[RESULT_SHEET_NAME]
        types = {result.cell(row=r, column=1).value for r in range(2, result.max_row + 1)}
        assert "未被满足" in types
        assert "用户不满" not in types
        wb.close()


def test_empty_portrait_modules() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / "in.xlsx"
        out = td_path / "out.xlsx"
        _write_source(src)
        meta = write_analysis_workbook(
            src,
            out,
            summary_rows=_full_summary(skip_types={"产品用途", "使用场景"}),
            product_name="Demo",
            product_category="Kitchen",
            total_reviews=50,
            voc_items=20,
        )
        assert meta["chart_count"] == 2, meta["chart_count"]
        assert meta["chart_titles"] == ["消费人群 TOP 5", "购买动机 TOP 5"]
        empty = [m for m in meta["module_metas"] if not m["has_chart"]]
        assert {m["type"] for m in empty} == {"产品用途", "使用场景"}

        wb = load_workbook(out)
        ov = wb[OVERVIEW_SHEET_NAME]
        assert len(ov._charts) == 2
        vals = [
            str(ov.cell(row=r, column=c).value)
            for r in range(1, 70)
            for c in range(1, 20)
            if ov.cell(row=r, column=c).value is not None
        ]
        assert vals.count("暂无足够评论证据") >= 2
        assert "产品名称" in vals
        assert "产品类目" in vals
        wb.close()


def test_display_and_guess() -> None:
    assert type_display_label("用户不满") == "未被满足"
    assert PORTRAIT_TYPES == ["消费人群", "产品用途", "使用场景", "购买动机"]
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "p.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Reviews"
        ws.append(["产品名称", "产品类目", "内容"])
        ws.append(["Alpha", "Tools", "nice"])
        ws.append(["Alpha", "Tools", "ok"])
        wb.save(path)
        wb.close()
        assert guess_product_fields(path, "Reviews") == ("Alpha", "Tools")


if __name__ == "__main__":
    test_display_and_guess()
    test_dashboard_full()
    test_empty_portrait_modules()
    print("ALL_TESTS_PASSED")
