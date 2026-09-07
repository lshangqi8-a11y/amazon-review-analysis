# -*- coding: utf-8 -*-
"""Self-contained Excel helpers (no Flask / project Gateway)."""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .constants import (
    ANALYSIS_SHEET_NAMES,
    OVERVIEW_SHEET_NAME,
    OVERVIEW_TOP_N,
    RESULT_SHEET_NAME,
    VOC_TYPES,
)
TITLE_HEADER_CANDIDATES = [
    "标题",
    "评论标题",
    "title",
    "review title",
    "headline",
    "subject",
]

CONTENT_HEADER_CANDIDATES = [
    "内容",
    "评论内容",
    "评论",
    "review content",
    "review text",
    "review",
    "body",
    "buyer comments",
    "customer reviews",
]


def _norm_header(value) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def list_sheet_names(path: str | Path) -> list[str]:
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def guess_review_sheet(sheet_names: list[str]) -> str | None:
    if not sheet_names:
        return None
    for name in sheet_names:
        low = name.lower()
        if any(k in low for k in ("评论", "review", "reviews", "feedback")):
            return name
    return sheet_names[0]


def read_headers(path: str | Path, sheet_name: str) -> list[str]:
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Sheet 不存在：{sheet_name}")
        ws = wb[sheet_name]
        first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if not first:
            return []
        return ["" if c is None else str(c).strip() for c in first]
    finally:
        wb.close()


def _guess_column(headers: list[str], candidates: list[str], *, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    normalized = [(_norm_header(h), h) for h in headers if str(h or "").strip() and h not in exclude]
    for cand in candidates:
        cand_n = _norm_header(cand)
        for nh, original in normalized:
            if nh == cand_n:
                return original
    for cand in candidates:
        cand_n = _norm_header(cand)
        for nh, original in normalized:
            if cand_n in nh or nh in cand_n:
                return original
    return None


def guess_title_column(headers: list[str]) -> str | None:
    return _guess_column(headers, TITLE_HEADER_CANDIDATES)


def guess_content_column(headers: list[str], *, title_column: str | None = None) -> str | None:
    exclude = {title_column} if title_column else set()
    return _guess_column(headers, CONTENT_HEADER_CANDIDATES, exclude=exclude)


def _cell_text(row, col_idx: int | None) -> str:
    if col_idx is None or row is None or col_idx >= len(row):
        return ""
    cell = row[col_idx]
    return "" if cell is None else str(cell).strip()


def build_review_text(title: str = "", content: str = "") -> str:
    title = (title or "").strip()
    content = (content or "").strip()
    if title and content:
        return f"标题：{title}\n内容：{content}"
    if title:
        return f"标题：{title}"
    if content:
        return f"内容：{content}"
    return ""


def format_ai_input_block(review: dict) -> str:
    rid = review.get("review_id") or ""
    review_text = (review.get("review_text") or "").strip()
    if not review_text:
        review_text = build_review_text(review.get("title") or "", review.get("content") or "")
    if not review_text:
        return ""
    return f"[review_id: {rid}]\n{review_text}"


def build_reviews_block(reviews: list[dict]) -> str:
    parts = [format_ai_input_block(item) for item in reviews]
    return "\n\n".join(p for p in parts if p)


def resolve_review_columns(
    path: str | Path,
    sheet_name: str | None = None,
    *,
    title_column: str | None = None,
    content_column: str | None = None,
) -> tuple[str, str | None, str | None]:
    sheets = list_sheet_names(path)
    if not sheets:
        raise ValueError("Excel 中没有任何 Sheet")
    sheet = (sheet_name or "").strip() or guess_review_sheet(sheets) or sheets[0]
    headers = read_headers(path, sheet)
    title = (title_column or "").strip() or guess_title_column(headers)
    content = (content_column or "").strip() or guess_content_column(headers, title_column=title)
    if not title and not content:
        raise ValueError("无法识别评论标题列或内容列")
    return sheet, title, content


def count_and_load_reviews(
    path: str | Path,
    sheet_name: str,
    content_column: str | None = None,
    title_column: str | None = None,
) -> list[dict]:
    title_column = (title_column or "").strip() or None
    content_column = (content_column or "").strip() or None
    if not title_column and not content_column:
        raise ValueError("请至少选择标题列或内容列之一")

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Sheet 不存在：{sheet_name}")
        ws = wb[sheet_name]
        first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if not first:
            return []
        headers = ["" if c is None else str(c).strip() for c in first]
        if title_column and title_column not in headers:
            raise ValueError(f"找不到标题列：{title_column}")
        if content_column and content_column not in headers:
            raise ValueError(f"找不到内容列：{content_column}")
        title_idx = headers.index(title_column) if title_column else None
        content_idx = headers.index(content_column) if content_column else None

        reviews = []
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if row is None or all(c is None or str(c).strip() == "" for c in row):
                continue
            title = _cell_text(row, title_idx)
            content = _cell_text(row, content_idx)
            review_text = build_review_text(title, content)
            item = {
                "review_row": row_idx,
                "review_id": f"R{row_idx:06d}",
                "title": title,
                "content": content,
                "review_text": review_text,
                "skip_ai": not review_text,
            }
            item["ai_input"] = format_ai_input_block(item)
            reviews.append(item)
        return reviews
    finally:
        wb.close()


_HEADER_FILL = PatternFill("solid", fgColor="D9E2F3")
_SECTION_FILL = PatternFill("solid", fgColor="E7E6E6")
_TITLE_FONT = Font(name="Microsoft YaHei", size=16, bold=True, color="1F4E79")
_SECTION_FONT = Font(name="Microsoft YaHei", size=12, bold=True, color="1F4E79")
_HEADER_FONT = Font(name="Microsoft YaHei", size=10, bold=True)
_BODY_FONT = Font(name="Microsoft YaHei", size=10)
_THIN = Border(
    left=Side(style="thin", color="B0B0B0"),
    right=Side(style="thin", color="B0B0B0"),
    top=Side(style="thin", color="B0B0B0"),
    bottom=Side(style="thin", color="B0B0B0"),
)


def _display_or_dash(value) -> str:
    text = str(value or "").strip()
    return text if text else "-"


def _style_header_row(ws, row: int, start_col: int, end_col: int) -> None:
    for col in range(start_col, end_col + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _THIN


def _top_rows_for_type(summary_rows: list[dict], item_type: str, top_n: int) -> list[dict]:
    rows = [r for r in summary_rows if (r.get("item_type") or "") == item_type]
    rows.sort(key=lambda x: (-int(x.get("mention_count") or 0), str(x.get("dimension") or "")))
    return rows[: max(0, int(top_n))]


def _add_horizontal_bar_chart(
    ws,
    *,
    title: str,
    header_row: int,
    data_start_row: int,
    data_end_row: int,
    anchor: str,
) -> None:
    """Horizontal bar chart: categories=具体维度, values=提及频率."""
    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.title = title
    chart.y_axis.title = None
    chart.x_axis.title = None
    chart.x_axis.numFmt = "0.00%"
    chart.legend = None
    data = Reference(ws, min_col=3, min_row=header_row, max_row=data_end_row)
    cats = Reference(ws, min_col=1, min_row=data_start_row, max_row=data_end_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    n = max(1, data_end_row - data_start_row + 1)
    chart.shape = 4
    chart.width = 14
    chart.height = max(6, min(14, 3 + n * 0.55))
    ws.add_chart(chart, anchor)


def _build_overview_sheet(
    wb,
    *,
    summary_rows: list[dict],
    product_name: str = "",
    product_category: str = "",
    total_reviews: int = 0,
    voc_items: int = 0,
) -> list[str]:
    """Build 评论分析总览. Returns chart titles created."""
    if OVERVIEW_SHEET_NAME in wb.sheetnames:
        del wb[OVERVIEW_SHEET_NAME]
    ws = wb.create_sheet(OVERVIEW_SHEET_NAME, 0)

    ws["A1"] = "Amazon 评论分析总览"
    ws["A1"].font = _TITLE_FONT
    ws.merge_cells("A1:G1")

    meta = [
        ("产品名称", _display_or_dash(product_name)),
        ("产品类目", _display_or_dash(product_category)),
        ("评论总数", int(total_reviews or 0)),
        ("VOC提炼条目数", int(voc_items or 0)),
        ("标准维度数", len(summary_rows or [])),
    ]
    for i, (label, value) in enumerate(meta, start=2):
        ws.cell(row=i, column=1, value=label).font = Font(name="Microsoft YaHei", bold=True, size=10)
        ws.cell(row=i, column=2, value=value).font = _BODY_FONT

    ws.freeze_panes = "A7"
    for idx, width in enumerate([18, 14, 12, 12, 12, 12, 18], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    chart_titles: list[str] = []
    row = 8
    for item_type in VOC_TYPES:
        top_n = int(OVERVIEW_TOP_N.get(item_type, 5))
        chart_title = f"{item_type} TOP {top_n}"
        section_title = ws.cell(row=row, column=1, value=chart_title)
        section_title.font = _SECTION_FONT
        section_title.fill = _SECTION_FILL
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        row += 1

        top_rows = _top_rows_for_type(summary_rows or [], item_type, top_n)
        if not top_rows:
            empty = ws.cell(row=row, column=1, value="暂无数据")
            empty.font = _BODY_FONT
            row += 3
            continue

        header_row = row
        for col, name in enumerate(["具体维度", "提及评论数", "提及频率"], start=1):
            ws.cell(row=header_row, column=col, value=name)
        _style_header_row(ws, header_row, 1, 3)
        row += 1
        data_start = row
        for item in top_rows:
            ws.cell(row=row, column=1, value=item.get("dimension") or "").font = _BODY_FONT
            ws.cell(row=row, column=1).border = _THIN
            count_cell = ws.cell(row=row, column=2, value=int(item.get("mention_count") or 0))
            count_cell.font = _BODY_FONT
            count_cell.alignment = Alignment(horizontal="center")
            count_cell.border = _THIN
            rate_cell = ws.cell(row=row, column=3, value=float(item.get("mention_rate") or 0) / 100.0)
            rate_cell.number_format = "0.00%"
            rate_cell.font = _BODY_FONT
            rate_cell.alignment = Alignment(horizontal="center")
            rate_cell.border = _THIN
            row += 1
        data_end = row - 1
        _add_horizontal_bar_chart(
            ws,
            title=chart_title,
            header_row=header_row,
            data_start_row=data_start,
            data_end_row=data_end,
            anchor=f"E{header_row}",
        )
        chart_titles.append(chart_title)
        row += 3

    return chart_titles


def _build_result_sheet(wb, summary_rows: list[dict]) -> None:
    if RESULT_SHEET_NAME in wb.sheetnames:
        del wb[RESULT_SHEET_NAME]
    ws = wb.create_sheet(RESULT_SHEET_NAME)
    headers = ["类型", "具体维度", "提及评论数", "提及频率", "代表性反馈"]
    ws.append(headers)
    _style_header_row(ws, 1, 1, 5)

    for row in summary_rows or []:
        rate = float(row.get("mention_rate") or 0)
        feedback = row.get("representative_feedback") or row.get("core_description") or ""
        ws.append(
            [
                row.get("item_type") or "",
                row.get("dimension") or "",
                int(row.get("mention_count") or 0),
                rate / 100.0,
                feedback,
            ]
        )
        r = ws.max_row
        for col in range(1, 6):
            cell = ws.cell(row=r, column=col)
            cell.font = _BODY_FONT
            cell.border = _THIN
            if col == 5:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            elif col in (3, 4):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(vertical="center")
        ws.cell(row=r, column=4).number_format = "0.00%"

    ws.freeze_panes = "A2"
    if ws.max_row >= 1:
        ws.auto_filter.ref = f"A1:E{ws.max_row}"
    for idx, width in enumerate([12, 18, 12, 12, 56], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.row_dimensions[1].height = 22


def write_analysis_workbook(
    source_path: str | Path,
    output_path: str | Path,
    *,
    summary_rows: list[dict],
    product_name: str = "",
    product_category: str = "",
    total_reviews: int = 0,
    voc_items: int | None = None,
) -> dict:
    """
    Keep original sheets; append 评论分析总览 + 评论分析结果.
    Returns meta: chart_titles, sheetnames, etc.
    """
    source_path = Path(source_path)
    if source_path.exists():
        wb = load_workbook(source_path)
    else:
        wb = Workbook()
        default = wb.active
        default.title = "Sheet1"

    for name in ANALYSIS_SHEET_NAMES:
        if name in wb.sheetnames:
            del wb[name]

    summary_rows = list(summary_rows or [])
    if voc_items is None:
        voc_items = 0

    chart_titles = _build_overview_sheet(
        wb,
        summary_rows=summary_rows,
        product_name=product_name,
        product_category=product_category,
        total_reviews=total_reviews,
        voc_items=int(voc_items or 0),
    )
    _build_result_sheet(wb, summary_rows)

    # Keep overview first, result second, originals after
    desired = [OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME]
    for idx, name in enumerate(desired):
        if name in wb.sheetnames:
            wb.move_sheet(name, offset=idx - wb.sheetnames.index(name))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    sheetnames = list(wb.sheetnames)
    chart_count = len(chart_titles)
    wb.close()
    return {
        "sheetnames": sheetnames,
        "chart_titles": chart_titles,
        "chart_count": chart_count,
        "overview_sheet": OVERVIEW_SHEET_NAME,
        "result_sheet": RESULT_SHEET_NAME,
    }
