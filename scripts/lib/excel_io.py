# -*- coding: utf-8 -*-
"""Self-contained Excel helpers (no Flask / project Gateway)."""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .constants import (
    ANALYSIS_SHEET_NAMES,
    MODULE_DESCRIPTIONS,
    NEED_FULFILLMENT_SECTION_DESC,
    OVERVIEW_MIN_MENTIONS,
    OVERVIEW_SHEET_NAME,
    OVERVIEW_TOP_N,
    PRODUCT_CATEGORY_HEADER_CANDIDATES,
    PRODUCT_NAME_HEADER_CANDIDATES,
    RESULT_SHEET_NAME,
    TYPE_DISPLAY_LABELS,
)
from .statistics import build_theme_insight_summary
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


def _top_rows_for_type(
    summary_rows: list[dict],
    item_type: str,
    top_n: int | None = None,
    *,
    min_mentions: int = 0,
) -> list[dict]:
    rows = [r for r in summary_rows if (r.get("item_type") or "") == item_type]
    if min_mentions and int(min_mentions) > 0:
        rows = [r for r in rows if int(r.get("mention_count") or 0) >= int(min_mentions)]
    rows.sort(key=lambda x: (-int(x.get("mention_count") or 0), str(x.get("dimension") or "")))
    if top_n is None or int(top_n) <= 0:
        return rows
    return rows[: int(top_n)]


def _overview_limit_for_type(item_type: str) -> int | None:
    """None = unlimited. Dict value or global None from OVERVIEW_TOP_N."""
    if OVERVIEW_TOP_N is None:
        return None
    if isinstance(OVERVIEW_TOP_N, dict):
        val = OVERVIEW_TOP_N.get(item_type)
        return None if val is None else int(val)
    return None


def _truncate_label(text: str, max_chars: int = 12) -> str:
    t = str(text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + "…"


def _first_representative_feedback(text: str) -> str:
    """Take the first of up to 5 joined feedbacks. No AI rewrite."""
    t = str(text or "").strip()
    if not t:
        return ""
    for sep in ("；", ";"):
        if sep in t:
            return t.split(sep, 1)[0].strip()
    return t


def _rate_count_label(item: dict) -> str:
    rate = float(item.get("mention_rate") or 0)
    count = int(item.get("mention_count") or 0)
    return f"{rate:.2f}% ({count})"


# Dashboard layout
PORTRAIT_TYPES = ["消费人群", "产品用途", "使用场景", "购买动机"]
_CARD_ROW_HEIGHT = 22
_CHART_WIDTH = 14.0
_CHART_HEIGHT = 9.0
_LEFT_CARD_COLS = (1, 9)  # A:I
_RIGHT_CARD_COLS = (11, 19)  # K:S
_HIDDEN_START_COL = 24  # X
_PAGE_FILL = PatternFill("solid", fgColor="F5F5F5")
_CARD_FILL = PatternFill("solid", fgColor="FFFFFF")
_CARD_TITLE_FONT = Font(name="Microsoft YaHei", size=12, bold=True, color="1F4E79")
_EMPTY_FONT = Font(name="Microsoft YaHei", size=11, color="808080", italic=True)
_DIM_FONT = Font(name="Microsoft YaHei", size=10, bold=True)
_METRIC_FONT = Font(name="Microsoft YaHei", size=9, color="595959")
_FEEDBACK_FONT = Font(name="Microsoft YaHei", size=9, color="404040")
_PANEL_HEADER_FILL_NEG = PatternFill("solid", fgColor="FCE4D6")
_PANEL_HEADER_FILL_POS = PatternFill("solid", fgColor="E2EFDA")
_DATABAR_NEG = "ED7D31"
_DATABAR_POS = "70AD47"


def _fill_range(ws, r1: int, c1: int, r2: int, c2: int, fill: PatternFill) -> None:
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            ws.cell(row=r, column=c).fill = fill


def _card_border(ws, r1: int, c1: int, r2: int, c2: int) -> None:
    thin = Side(style="thin", color="D0D0D0")
    medium = Side(style="medium", color="BFBFBF")
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = Border(
                left=medium if c == c1 else thin,
                right=medium if c == c2 else thin,
                top=medium if r == r1 else thin,
                bottom=medium if r == r2 else thin,
            )


def _ensure_analysis_sheets_at_end(wb, original_sheet_order: list[str]) -> None:
    originals = [n for n in original_sheet_order if n in wb.sheetnames]
    analysis = [n for n in (OVERVIEW_SHEET_NAME, RESULT_SHEET_NAME) if n in wb.sheetnames]
    known = set(originals) | set(analysis)
    extras = [n for n in wb.sheetnames if n not in known]
    desired = originals + extras + analysis
    sheets_by_name = {ws.title: ws for ws in wb._sheets}
    wb._sheets = [sheets_by_name[n] for n in desired]


def _add_portrait_column_chart(
    ws,
    *,
    title: str,
    header_row: int,
    data_start_row: int,
    data_end_row: int,
    cat_col: int,
    value_col: int,
    anchor: str,
    y_max: float | None = None,
) -> None:
    chart = BarChart()
    chart.type = "col"
    chart.style = 10
    chart.title = title
    # Critical: helper data lives in hidden columns; Excel skips them when True.
    chart.visible_cells_only = False
    chart.y_axis.title = None
    chart.x_axis.title = None
    chart.y_axis.numFmt = "0%"
    chart.y_axis.scaling.min = 0
    if y_max is not None and y_max > 0:
        # Pad headroom so small rates remain readable; cap at 100%.
        chart.y_axis.scaling.max = min(1.0, max(0.05, float(y_max) * 1.25))
    chart.legend = None
    data = Reference(ws, min_col=value_col, min_row=header_row, max_row=data_end_row)
    cats = Reference(ws, min_col=cat_col, min_row=data_start_row, max_row=data_end_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape = 4
    n_points = max(1, data_end_row - data_start_row + 1)
    # Widen slightly when many categories so labels stay readable
    chart.width = _CHART_WIDTH + min(6.0, max(0.0, (n_points - 5) * 0.6))
    chart.height = _CHART_HEIGHT
    labels = DataLabelList()
    labels.showVal = True
    labels.showCatName = False
    labels.showSerName = False
    chart.dataLabels = labels
    if chart.series:
        chart.series[0].dLbls = labels
    ws.add_chart(chart, anchor)


def _write_portrait_module(
    ws,
    *,
    card_row: int,
    card_col_start: int,
    card_col_end: int,
    item_type: str,
    summary_rows: list[dict],
    hidden_cat_col: int,
    hidden_val_col: int,
    hidden_header_row: int,
) -> dict:
    top_n = _overview_limit_for_type(item_type)
    display = type_display_label(item_type)
    card_end_row = card_row + _CARD_ROW_HEIGHT - 1
    _fill_range(ws, card_row, card_col_start, card_end_row, card_col_end, _CARD_FILL)
    _card_border(ws, card_row, card_col_start, card_end_row, card_col_end)

    title_cell = ws.cell(row=card_row, column=card_col_start, value=display)
    title_cell.font = _CARD_TITLE_FONT
    title_cell.fill = _CARD_FILL
    ws.merge_cells(
        start_row=card_row,
        start_column=card_col_start,
        end_row=card_row,
        end_column=min(card_col_start + 7, card_col_end),
    )

    desc = MODULE_DESCRIPTIONS.get(item_type) or ""
    desc_cell = ws.cell(row=card_row + 1, column=card_col_start, value=desc)
    desc_cell.font = Font(name="Microsoft YaHei", size=8, color="666666")
    desc_cell.alignment = Alignment(wrap_text=True, vertical="top")
    desc_cell.fill = _CARD_FILL
    ws.merge_cells(
        start_row=card_row + 1,
        start_column=card_col_start,
        end_row=card_row + 1,
        end_column=card_col_end,
    )
    ws.row_dimensions[card_row + 1].height = 28

    top_rows = _top_rows_for_type(
        summary_rows or [],
        item_type,
        top_n,
        min_mentions=OVERVIEW_MIN_MENTIONS,
    )
    if OVERVIEW_MIN_MENTIONS and OVERVIEW_MIN_MENTIONS > 0:
        sub_text = f"提及≥{OVERVIEW_MIN_MENTIONS} · 共 {len(top_rows)} 项 · 提及频率"
        if top_n is not None:
            sub_text = f"Top {top_n} · 提及≥{OVERVIEW_MIN_MENTIONS} · 提及频率"
    else:
        sub_text = f"共 {len(top_rows)} 项 · 提及频率"
        if top_n is not None:
            sub_text = f"Top {top_n} · 提及频率"
    sub = ws.cell(row=card_row + 2, column=card_col_start, value=sub_text)
    sub.font = Font(name="Microsoft YaHei", size=9, color="808080")
    sub.fill = _CARD_FILL

    if not top_rows:
        msg_row = card_row + (_CARD_ROW_HEIGHT // 2)
        msg = ws.cell(row=msg_row, column=card_col_start, value="暂无足够评论证据")
        msg.font = _EMPTY_FONT
        msg.alignment = Alignment(horizontal="center", vertical="center")
        msg.fill = _CARD_FILL
        ws.merge_cells(
            start_row=msg_row,
            start_column=card_col_start,
            end_row=msg_row,
            end_column=card_col_end,
        )
        return {"type": item_type, "title": display, "has_chart": False, "chart_title": None}

    ws.cell(row=hidden_header_row, column=hidden_cat_col, value="维度")
    ws.cell(row=hidden_header_row, column=hidden_val_col, value="提及频率")
    for i, item in enumerate(top_rows):
        r = hidden_header_row + 1 + i
        dim = str(item.get("dimension") or "")
        ws.cell(row=r, column=hidden_cat_col, value=_truncate_label(dim, 12))
        rate_cell = ws.cell(
            row=r,
            column=hidden_val_col,
            value=float(item.get("mention_rate") or 0) / 100.0,
        )
        rate_cell.number_format = "0.00%"

    data_start = hidden_header_row + 1
    data_end = hidden_header_row + len(top_rows)
    if top_n is None:
        chart_title = f"{display}（{len(top_rows)}）"
    else:
        chart_title = f"{display} TOP {top_n}"
    # Chart below title + description + meta line
    anchor = f"{get_column_letter(card_col_start)}{card_row + 3}"
    y_max = max(float(item.get("mention_rate") or 0) / 100.0 for item in top_rows)
    _add_portrait_column_chart(
        ws,
        title=chart_title,
        header_row=hidden_header_row,
        data_start_row=data_start,
        data_end_row=data_end,
        cat_col=hidden_cat_col,
        value_col=hidden_val_col,
        anchor=anchor,
        y_max=y_max,
    )
    return {
        "type": item_type,
        "title": display,
        "has_chart": True,
        "chart_title": chart_title,
    }


def _apply_databar(ws, cell_range: str, color: str) -> None:
    rule = DataBarRule(
        start_type="num",
        start_value=0,
        end_type="num",
        end_value=1,
        color=color,
        showValue=False,
        minLength=None,
        maxLength=None,
    )
    ws.conditional_formatting.add(cell_range, rule)


def _write_feedback_panel(
    ws,
    *,
    start_row: int,
    col_start: int,
    item_type: str,
    summary_rows: list[dict],
    header_fill: PatternFill,
    databar_color: str,
) -> int:
    display = type_display_label(item_type)
    top_n = _overview_limit_for_type(item_type)
    dim_c = col_start
    bar_c = col_start + 2
    metric_c = col_start + 3
    fb_c = col_start + 4
    fb_end = col_start + 8

    header = ws.cell(row=start_row, column=dim_c, value=display)
    header.font = _CARD_TITLE_FONT
    header.fill = header_fill
    for c in range(dim_c, fb_end + 1):
        ws.cell(row=start_row, column=c).fill = header_fill
    ws.merge_cells(start_row=start_row, start_column=dim_c, end_row=start_row, end_column=fb_end)
    ws.row_dimensions[start_row].height = 22

    desc = MODULE_DESCRIPTIONS.get(item_type) or ""
    desc_cell = ws.cell(row=start_row + 1, column=dim_c, value=desc)
    desc_cell.font = Font(name="Microsoft YaHei", size=8, color="666666")
    desc_cell.alignment = Alignment(wrap_text=True, vertical="center")
    for c in range(dim_c, fb_end + 1):
        ws.cell(row=start_row + 1, column=c).fill = PatternFill("solid", fgColor="FAFAFA")
    ws.merge_cells(
        start_row=start_row + 1,
        start_column=dim_c,
        end_row=start_row + 1,
        end_column=fb_end,
    )
    ws.row_dimensions[start_row + 1].height = 26

    top_rows = _top_rows_for_type(
        summary_rows or [],
        item_type,
        top_n,
        min_mentions=OVERVIEW_MIN_MENTIONS,
    )
    if not top_rows:
        r = start_row + 3
        cell = ws.cell(row=r, column=dim_c, value="暂无足够评论证据")
        cell.font = _EMPTY_FONT
        ws.merge_cells(start_row=r, start_column=dim_c, end_row=r, end_column=fb_end)
        return 4

    bar_start_row = start_row + 2
    for i, item in enumerate(top_rows):
        r = start_row + 2 + i
        ws.row_dimensions[r].height = 48
        dim = str(item.get("dimension") or "")
        dim_cell = ws.cell(row=r, column=dim_c, value=dim)
        dim_cell.font = _DIM_FONT
        dim_cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.merge_cells(start_row=r, start_column=dim_c, end_row=r, end_column=dim_c + 1)

        rate = float(item.get("mention_rate") or 0) / 100.0
        bar_cell = ws.cell(row=r, column=bar_c, value=rate)
        bar_cell.number_format = "0.00%"
        bar_cell.alignment = Alignment(vertical="center")

        metric = ws.cell(row=r, column=metric_c, value=_rate_count_label(item))
        metric.font = _METRIC_FONT
        metric.alignment = Alignment(horizontal="left", vertical="center")

        fb = item.get("theme_summary") or build_theme_insight_summary(item)
        fb_cell = ws.cell(row=r, column=fb_c, value=fb)
        fb_cell.font = _FEEDBACK_FONT
        fb_cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.merge_cells(start_row=r, start_column=fb_c, end_row=r, end_column=fb_end)

        for c in range(dim_c, fb_end + 1):
            ws.cell(row=r, column=c).border = Border(bottom=Side(style="hair", color="E0E0E0"))

    bar_end_row = start_row + 1 + len(top_rows)
    col_letter = get_column_letter(bar_c)
    _apply_databar(ws, f"{col_letter}{bar_start_row}:{col_letter}{bar_end_row}", databar_color)
    return 2 + len(top_rows)


def _build_overview_sheet(
    wb,
    *,
    summary_rows: list[dict],
    product_name: str = "",
    product_category: str = "",
    total_reviews: int = 0,
    voc_items: int = 0,
) -> dict:
    """Dashboard: meta + 2x2 charts + dual feedback DataBar panels."""
    if OVERVIEW_SHEET_NAME in wb.sheetnames:
        del wb[OVERVIEW_SHEET_NAME]
    ws = wb.create_sheet(OVERVIEW_SHEET_NAME)
    ws.sheet_view.showGridLines = False

    for r in range(1, 100):
        for c in range(1, 20):
            ws.cell(row=r, column=c).fill = _PAGE_FILL

    ws["A1"] = "Amazon 评论分析总览"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].fill = _PAGE_FILL
    ws.merge_cells("A1:I1")
    ws.row_dimensions[1].height = 28

    # One compact meta line (no conclusion block)
    meta_row = 3
    product_name = str(product_name or "").strip()
    product_category = str(product_category or "").strip()
    parts: list[str] = []
    if product_name:
        parts.append(f"产品名称：{product_name}")
    if product_category:
        parts.append(f"产品类目：{product_category}")
    parts.extend(
        [
            f"评论总数：{int(total_reviews or 0)}",
            f"评论洞察条目数：{int(voc_items or 0)}",
            f"标准维度数：{len(summary_rows or [])}",
        ]
    )
    meta = ws.cell(row=meta_row, column=1, value="　　".join(parts))
    meta.font = Font(name="Microsoft YaHei", size=10, color="404040")
    meta.alignment = Alignment(vertical="center", wrap_text=False)
    ws.merge_cells(start_row=meta_row, start_column=1, end_row=meta_row, end_column=19)
    ws.row_dimensions[meta_row].height = 22

    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 10
    for letter in ("G", "H", "I"):
        ws.column_dimensions[letter].width = 12
    ws.column_dimensions["J"].width = 2
    ws.column_dimensions["K"].width = 16
    ws.column_dimensions["L"].width = 12
    ws.column_dimensions["M"].width = 14
    ws.column_dimensions["N"].width = 14
    for letter in ("O", "P", "Q", "R", "S"):
        ws.column_dimensions[letter].width = 12

    for col_i in range(_HIDDEN_START_COL, _HIDDEN_START_COL + 8):
        letter = get_column_letter(col_i)
        ws.column_dimensions[letter].hidden = True
        ws.column_dimensions[letter].width = 12

    upper_start = meta_row + 2
    ws.freeze_panes = f"A{upper_start}"

    # Portrait modules (2×2) — no section banner
    grid_start = upper_start

    module_metas: list[dict] = []
    chart_titles: list[str] = []
    for idx, item_type in enumerate(PORTRAIT_TYPES):
        grid_r = idx // 2
        grid_c = idx % 2
        card_row = grid_start + grid_r * _CARD_ROW_HEIGHT
        c1, c2 = _LEFT_CARD_COLS if grid_c == 0 else _RIGHT_CARD_COLS
        hidden_cat = _HIDDEN_START_COL + idx * 2
        hidden_val = hidden_cat + 1
        # Each portrait module uses its own hidden column pair; all start at row 1
        hidden_header_row = 1
        meta = _write_portrait_module(
            ws,
            card_row=card_row,
            card_col_start=c1,
            card_col_end=c2,
            item_type=item_type,
            summary_rows=summary_rows or [],
            hidden_cat_col=hidden_cat,
            hidden_val_col=hidden_val,
            hidden_header_row=hidden_header_row,
        )
        module_metas.append(meta)
        if meta.get("chart_title"):
            chart_titles.append(meta["chart_title"])

    feedback_label_row = grid_start + 2 * _CARD_ROW_HEIGHT + 1
    sec = ws.cell(
        row=feedback_label_row,
        column=1,
        value="需求满足分析（用户满意 / 未被满足）",
    )
    sec.font = Font(name="Microsoft YaHei", size=11, bold=True, color="1F4E79")
    ws.merge_cells(
        start_row=feedback_label_row,
        start_column=1,
        end_row=feedback_label_row,
        end_column=19,
    )
    sec_desc = ws.cell(
        row=feedback_label_row + 1,
        column=1,
        value=NEED_FULFILLMENT_SECTION_DESC,
    )
    sec_desc.font = Font(name="Microsoft YaHei", size=8, color="666666")
    sec_desc.alignment = Alignment(wrap_text=True)
    ws.merge_cells(
        start_row=feedback_label_row + 1,
        start_column=1,
        end_row=feedback_label_row + 1,
        end_column=19,
    )
    ws.row_dimensions[feedback_label_row + 1].height = 24
    panel_start = feedback_label_row + 2

    left_rows = _write_feedback_panel(
        ws,
        start_row=panel_start,
        col_start=_LEFT_CARD_COLS[0],
        item_type="用户不满",
        summary_rows=summary_rows or [],
        header_fill=_PANEL_HEADER_FILL_NEG,
        databar_color=_DATABAR_NEG,
    )
    right_rows = _write_feedback_panel(
        ws,
        start_row=panel_start,
        col_start=_RIGHT_CARD_COLS[0],
        item_type="用户满意",
        summary_rows=summary_rows or [],
        header_fill=_PANEL_HEADER_FILL_POS,
        databar_color=_DATABAR_POS,
    )

    return {
        "chart_titles": chart_titles,
        "chart_count": len(chart_titles),
        "module_metas": module_metas,
        "feedback_left_rows": left_rows,
        "feedback_right_rows": right_rows,
        "upper_start": upper_start,
        "feedback_start": panel_start,
    }


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
    """Keep original sheets; append dashboard overview + result at end."""
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

    overview_meta = _build_overview_sheet(
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
    wb.close()
    return {
        "sheetnames": sheetnames,
        "chart_titles": overview_meta.get("chart_titles") or [],
        "chart_count": int(overview_meta.get("chart_count") or 0),
        "module_metas": overview_meta.get("module_metas") or [],
        "overview_sheet": OVERVIEW_SHEET_NAME,
        "result_sheet": RESULT_SHEET_NAME,
        "feedback_start": overview_meta.get("feedback_start"),
    }
