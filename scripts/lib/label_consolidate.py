# -*- coding: utf-8 -*-
"""
Optional heuristic fallback only.

Primary merge path is AI normalize (step4/5). Keep this module tiny and
product-agnostic — no category-specific synonym tables.
"""
from __future__ import annotations

from collections import defaultdict

from .constants import LABEL_KEEP_TOP, LABEL_MIN_MENTIONS, LABEL_MIN_RATE, LABEL_OTHER, VOC_TYPES


def consolidate_extract_items(
    items: list[dict],
    *,
    total_reviews: int,
    min_mentions: int | None = None,
    min_rate: float | None = None,
    keep_top: int | None = None,
    other_label: str | None = None,
) -> list[dict]:
    """
    Light long-tail bucket only (no synonym dictionary).
    Prefer AI normalize; call with consolidate=True only as emergency fallback.
    """
    if not items:
        return []
    min_mentions = LABEL_MIN_MENTIONS if min_mentions is None else int(min_mentions)
    min_rate = LABEL_MIN_RATE if min_rate is None else float(min_rate)
    keep_top = LABEL_KEEP_TOP if keep_top is None else int(keep_top)
    other_label = LABEL_OTHER if other_label is None else str(other_label)

    out: list[dict] = []
    for it in items:
        row = dict(it)
        d = str(row.get("merged_dimension") or row.get("dimension") or "").strip()
        row["merged_dimension"] = d
        out.append(row)

    pairs: dict[tuple[str, str], set[int]] = defaultdict(set)
    for it in out:
        t = str(it.get("item_type") or "").strip()
        d = str(it.get("merged_dimension") or "").strip()
        if not t or not d or d == other_label:
            continue
        pairs[(t, d)].add(int(it.get("review_row") or 0))

    total = max(1, int(total_reviews or 1))
    thr_count = max(1, int(min_mentions))
    thr_rate = max(0.0, float(min_rate))
    drop: set[tuple[str, str]] = set()

    for t in VOC_TYPES:
        rows = [
            (d, len(rids), len(rids) * 100.0 / total)
            for (tt, d), rids in pairs.items()
            if tt == t
        ]
        rows.sort(key=lambda x: (-x[1], x[0]))
        keep_names: set[str] = set()
        for d, c, rate in rows:
            if c >= thr_count or rate >= thr_rate:
                keep_names.add(d)
        if len(keep_names) < max(1, int(keep_top)):
            for d, c, _rate in rows:
                if len(keep_names) >= max(1, int(keep_top)):
                    break
                if c >= 2:
                    keep_names.add(d)
        if not keep_names and rows:
            keep_names.add(rows[0][0])
        for d, _c, _rate in rows:
            if d not in keep_names:
                drop.add((t, d))

    if drop and other_label:
        for row in out:
            t = str(row.get("item_type") or "").strip()
            d = str(row.get("merged_dimension") or "").strip()
            if (t, d) in drop:
                row["merged_dimension"] = other_label
                row["long_tail_bucketed"] = True
    return out
