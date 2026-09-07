# -*- coding: utf-8 -*-
"""Local assertions for V2 Excel export (sheet order, labels, charts)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME
from lib.excel_io import guess_product_fields, type_display_label, write_analysis_workbook


def _sample_summary() -> list[dict]:
    rows = []
    specs = [
        ("消费人群", ["家庭用户", "新手买家", "老年用户"], 5),
        ("产品用途", ["日常切割", "厨房备菜", "户外野餐"], 5),
        ("使用场景", ["家中厨房", "露营", "办公室"], 5),
        ("购买动机", ["性价比", "品牌信任", "礼品"], 5),
        ("用户满意", [f"满意点{i}" for i in range(1, 11)], 10),
        ("用户不满", [f"很长很长的痛点维度名称用于截断测试{i}" for i in range(1, 11)], 10),
    ]
    for item_type, dims, _n in specs:
        for i, dim in enumerate(dims):
            rows.append(
                {
                    "item_type": item_type,
                    "dimension": dim,
                    "mention_count": 20 - i,
                    "mention_rate": (20 - i) / 100 * 100,
                    "representative_feedback": f"反馈示例{i+1}",
                }
            )
    return rows


def test_sheet_order_and_charts() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / "in.xlsx"
        out = td_path / "out.xlsx"

        wb = Workbook()
        wb.active.title = "Reviews"
        wb.create_sheet("Summary")
        wb.create_sheet("Raw Data")
        # Old analysis sheets should be removed and regenerated at end
        wb.create_sheet("评论分析总览")
        wb.create_sheet("VOC分析结果")
        ws = wb["Reviews"]
        ws.append(["标题", "内容"])
        ws.append(["good", "works well"])
        wb.save(src)
        wb.close()

        meta = write_analysis_workbook(
            src,
            out,
            summary_rows=_sample_summary(),
            product_name="",
            product_category="",
            total_reviews=10,
            voc_items=30,
        )

        expected = ["Reviews", "Summary", "Raw Data", OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME]
        assert meta["sheetnames"] == expected, meta["sheetnames"]
        assert meta["chart_count"] == 6, meta["chart_count"]
        assert meta["chart_titles"] == [
            "消费人群 TOP 5",
            "产品用途 TOP 5",
            "使用场景 TOP 5",
            "购买动机 TOP 5",
            "用户满意 TOP 10",
            "未被满足 TOP 10",
        ], meta["chart_titles"]

        out_wb = load_workbook(out)
        assert out_wb.sheetnames == expected
        assert "VOC分析结果" not in out_wb.sheetnames

        overview = out_wb[OVERVIEW_SHEET_NAME]
        # Empty product → no "产品名称" / "产品类目" rows
        labels = [overview.cell(row=r, column=1).value for r in range(1, 12)]
        assert "产品名称" not in labels
        assert "产品类目" not in labels
        assert overview._charts and len(overview._charts) == 6
        for ch in overview._charts:
            assert ch.type == "col", ch.type

        result = out_wb[RESULT_SHEET_NAME]
        type_vals = {
            result.cell(row=r, column=1).value
            for r in range(2, result.max_row + 1)
        }
        assert "未被满足" in type_vals
        assert "用户不满" not in type_vals
        out_wb.close()

        # With product meta present
        meta2 = write_analysis_workbook(
            src,
            td_path / "out2.xlsx",
            summary_rows=_sample_summary(),
            product_name="Demo Knife",
            product_category="Kitchen",
            total_reviews=10,
            voc_items=30,
        )
        wb2 = load_workbook(td_path / "out2.xlsx")
        ov2 = wb2[OVERVIEW_SHEET_NAME]
        labels2 = [ov2.cell(row=r, column=1).value for r in range(1, 15)]
        assert "产品名称" in labels2
        assert "产品类目" in labels2
        assert meta2["sheetnames"][-2:] == [OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME]
        wb2.close()


def test_guess_product_fields_single_value() -> None:
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
        name, cat = guess_product_fields(path, "Reviews")
        assert name == "Alpha"
        assert cat == "Tools"

        wb = Workbook()
        ws = wb.active
        ws.title = "Reviews"
        ws.append(["产品名称", "内容"])
        ws.append(["Alpha", "a"])
        ws.append(["Beta", "b"])
        wb.save(path)
        wb.close()
        name, cat = guess_product_fields(path, "Reviews")
        assert name == ""
        assert cat == ""


def test_display_label() -> None:
    assert type_display_label("用户不满") == "未被满足"
    assert type_display_label("用户满意") == "用户满意"


if __name__ == "__main__":
    test_display_label()
    test_guess_product_fields_single_value()
    test_sheet_order_and_charts()
    print("ALL_TESTS_PASSED")
