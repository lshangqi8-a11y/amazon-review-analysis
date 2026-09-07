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
    PRODUCT_CATEGORY_HEADER_CANDIDATES,
    PRODUCT_NAME_HEADER_CANDIDATES,
    RESULT_SHEET_NAME,
    TYPE_DISPLAY_LABELS,
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


def type_display_label(item_type: str) -> str:
    t = (item_type or "").strip()
    return TYPE_DISPLAY_LABELS.get(t, t)


def guess_product_fields(
    path: str | Path,
    sheet_name: str,
) -> tuple[str, str]:
    """
    Optionally read a single reliable product_name / product_category from Excel.
    Returns ("", "") when not reliably available. No AI.
    """
    headers = read_headers(path, sheet_name)
    name_col = _guess_column(headers, PRODUCT_NAME_HEADER_CANDIDATES)
    cat_col = _guess_column(
        headers,
        PRODUCT_CATEGORY_HEADER_CANDIDATES,
        exclude={name_col} if name_col else set(),
    )
    if not name_col and not cat_col:
        return "", ""

    name_idx = headers.index(name_col) if name_col else None
    cat_idx = headers.index(cat_col) if cat_col else None
    names: set[str] = set()
    cats: set[str] = set()
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None:
                continue
            if name_idx is not None:
                v = _cell_text(row, name_idx)
                if v:
                    names.add(v)
            if cat_idx is not None:
                v = _cell_text(row, cat_idx)
                if v:
                    cats.add(v)
    finally:
        wb.close()

    product_name = next(iter(names)) if len(names) == 1 else ""
    product_category = next(iter(cats)) if len(cats) == 1 else ""
    return product_name, product_category


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


def _truncate_label(text: str, max_chars: int = 14) -> str:
    t = str(text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + "…"


# Overview fixed grid: 2 columns × 3 rows (table left / chart right per cell)
_GRID_BLOCK_HEIGHT = 24
_LEFT_TABLE_COL = 1   # A
_LEFT_CAT_COL = 4     # D (chart categories, truncated; hidden)
_LEFT_CHART_ANCHOR_COL = "E"
_RIGHT_TABLE_COL = 9  # I
_RIGHT_CAT_COL = 12   # L (hidden)
_RIGHT_CHART_ANCHOR_COL = "M"
_CHART_WIDTH = 12.0
_CHART_HEIGHT = 8.0


def _add_column_chart(
    ws,
    *,
    title: str,
    header_row: int,
    data_start_row: int,
    data_end_row: int,
    value_col: int,
    cat_col: int,
    anchor: str,
) -> None:
    """Vertical column chart: categories from cat_col, values=提及频率."""
    chart = BarChart()
    chart.type = "col"
    chart.style = 10
    chart.title = title
    chart.y_axis.title = None
    chart.x_axis.title = None
    chart.y_axis.numFmt = "0.00%"
    chart.legend = None
    data = Reference(ws, min_col=value_col, min_row=header_row, max_row=data_end_row)
    cats = Reference(ws, min_col=cat_col, min_row=data_start_row, max_row=data_end_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape = 4
    chart.width = _CHART_WIDTH
    chart.height = _CHART_HEIGHT
    ws.add_chart(chart, anchor)


def _ensure_analysis_sheets_at_end(wb, original_sheet_order: list[str]) -> None:
    """
    Explicitly force final order:
    [original sheets in original order] + 评论分析总览 + 评论分析结果
    Does not rely on create_sheet / move_sheet defaults alone.
    """
    originals = [n for n in original_sheet_order if n in wb.sheetnames]
    analysis = [n for n in (OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME) if n in wb.sheetnames]
    known = set(originals) | set(analysis)
    extras = [n for n in wb.sheetnames if n not in known]
    desired = originals + extras + analysis
    sheets_by_name = {ws.title: ws for ws in wb._sheets}
    wb._sheets = [sheets_by_name[n] for n in desired]


def _write_module_block(
    ws,
    *,
    start_row: int,
    table_col: int,
    cat_col: int,
    chart_anchor_col: str,
    item_type: str,
    summary_rows: list[dict],
) -> str:
    """Write one TOP table + column chart in a grid cell. Returns chart title."""
    top_n = int(OVERVIEW_TOP_N.get(item_type, 5))
    display = type_display_label(item_type)
    chart_title = f"{display} TOP {top_n}"

    title_cell = ws.cell(row=start_row, column=table_col, value=chart_title)
    title_cell.font = _SECTION_FONT
    title_cell.fill = _SECTION_FILL
    ws.merge_cells(
        start_row=start_row,
        start_column=table_col,
        end_row=start_row,
        end_column=table_col + 2,
    )
    ws.row_dimensions[start_row].height = 20

    header_row = start_row + 1
    for offset, name in enumerate(["具体维度", "提及评论数", "提及频率"]):
        ws.cell(row=header_row, column=table_col + offset, value=name)
    _style_header_row(ws, header_row, table_col, table_col + 2)
    # Hidden header for chart category series alignment
    ws.cell(row=header_row, column=cat_col, value="图表标签")

    top_rows = _top_rows_for_type(summary_rows or [], item_type, top_n)
    if not top_rows:
        top_rows = [{"dimension": "暂无数据", "mention_count": 0, "mention_rate": 0}]

    data_start = header_row + 1
    row = data_start
    for item in top_rows:
        dim = str(item.get("dimension") or "")
        dim_cell = ws.cell(row=row, column=table_col, value=dim)
        dim_cell.font = _BODY_FONT
        dim_cell.border = _THIN
        dim_cell.alignment = Alignment(wrap_text=True, vertical="center")

        count_cell = ws.cell(row=row, column=table_col + 1, value=int(item.get("mention_count") or 0))
        count_cell.font = _BODY_FONT
        count_cell.alignment = Alignment(horizontal="center")
        count_cell.border = _THIN

        rate_cell = ws.cell(
            row=row,
            column=table_col + 2,
            value=float(item.get("mention_rate") or 0) / 100.0,
        )
        rate_cell.number_format = "0.00%"
        rate_cell.font = _BODY_FONT
        rate_cell.alignment = Alignment(horizontal="center")
        rate_cell.border = _THIN

        ws.cell(row=row, column=cat_col, value=_truncate_label(dim))
        row += 1
    data_end = row - 1

    # Chart to the RIGHT of the table (same block row) — never over the table cells
    _add_column_chart(
        ws,
        title=chart_title,
        header_row=header_row,
        data_start_row=data_start,
        data_end_row=data_end,
        value_col=table_col + 2,
        cat_col=cat_col,
        anchor=f"{chart_anchor_col}{start_row}",
    )
    return chart_title


def _build_overview_sheet(
    wb,
    *,
    summary_rows: list[dict],
    product_name: str = "",
    product_category: str = "",
    total_reviews: int = 0,
    voc_items: int = 0,
) -> list[str]:
    """Build 评论分析总览: meta + fixed 2×3 grid (table | chart)."""
    if OVERVIEW_SHEET_NAME in wb.sheetnames:
        del wb[OVERVIEW_SHEET_NAME]
    ws = wb.create_sheet(OVERVIEW_SHEET_NAME)

    ws["A1"] = "Amazon 评论分析总览"
    ws["A1"].font = _TITLE_FONT
    ws.merge_cells("A1:F1")
    ws.row_dimensions[1].height = 28

    row = 3
    product_name = str(product_name or "").strip()
    product_category = str(product_category or "").strip()
    # Show product rows only when present (no "-" placeholders)
    if product_name:
        ws.cell(row=row, column=1, value="产品名称").font = Font(name="Microsoft YaHei", bold=True, size=10)
        ws.cell(row=row, column=2, value=product_name).font = _BODY_FONT
        row += 1
    if product_category:
        ws.cell(row=row, column=1, value="产品类目").font = Font(name="Microsoft YaHei", bold=True, size=10)
        ws.cell(row=row, column=2, value=product_category).font = _BODY_FONT
        row += 1

    for label, value in (
        ("评论总数", int(total_reviews or 0)),
        ("VOC提炼条目数", int(voc_items or 0)),
        ("标准维度数", len(summary_rows or [])),
    ):
        ws.cell(row=row, column=1, value=label).font = Font(name="Microsoft YaHei", bold=True, size=10)
        ws.cell(row=row, column=2, value=value).font = _BODY_FONT
        row += 1

    grid_start = row + 2
    ws.freeze_panes = f"A{grid_start}"

    widths = {
        "A": 20,
        "B": 12,
        "C": 12,
        "D": 3,
        "E": 3,
        "F": 3,
        "G": 3,
        "H": 3,
        "I": 20,
        "J": 12,
        "K": 12,
        "L": 3,
        "M": 3,
        "N": 3,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.column_dimensions["D"].hidden = True
    ws.column_dimensions["L"].hidden = True

    chart_titles: list[str] = []
    for idx, item_type in enumerate(VOC_TYPES):
        grid_r = idx // 2
        grid_c = idx % 2
        start_row = grid_start + grid_r * _GRID_BLOCK_HEIGHT
        if grid_c == 0:
            title = _write_module_block(
                ws,
                start_row=start_row,
                table_col=_LEFT_TABLE_COL,
                cat_col=_LEFT_CAT_COL,
                chart_anchor_col=_LEFT_CHART_ANCHOR_COL,
                item_type=item_type,
                summary_rows=summary_rows or [],
            )
        else:
            title = _write_module_block(
                ws,
                start_row=start_row,
                table_col=_RIGHT_TABLE_COL,
                cat_col=_RIGHT_CAT_COL,
                chart_anchor_col=_RIGHT_CHART_ANCHOR_COL,
                item_type=item_type,
                summary_rows=summary_rows or [],
            )
        chart_titles.append(title)

    return chart_titles


def _build_result_sheet(wb, summary_rows: list[dict]) -> None:
    if RESULT_SHEET_NAME in wb.sheetnames:
        del wb[RESULT_SHEET_NAME]
    ws = wb.create_sheet(RESULT_SHEET_NAME)  # append to end
    headers = ["类型", "具体维度", "提及评论数", "提及频率", "代表性反馈"]
    ws.append(headers)
    _style_header_row(ws, 1, 1, 5)

    for row in summary_rows or []:
        rate = float(row.get("mention_rate") or 0)
        feedback = row.get("representative_feedback") or row.get("core_description") or ""
        item_type = row.get("item_type") or ""
        ws.append(
            [
                type_display_label(item_type),
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
    Keep original sheets (order/data/format); append 评论分析总览 + 评论分析结果 at end.
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

    original_sheet_order = list(wb.sheetnames)

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
    _ensure_analysis_sheets_at_end(wb, original_sheet_order)

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
