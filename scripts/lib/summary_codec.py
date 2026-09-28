# -*- coding: utf-8 -*-
"""Build / validate one-shot overview AI summary."""
from __future__ import annotations

from .constants import LABEL_OTHER, VOC_TYPES
from .extract_codec import parse_json_content

_ALLOWED_TITLES = set(VOC_TYPES)


def build_stats_block(summary_rows: list[dict], *, top_n: int = 8) -> str:
    """Plain-text block for the summary user prompt."""
    lines: list[str] = []
    for t in VOC_TYPES:
        rows = [
            r
            for r in (summary_rows or [])
            if (r.get("item_type") or "") == t and str(r.get("dimension") or "") != LABEL_OTHER
        ]
        rows.sort(key=lambda x: (-int(x.get("mention_count") or 0), str(x.get("dimension") or "")))
        rows = rows[: max(1, int(top_n))]
        lines.append(f"## {t}")
        if not rows:
            lines.append("（无统计条目）")
            continue
        for r in rows:
            dim = r.get("dimension") or ""
            cnt = int(r.get("mention_count") or 0)
            rate = float(r.get("mention_rate") or 0)
            fb = (r.get("representative_feedback") or r.get("core_description") or "").strip()
            if len(fb) > 120:
                fb = fb[:117] + "…"
            lines.append(f"- {dim}：{rate:.1f}%（{cnt}）｜{fb}")
        lines.append("")
    return "\n".join(lines).strip()


def format_section_cell_text(title: str, bullets: list | None) -> str:
    """One copyable module cell for the AI总结 sheet."""
    t = str(title or "").strip()
    lines: list[str] = [f"{t}总结"]
    if not isinstance(bullets, list) or not bullets:
        lines.append("· 证据不足，从略")
        return "\n".join(lines)
    for b in bullets:
        text = str(b or "").strip()
        if text:
            lines.append(f"· {text}")
    if len(lines) == 1:
        lines.append("· 证据不足，从略")
    return "\n".join(lines)


def format_summary_sections(payload: dict) -> list[dict]:
    """Ordered [{title, cell_text}] for AI总结 sheet (八维)."""
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list):
        return []
    by_title: dict[str, list] = {}
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "").strip()
        if title not in _ALLOWED_TITLES:
            continue
        by_title[title] = sec.get("bullets") or []
    out: list[dict] = []
    for t in VOC_TYPES:
        bullets = by_title.get(t)
        out.append(
            {
                "title": t,
                "cell_text": format_section_cell_text(t, bullets if bullets is not None else []),
            }
        )
    return out


def format_summary_text(payload: dict) -> str:
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list):
        return ""
    chunks: list[str] = ["AI总结（全量）", ""]
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "").strip()
        bullets = sec.get("bullets") or []
        if not title:
            continue
        chunks.append(f"【{title}】")
        if not isinstance(bullets, list) or not bullets:
            chunks.append("· 证据不足，从略")
        else:
            for b in bullets:
                text = str(b or "").strip()
                if text:
                    chunks.append(f"· {text}")
        chunks.append("")
    return "\n".join(chunks).strip()


def validate_summary_payload(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return "总结输出必须是对象"
    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        return "sections 必须为非空数组"
    seen: set[str] = set()
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            return f"sections[{i}] 必须是对象"
        title = str(sec.get("title") or "").strip()
        if title not in _ALLOWED_TITLES:
            return f"sections[{i}].title 非法：{title}"
        if title in seen:
            return f"重复维：{title}"
        seen.add(title)
        bullets = sec.get("bullets")
        if not isinstance(bullets, list):
            return f"sections[{i}].bullets 必须是数组"
        for j, b in enumerate(bullets):
            if not isinstance(b, str) or not b.strip():
                return f"sections[{i}].bullets[{j}] 必须是非空字符串"
    missing = [t for t in VOC_TYPES if t not in seen]
    if missing:
        return f"缺少维：{'、'.join(missing)}"
    return None


def parse_summary_output(raw_text: str) -> tuple[str | None, str | None]:
    """
    Returns (summary_text, error).
    """
    payload, err = parse_summary_payload(raw_text)
    if err:
        return None, err
    return format_summary_text(payload or {}), None


def parse_summary_payload(raw_text: str) -> tuple[dict | None, str | None]:
    """Returns (validated payload, error)."""
    text = (raw_text or "").strip()
    if not text or text.startswith("/*"):
        return None, "总结模型输出尚未填写"
    payload = parse_json_content(text)
    if payload is None:
        return None, "无法解析总结 JSON"
    err = validate_summary_payload(payload)
    if err:
        return None, err
    return payload, None
