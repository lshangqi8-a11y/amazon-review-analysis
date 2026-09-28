# -*- coding: utf-8 -*-
"""Self-contained Excel helpers (no Flask / project Gateway)."""
from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .constants import (
    ANALYSIS_SHEET_NAMES,
    CONTEXT_SECTION_DESC,
    EXCEL_PERCENT_FORMAT,
    LABEL_OTHER,
    MODULE_DESCRIPTIONS,
    NEED_FULFILLMENT_SECTION_DESC,
    OVERVIEW_CHART_TYPES,
    OVERVIEW_MIN_MENTIONS,
    OVERVIEW_SHEET_NAME,
    OVERVIEW_TOP_N,
    PRODUCT_CATEGORY_HEADER_CANDIDATES,
    PRODUCT_NAME_HEADER_CANDIDATES,
    RESULT_SHEET_NAME,
    SEGMENT_INSIGHT_SHEET_NAME,
    SEGMENT_RELATED_TYPES,
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
    # Long-tail bucket is for the result sheet audit, not for overview charts.
    rows = [r for r in rows if str(r.get("dimension") or "") != LABEL_OTHER]
    if min_mentions and int(min_mentions) > 0:
        rows = [r for r in rows if int(r.get("mention_count") or 0) >= int(min_mentions)]
    rows.sort(key=lambda x: (-int(x.get("mention_count") or 0), str(x.get("dimension") or "")))
    if top_n is None or int(top_n) <= 0:
        return rows
    return rows[: int(top_n)]


def _overview_limit_for_type(item_type: str) -> int | None:
    """None = unlimited. Dict value, or a global int from OVERVIEW_TOP_N."""
    if OVERVIEW_TOP_N is None:
        return None
    if isinstance(OVERVIEW_TOP_N, dict):
        val = OVERVIEW_TOP_N.get(item_type)
        return None if val is None else int(val)
    return int(OVERVIEW_TOP_N)


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


def _rate_count_label(item: dict, total_reviews: int = 0) -> str:
    rate = float(item.get("mention_rate") or 0)
    count = int(item.get("mention_count") or 0)
    total = int(total_reviews or 0)
    if total > 0:
        return f"{rate:.2f}%（{count}/{total}）"
    return f"{rate:.2f}%（{count}）"


def _bar_share_label(share_pct: float) -> str:
    """Compact on-bar label for module-internal share (e.g. 83.3%)."""
    rate = float(share_pct or 0)
    if abs(rate - round(rate)) < 0.05:
        rate_txt = f"{rate:.0f}"
    else:
        rate_txt = f"{rate:.1f}"
    return f"{rate_txt}%"


def _module_composition_shares(top_rows: list[dict]) -> list[float]:
    """
    Module-internal composition fractions that sum to ~1.0.
    share = mention_count / sum(mention_count of displayed dims).
    """
    counts = [max(0, int(r.get("mention_count") or 0)) for r in top_rows]
    denom = sum(counts)
    if denom <= 0:
        return [0.0 for _ in top_rows]
    return [c / denom for c in counts]


PORTRAIT_TYPES = list(OVERVIEW_CHART_TYPES)
_CARD_ROW_HEIGHT = 18
_CHART_WIDTH = 10.5
_CHART_HEIGHT = 9.0
_CHART_LEFT_COLS = (1, 7)  # A:G
_CHART_RIGHT_COLS = (9, 14)  # I:N
_PANEL_LEFT_COLS = (1, 7)
_PANEL_RIGHT_COLS = (9, 14)
_LEFT_ZONE_END = 14  # N
_SUMMARY_COL_START = 15  # O
_SUMMARY_COL_END = 21  # U
_HIDDEN_START_COL = 24
_PAGE_FILL = PatternFill("solid", fgColor="F5F5F5")
_CARD_FILL = PatternFill("solid", fgColor="FFFFFF")
_CARD_TITLE_FONT = Font(name="Microsoft YaHei", size=12, bold=True, color="1F4E79")
_EMPTY_FONT = Font(name="Microsoft YaHei", size=11, color="808080", italic=True)
_DIM_FONT = Font(name="Microsoft YaHei", size=10, bold=True)
_METRIC_FONT = Font(name="Microsoft YaHei", size=9, color="595959")
_FEEDBACK_FONT = Font(name="Microsoft YaHei", size=9, color="404040")
_PANEL_HEADER_FILL_NEG = PatternFill("solid", fgColor="FCE4D6")
_PANEL_HEADER_FILL_POS = PatternFill("solid", fgColor="E2EFDA")
_PANEL_HEADER_FILL_CTX = PatternFill("solid", fgColor="D6EAF8")
_DATABAR_NEG = "ED7D31"
_DATABAR_POS = "70AD47"
_DATABAR_CTX = "5B9BD5"
_SUMMARY_FILL = PatternFill("solid", fgColor="FFFFFF")
_SUMMARY_HEADER_FILL = PatternFill("solid", fgColor="D6EAF8")


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
    analysis = [
        n
        for n in (
            OVERVIEW_SHEET_NAME,
            SEGMENT_INSIGHT_SHEET_NAME,
            RESULT_SHEET_NAME,
        )
        if n in wb.sheetnames
    ]
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
    # Values hidden here; custom 6%（6/100） labels injected after save from label cells.
    labels = DataLabelList()
    labels.showVal = False
    labels.showCatName = False
    labels.showSerName = False
    chart.dataLabels = labels
    if chart.series:
        chart.series[0].dLbls = labels
    ws.add_chart(chart, anchor)


def _patch_chart_datalabels_from_cells(
    xlsx_path: Path,
    label_payloads: list[dict],
) -> None:
    """
    Inject Excel 'Values From Cells' data labels into portrait charts.

    label_payloads: ordered list matching chart1..N, each with:
      formula: e.g. \"'评论分析总览'!$Z$2:$Z$7\"
      values: list[str] cached label texts
    """
    if not label_payloads:
        return
    ns_c = "http://schemas.openxmlformats.org/drawingml/2006/chart"
    ns_c15 = "http://schemas.microsoft.com/office/drawing/2012/chart"
    ET.register_namespace("c", ns_c)
    ET.register_namespace("c15", ns_c15)
    uri_show = "{CE6537A1-D777-4B75-AEB2-F5D3B9D8D6C5}"
    uri_range = "{02D57815-91ED-43cb-92C2-25804820EDAC}"

    path = Path(xlsx_path)
    buf = BytesIO(path.read_bytes())
    out = BytesIO()
    with zipfile.ZipFile(buf, "r") as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            m = re.fullmatch(r"xl/charts/chart(\d+)\.xml", info.filename.replace("\\", "/"))
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(label_payloads):
                    data = _inject_datalabel_range_xml(
                        data,
                        formula=label_payloads[idx]["formula"],
                        values=label_payloads[idx]["values"],
                        ns_c=ns_c,
                        ns_c15=ns_c15,
                        uri_show=uri_show,
                        uri_range=uri_range,
                    )
            zout.writestr(info, data)
    path.write_bytes(out.getvalue())


def _inject_datalabel_range_xml(
    xml_bytes: bytes,
    *,
    formula: str,
    values: list[str],
    ns_c: str,
    ns_c15: str,
    uri_show: str,
    uri_range: str,
) -> bytes:
    root = ET.fromstring(xml_bytes)
    ser = root.find(f".//{{{ns_c}}}ser")
    if ser is None:
        return xml_bytes

    # Ensure dLbls under ser
    dLbls = ser.find(f"{{{ns_c}}}dLbls")
    if dLbls is None:
        dLbls = ET.SubElement(ser, f"{{{ns_c}}}dLbls")
    for tag, val in (
        ("showLegendKey", "0"),
        ("showVal", "0"),
        ("showCatName", "0"),
        ("showSerName", "0"),
        ("showPercent", "0"),
        ("showBubbleSize", "0"),
    ):
        node = dLbls.find(f"{{{ns_c}}}{tag}")
        if node is None:
            node = ET.SubElement(dLbls, f"{{{ns_c}}}{tag}")
        node.set("val", val)

    # dLbls ext: showDataLabelsRange=1
    d_ext_lst = dLbls.find(f"{{{ns_c}}}extLst")
    if d_ext_lst is None:
        d_ext_lst = ET.SubElement(dLbls, f"{{{ns_c}}}extLst")
    d_ext = None
    for ext in d_ext_lst.findall(f"{{{ns_c}}}ext"):
        if ext.get("uri") == uri_show:
            d_ext = ext
            break
    if d_ext is None:
        d_ext = ET.SubElement(d_ext_lst, f"{{{ns_c}}}ext")
        d_ext.set("uri", uri_show)
    show = d_ext.find(f"{{{ns_c15}}}showDataLabelsRange")
    if show is None:
        show = ET.SubElement(d_ext, f"{{{ns_c15}}}showDataLabelsRange")
    show.set("val", "1")

    # ser ext: datalabelsRange + cache
    s_ext_lst = ser.find(f"{{{ns_c}}}extLst")
    if s_ext_lst is None:
        s_ext_lst = ET.SubElement(ser, f"{{{ns_c}}}extLst")
    s_ext = None
    for ext in s_ext_lst.findall(f"{{{ns_c}}}ext"):
        if ext.get("uri") == uri_range:
            s_ext = ext
            break
    if s_ext is None:
        s_ext = ET.SubElement(s_ext_lst, f"{{{ns_c}}}ext")
        s_ext.set("uri", uri_range)
    # clear old
    for child in list(s_ext):
        s_ext.remove(child)
    dl_range = ET.SubElement(s_ext, f"{{{ns_c15}}}datalabelsRange")
    f_node = ET.SubElement(dl_range, f"{{{ns_c15}}}f")
    f_node.text = formula
    cache = ET.SubElement(dl_range, f"{{{ns_c15}}}dlblRangeCache")
    pt_count = ET.SubElement(cache, f"{{{ns_c}}}ptCount")
    pt_count.set("val", str(len(values)))
    for i, text in enumerate(values):
        pt = ET.SubElement(cache, f"{{{ns_c}}}pt")
        pt.set("idx", str(i))
        v = ET.SubElement(pt, f"{{{ns_c}}}v")
        v.text = text
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


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
    hidden_label_col: int,
    hidden_header_row: int,
    total_reviews: int = 0,
) -> dict:
    """Compact chart card: bars = module-internal composition share (sum ≈ 100%)."""
    del total_reviews  # charts no longer use coverage / analyzed_reviews
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

    top_rows = _top_rows_for_type(
        summary_rows or [],
        item_type,
        top_n,
        min_mentions=OVERVIEW_MIN_MENTIONS,
    )

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
        return {
            "type": item_type,
            "title": display,
            "has_chart": False,
            "chart_title": None,
            "label_payload": None,
            "composition_sum": 0.0,
        }

    shares = _module_composition_shares(top_rows)
    ws.cell(row=hidden_header_row, column=hidden_cat_col, value="维度")
    ws.cell(row=hidden_header_row, column=hidden_val_col, value="构成占比")
    ws.cell(row=hidden_header_row, column=hidden_label_col, value="柱顶标签")
    label_values: list[str] = []
    for i, item in enumerate(top_rows):
        r = hidden_header_row + 1 + i
        dim = str(item.get("dimension") or "")
        share = float(shares[i])
        ws.cell(row=r, column=hidden_cat_col, value=_truncate_label(dim, 14))
        rate_cell = ws.cell(row=r, column=hidden_val_col, value=share)
        rate_cell.number_format = EXCEL_PERCENT_FORMAT
        label = _bar_share_label(share * 100.0)
        ws.cell(row=r, column=hidden_label_col, value=label)
        label_values.append(label)

    data_start = hidden_header_row + 1
    data_end = hidden_header_row + len(top_rows)
    chart_title = display
    anchor = f"{get_column_letter(card_col_start)}{card_row + 1}"
    y_max = max(shares) if shares else 0.0
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

    sheet = OVERVIEW_SHEET_NAME.replace("'", "''")
    label_letter = get_column_letter(hidden_label_col)
    formula = f"'{sheet}'!${label_letter}${data_start}:${label_letter}${data_end}"
    return {
        "type": item_type,
        "title": display,
        "has_chart": True,
        "chart_title": chart_title,
        "label_payload": {"formula": formula, "values": label_values},
        "composition_sum": round(sum(shares), 6),
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
    col_end: int,
    item_type: str,
    summary_rows: list[dict],
    header_fill: PatternFill,
    databar_color: str,
    total_reviews: int = 0,
    show_desc: bool = True,
) -> int:
    display = type_display_label(item_type)
    top_n = _overview_limit_for_type(item_type)
    dim_c = col_start
    bar_c = min(col_start + 2, col_end)
    metric_c = min(col_start + 3, col_end)
    fb_c = min(col_start + 4, col_end)
    fb_end = col_end

    header = ws.cell(row=start_row, column=dim_c, value=display)
    header.font = _CARD_TITLE_FONT
    header.fill = header_fill
    for c in range(dim_c, fb_end + 1):
        ws.cell(row=start_row, column=c).fill = header_fill
    ws.merge_cells(start_row=start_row, start_column=dim_c, end_row=start_row, end_column=fb_end)
    ws.row_dimensions[start_row].height = 22

    data_row = start_row + 1
    if show_desc:
        desc = MODULE_DESCRIPTIONS.get(item_type) or ""
        if desc:
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
            ws.row_dimensions[start_row + 1].height = 22
            data_row = start_row + 2

    top_rows = _top_rows_for_type(
        summary_rows or [],
        item_type,
        top_n,
        min_mentions=OVERVIEW_MIN_MENTIONS,
    )
    if not top_rows:
        r = data_row + 1
        cell = ws.cell(row=r, column=dim_c, value="暂无足够评论证据")
        cell.font = _EMPTY_FONT
        ws.merge_cells(start_row=r, start_column=dim_c, end_row=r, end_column=fb_end)
        return r - start_row + 1

    bar_start_row = data_row
    for i, item in enumerate(top_rows):
        r = data_row + i
        ws.row_dimensions[r].height = 44
        dim = str(item.get("dimension") or "")
        dim_cell = ws.cell(row=r, column=dim_c, value=dim)
        dim_cell.font = _DIM_FONT
        dim_cell.alignment = Alignment(wrap_text=True, vertical="center")
        merge_dim_end = min(dim_c + 1, bar_c - 1) if bar_c > dim_c + 1 else dim_c
        if merge_dim_end > dim_c:
            ws.merge_cells(start_row=r, start_column=dim_c, end_row=r, end_column=merge_dim_end)

        rate = float(item.get("mention_rate") or 0) / 100.0
        bar_cell = ws.cell(row=r, column=bar_c, value=rate)
        bar_cell.number_format = EXCEL_PERCENT_FORMAT
        bar_cell.alignment = Alignment(vertical="center")

        metric = ws.cell(row=r, column=metric_c, value=_rate_count_label(item, total_reviews))
        metric.font = _METRIC_FONT
        metric.alignment = Alignment(horizontal="left", vertical="center")

        fb = item.get("theme_summary") or build_theme_insight_summary(item)
        fb_cell = ws.cell(row=r, column=fb_c, value=fb)
        fb_cell.font = _FEEDBACK_FONT
        fb_cell.alignment = Alignment(wrap_text=True, vertical="center")
        if fb_end > fb_c:
            ws.merge_cells(start_row=r, start_column=fb_c, end_row=r, end_column=fb_end)

        for c in range(dim_c, fb_end + 1):
            ws.cell(row=r, column=c).border = Border(bottom=Side(style="hair", color="E0E0E0"))

    bar_end_row = data_row + len(top_rows) - 1
    col_letter = get_column_letter(bar_c)
    _apply_databar(ws, f"{col_letter}{bar_start_row}:{col_letter}{bar_end_row}", databar_color)
    return (data_row - start_row) + len(top_rows)


def _write_section_banner(ws, *, row: int, title: str, desc: str = "", end_col: int = _LEFT_ZONE_END) -> int:
    """Return next content row after banner (+ optional desc)."""
    cell = ws.cell(row=row, column=1, value=title)
    cell.font = Font(name="Microsoft YaHei", size=11, bold=True, color="1F4E79")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=end_col)
    if not desc:
        return row + 1
    d = ws.cell(row=row + 1, column=1, value=desc)
    d.font = Font(name="Microsoft YaHei", size=8, color="666666")
    d.alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=row + 1, start_column=1, end_row=row + 1, end_column=end_col)
    ws.row_dimensions[row + 1].height = 20
    return row + 2


def _write_ai_summary_column(
    ws,
    *,
    start_row: int,
    end_row: int,
    summary_text: str,
) -> None:
    c1, c2 = _SUMMARY_COL_START, _SUMMARY_COL_END
    thin = Side(style="thin", color="BFBFBF")
    title = ws.cell(row=start_row, column=c1, value="AI总结")
    title.font = _CARD_TITLE_FONT
    title.fill = _SUMMARY_HEADER_FILL
    title.alignment = Alignment(vertical="center")
    for c in range(c1, c2 + 1):
        cell = ws.cell(row=start_row, column=c)
        cell.fill = _SUMMARY_HEADER_FILL
        cell.border = Border(
            left=thin if c == c1 else None,
            right=thin if c == c2 else None,
            top=thin,
            bottom=thin,
        )
    ws.merge_cells(start_row=start_row, start_column=c1, end_row=start_row, end_column=c2)
    ws.row_dimensions[start_row].height = 24

    body_start = start_row + 1
    body_end = max(body_start, end_row)
    text = (summary_text or "").strip() or "（尚未生成 AI 总结）"
    body = ws.cell(row=body_start, column=c1, value=text)
    body.font = Font(name="Microsoft YaHei", size=9, color="303030")
    body.alignment = Alignment(wrap_text=True, vertical="top")
    body.fill = _SUMMARY_FILL
    for r in range(body_start, body_end + 1):
        for c in range(c1, c2 + 1):
            cell = ws.cell(row=r, column=c)
            cell.fill = _SUMMARY_FILL
            cell.border = Border(
                left=thin if c == c1 else None,
                right=thin if c == c2 else None,
                top=thin if r == body_start else None,
                bottom=thin if r == body_end else None,
            )
    ws.merge_cells(start_row=body_start, start_column=c1, end_row=body_end, end_column=c2)


def _build_overview_sheet(
    wb,
    *,
    summary_rows: list[dict],
    total_reviews: int = 0,
    overview_summary: str = "",
    voc_items: int = 0,
    product_name: str = "",
    product_category: str = "",
) -> dict:
    """Left A–N charts/panels; right O–U one-shot AI summary. No product fields on dashboard."""
    del voc_items, product_name, product_category
    if OVERVIEW_SHEET_NAME in wb.sheetnames:
        del wb[OVERVIEW_SHEET_NAME]
    ws = wb.create_sheet(OVERVIEW_SHEET_NAME)
    ws.sheet_view.showGridLines = False

    chart_types = list(OVERVIEW_CHART_TYPES)
    n_chart_rows = (len(chart_types) + 1) // 2
    page_rows = 10 + n_chart_rows * _CARD_ROW_HEIGHT + 120
    for r in range(1, page_rows):
        for c in range(1, 20):
            ws.cell(row=r, column=c).fill = _PAGE_FILL

    ws["A1"] = "Amazon 评论分析总览"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].fill = _PAGE_FILL
    ws.merge_cells("A1:D1")
    ws.row_dimensions[1].height = 28

    count_cell = ws.cell(row=1, column=5, value=f"评论总数：{int(total_reviews or 0)}")
    count_cell.font = Font(name="Microsoft YaHei", size=10, color="404040")
    count_cell.alignment = Alignment(vertical="center")
    ws.merge_cells("E1:M1")

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 11
    ws.column_dimensions["F"].width = 10
    ws.column_dimensions["G"].width = 10
    ws.column_dimensions["H"].width = 2
    for letter in ("I", "J", "K", "L", "M", "N"):
        ws.column_dimensions[letter].width = 11
    for letter in ("O", "P", "Q", "R", "S", "T", "U"):
        ws.column_dimensions[letter].width = 14

    hidden_cols = max(12, len(chart_types) * 3)
    for col_i in range(_HIDDEN_START_COL, _HIDDEN_START_COL + hidden_cols):
        letter = get_column_letter(col_i)
        ws.column_dimensions[letter].hidden = True
        ws.column_dimensions[letter].width = 14

    content_start = 3
    ws.freeze_panes = f"A{content_start}"
    grid_start = content_start

    module_metas: list[dict] = []
    chart_titles: list[str] = []
    label_payloads: list[dict] = []
    for idx, item_type in enumerate(chart_types):
        grid_r = idx // 2
        grid_c = idx % 2
        card_row = grid_start + grid_r * _CARD_ROW_HEIGHT
        c1, c2 = _CHART_LEFT_COLS if grid_c == 0 else _CHART_RIGHT_COLS
        hidden_cat = _HIDDEN_START_COL + idx * 3
        hidden_val = hidden_cat + 1
        hidden_label = hidden_cat + 2
        meta = _write_portrait_module(
            ws,
            card_row=card_row,
            card_col_start=c1,
            card_col_end=c2,
            item_type=item_type,
            summary_rows=summary_rows or [],
            hidden_cat_col=hidden_cat,
            hidden_val_col=hidden_val,
            hidden_label_col=hidden_label,
            hidden_header_row=1,
            total_reviews=total_reviews,
        )
        module_metas.append(meta)
        if meta.get("chart_title"):
            chart_titles.append(meta["chart_title"])
        if meta.get("label_payload"):
            label_payloads.append(meta["label_payload"])

    cursor = grid_start + n_chart_rows * _CARD_ROW_HEIGHT + 1
    cursor = _write_section_banner(
        ws, row=cursor, title="使用地点 / 使用时刻", desc=CONTEXT_SECTION_DESC
    )
    ctx_start = cursor
    left_ctx = _write_feedback_panel(
        ws,
        start_row=ctx_start,
        col_start=_PANEL_LEFT_COLS[0],
        col_end=_PANEL_LEFT_COLS[1],
        item_type="使用地点",
        summary_rows=summary_rows or [],
        header_fill=_PANEL_HEADER_FILL_CTX,
        databar_color=_DATABAR_CTX,
        total_reviews=total_reviews,
        show_desc=True,
    )
    right_ctx = _write_feedback_panel(
        ws,
        start_row=ctx_start,
        col_start=_PANEL_RIGHT_COLS[0],
        col_end=_PANEL_RIGHT_COLS[1],
        item_type="使用时刻",
        summary_rows=summary_rows or [],
        header_fill=_PANEL_HEADER_FILL_CTX,
        databar_color=_DATABAR_CTX,
        total_reviews=total_reviews,
        show_desc=True,
    )
    cursor = ctx_start + max(left_ctx, right_ctx) + 1
    cursor = _write_section_banner(
        ws,
        row=cursor,
        title="需求满足分析（未被满足 / 用户满意）",
        desc=NEED_FULFILLMENT_SECTION_DESC,
    )
    panel_start = cursor
    left_rows = _write_feedback_panel(
        ws,
        start_row=panel_start,
        col_start=_PANEL_LEFT_COLS[0],
        col_end=_PANEL_LEFT_COLS[1],
        item_type="未被满足",
        summary_rows=summary_rows or [],
        header_fill=_PANEL_HEADER_FILL_NEG,
        databar_color=_DATABAR_NEG,
        total_reviews=total_reviews,
        show_desc=True,
    )
    right_rows = _write_feedback_panel(
        ws,
        start_row=panel_start,
        col_start=_PANEL_RIGHT_COLS[0],
        col_end=_PANEL_RIGHT_COLS[1],
        item_type="用户满意",
        summary_rows=summary_rows or [],
        header_fill=_PANEL_HEADER_FILL_POS,
        databar_color=_DATABAR_POS,
        total_reviews=total_reviews,
        show_desc=True,
    )
    left_end = panel_start + max(left_rows, right_rows)
    _write_ai_summary_column(
        ws,
        start_row=1,
        end_row=max(left_end, grid_start + n_chart_rows * _CARD_ROW_HEIGHT),
        summary_text=overview_summary or "",
    )
    return {
        "chart_titles": chart_titles,
        "chart_count": len(chart_titles),
        "module_metas": module_metas,
        "label_payloads": label_payloads,
        "feedback_left_rows": left_rows,
        "feedback_right_rows": right_rows,
        "context_left_rows": left_ctx,
        "context_right_rows": right_ctx,
        "upper_start": grid_start,
        "feedback_start": panel_start,
        "context_start": ctx_start,
        "summary_reserve": f"O1:U{max(left_end, 2)}",
        "has_overview_summary": bool((overview_summary or "").strip()),
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
        ws.cell(row=r, column=4).number_format = EXCEL_PERCENT_FORMAT

    ws.freeze_panes = "A2"
    if ws.max_row >= 1:
        ws.auto_filter.ref = f"A1:E{ws.max_row}"
    for idx, width in enumerate([12, 18, 12, 12, 56], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.row_dimensions[1].height = 22


def _join_lines(values: list | None, *, empty: str = "（暂无）") -> str:
    parts = [str(v).strip() for v in (values or []) if str(v or "").strip()]
    return "\n".join(f"· {p}" for p in parts) if parts else empty


def _build_segment_insight_sheet(
    wb,
    *,
    core_segments: list[dict] | None = None,
    insight_payload: dict | None = None,
) -> dict:
    if SEGMENT_INSIGHT_SHEET_NAME in wb.sheetnames:
        del wb[SEGMENT_INSIGHT_SHEET_NAME]
    ws = wb.create_sheet(SEGMENT_INSIGHT_SHEET_NAME)

    payload = insight_payload if isinstance(insight_payload, dict) else {}
    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    role_by_name = {
        str(s.get("segment") or "").strip(): str(s.get("role") or "").strip()
        for s in segments
        if isinstance(s, dict) and str(s.get("segment") or "").strip()
    }

    for idx, width in enumerate([16, 14, 10, 12, 8], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    row = 1
    h1 = ws.cell(row=row, column=1, value="01 核心消费人群")
    h1.font = _SECTION_FONT
    h1.fill = _SECTION_FILL
    row = 2
    headers = ["人群", "角色", "评论数", "评论覆盖率", "排名"]
    for c, name in enumerate(headers, start=1):
        ws.cell(row=row, column=c, value=name)
    _style_header_row(ws, row, 1, 5)
    row = 3
    core = list(core_segments or [])
    if not core:
        cell = ws.cell(row=row, column=1, value="（未识别到消费人群）")
        cell.font = _EMPTY_FONT
        row += 1
    else:
        for item in core:
            name = str(item.get("segment") or "")
            ws.cell(row=row, column=1, value=name)
            ws.cell(row=row, column=2, value=role_by_name.get(name) or "（待AI判定）")
            ws.cell(row=row, column=3, value=int(item.get("review_count") or 0))
            rate_cell = ws.cell(
                row=row,
                column=4,
                value=float(item.get("coverage_rate") or 0) / 100.0,
            )
            rate_cell.number_format = EXCEL_PERCENT_FORMAT
            ws.cell(row=row, column=5, value=int(item.get("rank") or 0))
            for c in range(1, 6):
                ws.cell(row=row, column=c).font = _BODY_FONT
                ws.cell(row=row, column=c).border = _THIN
            row += 1

    row += 1
    h2 = ws.cell(row=row, column=1, value="02 核心人群画像")
    h2.font = _SECTION_FONT
    h2.fill = _SECTION_FILL
    row += 1
    portrait_headers = ["人群", "评论发现", "AI联网画像", "核心需求", "来源"]
    for c, name in enumerate(portrait_headers, start=1):
        ws.cell(row=row, column=c, value=name)
    _style_header_row(ws, row, 1, 5)
    for idx, width in enumerate([14, 32, 36, 28, 40], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = max(
            ws.column_dimensions[get_column_letter(idx)].width or 10,
            width,
        )
    row += 1

    if not segments:
        cell = ws.cell(row=row, column=1, value="（暂无人群画像）")
        cell.font = _EMPTY_FONT
        row += 1
    else:
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            sources = seg.get("sources") or []
            source_txt = "\n".join(
                f"{s.get('source_title')}: {s.get('finding')}"
                + (f" ({s.get('source_url')})" if s.get("source_url") else "")
                for s in sources
                if isinstance(s, dict)
            ) or "（无外部来源）"
            values = [
                str(seg.get("segment") or ""),
                _join_lines(seg.get("review_findings")),
                _join_lines(seg.get("ai_profile")),
                _join_lines(seg.get("core_needs")),
                source_txt,
            ]
            for c, val in enumerate(values, start=1):
                cell = ws.cell(row=row, column=c, value=val)
                cell.font = _BODY_FONT
                cell.border = _THIN
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[row].height = 80
            row += 1

    row += 1
    h3 = ws.cell(row=row, column=1, value="03 产品开发方向")
    h3.font = _SECTION_FONT
    h3.fill = _SECTION_FILL
    row += 1
    pd = payload.get("product_development") if isinstance(payload.get("product_development"), dict) else {}

    ws.cell(row=row, column=1, value="产品要求").font = _HEADER_FONT
    row += 1
    req_headers = ["产品要求", "对应核心人群", "依据"]
    for c, name in enumerate(req_headers, start=1):
        ws.cell(row=row, column=c, value=name)
    _style_header_row(ws, row, 1, 3)
    row += 1
    requirements = pd.get("requirements") if isinstance(pd.get("requirements"), list) else []
    if not requirements:
        cell = ws.cell(row=row, column=1, value="（暂无产品要求）")
        cell.font = _EMPTY_FONT
        row += 1
    else:
        for req in requirements:
            if not isinstance(req, dict):
                continue
            targets = req.get("target_segments") or []
            values = [
                str(req.get("requirement") or ""),
                " / ".join(str(t) for t in targets),
                str(req.get("basis") or ""),
            ]
            for c, val in enumerate(values, start=1):
                cell = ws.cell(row=row, column=c, value=val)
                cell.font = _BODY_FONT
                cell.border = _THIN
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[row].height = 48
            row += 1

    row += 1
    ws.cell(row=row, column=1, value="产品壁垒").font = _HEADER_FONT
    row += 1
    moat_headers = ["壁垒方向", "为什么值得做成壁垒"]
    for c, name in enumerate(moat_headers, start=1):
        ws.cell(row=row, column=c, value=name)
    _style_header_row(ws, row, 1, 2)
    row += 1
    moats = pd.get("product_moats") if isinstance(pd.get("product_moats"), list) else []
    if not moats:
        cell = ws.cell(row=row, column=1, value="（暂无壁垒方向）")
        cell.font = _EMPTY_FONT
        row += 1
    else:
        for moat in moats:
            if not isinstance(moat, dict):
                continue
            values = [str(moat.get("moat") or ""), str(moat.get("reason") or "")]
            for c, val in enumerate(values, start=1):
                cell = ws.cell(row=row, column=c, value=val)
                cell.font = _BODY_FONT
                cell.border = _THIN
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[row].height = 48
            row += 1

    status = str(payload.get("external_research_status") or "")
    return {
        "sheet": SEGMENT_INSIGHT_SHEET_NAME,
        "core_segment_count": len(core),
        "portrait_count": len(segments),
        "external_research_status": status,
        "modules": ["01 核心消费人群", "02 核心人群画像", "03 产品开发方向"],
        "related_types": list(SEGMENT_RELATED_TYPES),
    }


def write_analysis_workbook(
    source_path: str | Path,
    output_path: str | Path,
    *,
    summary_rows: list[dict],
    product_name: str = "",
    product_category: str = "",
    total_reviews: int = 0,
    voc_items: int | None = None,
    overview_summary: str = "",
    core_segments: list[dict] | None = None,
    segment_insight: dict | None = None,
) -> dict:
    """Keep original sheets; append overview + 消费人群洞察 + result."""
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
        total_reviews=total_reviews,
        overview_summary=overview_summary or "",
        voc_items=int(voc_items or 0),
        product_name=product_name or "",
        product_category=product_category or "",
    )
    seg_meta = _build_segment_insight_sheet(
        wb,
        core_segments=core_segments,
        insight_payload=segment_insight,
    )
    _build_result_sheet(wb, summary_rows)
    _ensure_analysis_sheets_at_end(wb, original_sheet_order)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    sheetnames = list(wb.sheetnames)
    wb.close()
    payloads = overview_meta.get("label_payloads") or []
    if payloads:
        _patch_chart_datalabels_from_cells(Path(output_path), payloads)
    return {
        "sheetnames": sheetnames,
        "chart_titles": overview_meta.get("chart_titles") or [],
        "chart_count": int(overview_meta.get("chart_count") or 0),
        "module_metas": overview_meta.get("module_metas") or [],
        "overview_sheet": OVERVIEW_SHEET_NAME,
        "result_sheet": RESULT_SHEET_NAME,
        "segment_insight_sheet": SEGMENT_INSIGHT_SHEET_NAME,
        "segment_insight_meta": seg_meta,
        "feedback_start": overview_meta.get("feedback_start"),
        "context_start": overview_meta.get("context_start"),
        "summary_reserve": overview_meta.get("summary_reserve"),
        "has_overview_summary": overview_meta.get("has_overview_summary"),
    }
