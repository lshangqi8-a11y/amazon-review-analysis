# -*- coding: utf-8 -*-
"""Python-side statistics + representative feedback."""
from __future__ import annotations

from collections import defaultdict

from .constants import REPRESENTATIVE_FEEDBACK_LIMIT, VOC_TYPES

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


def aggregate_statistics(items: list[dict], total_reviews: int) -> list[dict]:
    """
    Output order for reviewability:
    消费人群 → 产品用途 → 使用场景 → 购买动机 → 用户满意 → 用户不满
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
        rows.append(
            {
                "item_type": t,
                "dimension": d,
                "mention_count": count,
                "mention_rate": round(count * 100.0 / total, 2),
                "core_description": feedback,
                "representative_feedback": feedback,
            }
        )
    rows.sort(
        key=lambda x: (
            _TYPE_ORDER.get(x["item_type"], 999),
            -int(x["mention_count"]),
            x["dimension"] or "",
        )
    )
    return rows
