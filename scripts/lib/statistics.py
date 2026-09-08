# -*- coding: utf-8 -*-
"""Python-side statistics + representative feedback + overview copy helpers."""
from __future__ import annotations

from collections import defaultdict

from .constants import (
    OVERVIEW_MIN_MENTIONS,
    REPRESENTATIVE_FEEDBACK_LIMIT,
    VOC_TYPES,
)

_TYPE_ORDER = {name: idx for idx, name in enumerate(VOC_TYPES)}


def pick_representative_feedback(items: list[dict], *, max_n: int = REPRESENTATIVE_FEEDBACK_LIMIT) -> str:
    texts: list[str] = []
    seen_rids: set[int] = set()
    seen_texts: set[str] = set()
    for it in sorted(items, key=lambda x: int(x.get("review_row") or 0)):
        rid = int(it.get("review_row") or 0)
        text = (it.get("extracted_summary") or "").strip()
        if not text or rid in seen_rids or text in seen_texts:
            continue
        seen_rids.add(rid)
        seen_texts.add(text)
        texts.append(text)
        if len(texts) >= max_n:
            break
    return "；".join(texts)


def split_feedback_snippets(text: str) -> list[str]:
    t = str(text or "").strip()
    if not t:
        return []
    for sep in ("；", ";"):
        if sep in t:
            return [p.strip() for p in t.split(sep) if p.strip()]
    return [t]


def build_theme_insight_summary(item: dict) -> str:
    """
    Short theme blurb for overview panels (deterministic, no extra AI call).
    Result sheet still keeps full joined representative_feedback (up to 5).
    """
    dim = str(item.get("dimension") or "").strip()
    snippets = split_feedback_snippets(
        item.get("representative_feedback") or item.get("core_description") or ""
    )
    count = int(item.get("mention_count") or 0)
    rate = float(item.get("mention_rate") or 0)
    head = f"「{dim}」出现在 {count} 条评论中（{rate:.2f}%）"
    if not snippets:
        return head + "。"
    if len(snippets) == 1:
        return f"{head}。买家反馈：{snippets[0]}"
    return f"{head}。买家反馈：{snippets[0]}；亦有评论提到：{snippets[1]}"


def filter_main_dimensions(
    summary_rows: list[dict],
    *,
    min_mentions: int = OVERVIEW_MIN_MENTIONS,
) -> list[dict]:
    # 0 = keep all rows that have any positive mention count
    threshold = max(1, int(min_mentions)) if int(min_mentions or 0) > 0 else 1
    return [r for r in (summary_rows or []) if int(r.get("mention_count") or 0) >= threshold]


def build_overview_conclusion(
    summary_rows: list[dict],
    *,
    total_reviews: int = 0,
    min_mentions: int = OVERVIEW_MIN_MENTIONS,
) -> str:
    """Deterministic one-page conclusion from overview dimensions."""
    main = filter_main_dimensions(summary_rows, min_mentions=min_mentions)
    total = max(0, int(total_reviews or 0))
    thr = int(min_mentions or 0)
    if thr > 1:
        head = f"基于 {total} 条评论的评论洞察结论（总览仅展示提及≥{thr} 的维度）："
    else:
        head = f"基于 {total} 条评论的评论洞察结论："
    lines = [head]

    def tops(item_type: str, n: int = 3) -> list[dict]:
        rows = [r for r in main if (r.get("item_type") or "") == item_type]
        rows.sort(key=lambda x: (-int(x.get("mention_count") or 0), str(x.get("dimension") or "")))
        return rows[:n]

    def fmt(rows: list[dict]) -> str:
        if not rows:
            return "暂无足够主维度证据"
        return "、".join(
            f"{r.get('dimension')}（{float(r.get('mention_rate') or 0):.1f}%）" for r in rows
        )

    lines.append("【消费者画像】谁、在哪、何时、做什么、什么场合、为何买")
    lines.append(f"• 消费人群：{fmt(tops('消费人群'))}")
    lines.append(f"• 使用地点：{fmt(tops('使用地点'))}")
    lines.append(f"• 使用时刻：{fmt(tops('使用时刻'))}")
    lines.append(f"• 产品用途：{fmt(tops('产品用途'))}")
    lines.append(f"• 使用场景：{fmt(tops('使用场景'))}")
    lines.append(f"• 购买动机：{fmt(tops('购买动机'))}")
    lines.append("【需求满足】满意点与未被满足点")
    lines.append(f"• 主要满意：{fmt(tops('用户满意', 5))}")
    lines.append(f"• 主要未被满足：{fmt(tops('未被满足', 5))}")
    return "\n".join(lines)


def aggregate_statistics(items: list[dict], total_reviews: int) -> list[dict]:
    """
    Output order follows VOC_TYPES (8 dims).
    within each type: mention_count desc, then dimension name.
    """
    pairs = defaultdict(set)
    items_by_std: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for it in items:
        t = (it.get("item_type") or "").strip()
        d = (it.get("merged_dimension") or it.get("dimension") or "").strip()
        if not t or not d:
            continue
        rid = int(it.get("review_row") or 0)
        pairs[(t, d)].add(rid)
        items_by_std[(t, d)].append(it)

    total = max(1, int(total_reviews or 1))
    rows = []
    for (t, d), review_set in pairs.items():
        count = len(review_set)
        if count <= 0:
            continue
        feedback = pick_representative_feedback(items_by_std.get((t, d), []))
        item = {
            "item_type": t,
            "dimension": d,
            "mention_count": count,
            "mention_rate": round(count * 100.0 / total, 2),
            "core_description": feedback,
            "representative_feedback": feedback,
        }
        item["theme_summary"] = build_theme_insight_summary(item)
        thr = int(OVERVIEW_MIN_MENTIONS or 0)
        item["is_main_dimension"] = count >= (thr if thr > 0 else 1)
        rows.append(item)
    rows.sort(
        key=lambda x: (
            _TYPE_ORDER.get(x["item_type"], 999),
            -int(x["mention_count"]),
            x["dimension"] or "",
        )
    )
    return rows
