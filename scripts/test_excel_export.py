# -*- coding: utf-8 -*-
"""Local assertions for V2 Excel Dashboard export."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import OVERVIEW_MIN_MENTIONS, OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME
from lib.excel_io import (
    PORTRAIT_TYPES,
    guess_product_fields,
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
        ("消费人群", ["家庭用户", "新手买家", "老年用户", "学生党", "专业厨师"], 5),
        ("产品用途", ["日常切割", "厨房备菜", "户外野餐", "精细加工", "开箱拆封"], 5),
        ("使用场景", ["家中厨房", "露营", "办公室", "旅行途中", "餐厅后厨"], 5),
        ("购买动机", ["性价比", "品牌信任", "礼品", "促销吸引", "朋友推荐"], 5),
        ("用户满意", [f"满意点{i}" for i in range(1, 11)], 10),
        ("用户不满", [f"很长很长的痛点维度名称用于截断与换行测试{i}" for i in range(1, 11)], 10),
    ]
    for item_type, dims, _n in specs:
        if item_type in skip_types:
            continue
        for i, dim in enumerate(dims):
            # First dims have high counts; last ones = 1 to test overview filter
            count = max(1, 6 - i) if i < 4 else 1
            long_fb = (
                f"这是第1条代表性反馈，说明维度「{dim}」的真实用户表述；"
                f"这是第2条；这是第3条"
            )
            rows.append(_row(item_type, dim, count, float(count), long_fb))
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

        wb = load_workbook(out)
        ov = wb[OVERVIEW_SHEET_NAME]

        assert ov.cell(row=3, column=1).value
        meta_line = str(ov.cell(row=3, column=1).value)
        assert "评论总数：100" in meta_line
        assert "评论洞察条目数：40" in meta_line
        assert "标准维度数：" in meta_line
        assert "主维度数" not in meta_line

        visible_vals = []
        for r in range(1, 100):
            for c in range(1, 20):
                v = ov.cell(row=r, column=c).value
                if v is not None:
                    visible_vals.append(str(v))
        joined = "\n".join(visible_vals)
        assert "消费者画像" not in joined
        assert "需求满足分析" in joined
        assert "评论洞察结论" not in joined
        assert "具体维度" not in visible_vals
        assert "VOC提炼条目数" not in joined
        assert "未被满足" in joined
        assert "用户满意" in joined
        assert "用户不满" not in joined
        assert any("项 · 提及频率" in v or "提及频率" in v for v in visible_vals)

        assert len(ov._charts) == 4
        for ch in ov._charts:
            assert ch.type == "col"
            assert ch.visible_cells_only is False

        # Theme summary style (not raw only-first snippet without count framing)
        assert any("出现在" in v and "买家反馈" in v for v in visible_vals)

        result = wb[RESULT_SHEET_NAME]
        # Full detail retained (including mention=1 rows)
        assert result.max_row > 20
        types = {result.cell(row=r, column=1).value for r in range(2, result.max_row + 1)}
        assert "未被满足" in types
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
        empty = [m for m in meta["module_metas"] if not m["has_chart"]]
        assert {m["type"] for m in empty} == {"产品用途", "使用场景"}
        wb = load_workbook(out)
        ov = wb[OVERVIEW_SHEET_NAME]
        assert "产品名称：Demo" in str(ov.cell(row=3, column=1).value or "")
        assert any(
            ov.cell(row=r, column=1).value and "消费人群" in str(ov.cell(row=r, column=1).value)
            for r in range(1, 30)
        )
        wb.close()


def test_overview_shows_single_mention_dimensions() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / "in.xlsx"
        out = td_path / "out.xlsx"
        _write_source(src)
        rows = [
            _row("消费人群", "儿童使用", 10, 33.3, "适合孩子；宝宝喜欢"),
            _row("消费人群", "偶发人群", 1, 3.3, "偶尔提到"),
            _row("用户满意", "易清洗", 5, 16.7, "好洗；金属环可拆"),
            _row("用户满意", "偶发满意", 1, 3.3, "偶尔说好"),
            _row("用户不满", "密封不良", 4, 13.3, "封不住"),
            _row("用户不满", "偶发不满", 1, 3.3, "偶发问题"),
        ]
        write_analysis_workbook(src, out, summary_rows=rows, total_reviews=30, voc_items=20)
        wb = load_workbook(out)
        ov = wb[OVERVIEW_SHEET_NAME]
        text = "\n".join(
            str(ov.cell(row=r, column=c).value)
            for r in range(1, 120)
            for c in range(1, 40)
            if ov.cell(row=r, column=c).value is not None
        )
        assert "儿童使用" in text or "儿童" in text
        assert "易清洗" in text
        assert "密封不良" in text
        assert "偶发人群" in text or "偶发" in text
        assert "偶发满意" in text
        assert "偶发不满" in text
        assert OVERVIEW_MIN_MENTIONS == 0
        assert "评论洞察结论" not in text
        res = wb[RESULT_SHEET_NAME]
        dims = {res.cell(row=r, column=2).value for r in range(2, res.max_row + 1)}
        assert "偶发人群" in dims
        wb.close()


def test_display_labels() -> None:
    assert type_display_label("用户不满") == "未被满足"
    assert PORTRAIT_TYPES == ["消费人群", "产品用途", "使用场景", "购买动机"]


def test_guess_product() -> None:
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
    test_display_labels()
    test_guess_product()
    test_dashboard_full()
    test_empty_portrait_modules()
    test_overview_shows_single_mention_dimensions()
    print("ALL_TESTS_PASSED")
