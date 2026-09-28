# -*- coding: utf-8 -*-
"""Python-side consumer segment stats for V6 (no AI math)."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from .constants import (
    LABEL_OTHER,
    SEGMENT_COMBO_TOP_N,
    SEGMENT_RELATED_TOP_N,
    SEGMENT_RELATED_TYPES,
    SEGMENT_TOP_N,
    SEGMENT_TYPE,
)
from .statistics import pick_representative_feedback


def _dim(item: dict) -> str:
    return (item.get("merged_dimension") or item.get("dimension") or "").strip()


def _type(item: dict) -> str:
    return (item.get("item_type") or "").strip()


def _rid(item: dict) -> int:
    return int(item.get("review_row") or 0)


def analyzed_review_count(meta: dict | None, *, fallback_total: int = 0) -> int:
    """Prefer ai_reviews (reviews sent to AI); else total_reviews."""
    meta = meta or {}
    for key in ("analyzed_reviews", "ai_reviews", "total_reviews"):
        val = meta.get(key)
        if val is not None and int(val) > 0:
            return int(val)
    return max(0, int(fallback_total or 0))


def build_core_segments(
    items: list[dict],
    analyzed_reviews: int,
    *,
    top_n: int = SEGMENT_TOP_N,
) -> list[dict]:
    """
    Top-N 消费人群 by unique-review coverage.
    coverage_rate is a percentage number (e.g. 19.4), not a fraction.
    """
    by_seg: dict[str, set[int]] = defaultdict(set)
    items_by_seg: dict[str, list[dict]] = defaultdict(list)
    for it in items or []:
        if _type(it) != SEGMENT_TYPE:
            continue
        dim = _dim(it)
        if not dim or dim == LABEL_OTHER:
            continue
        rid = _rid(it)
        if rid <= 0:
            continue
        by_seg[dim].add(rid)
        items_by_seg[dim].append(it)

    total = max(1, int(analyzed_reviews or 1))
    rows: list[dict] = []
    for seg, rids in by_seg.items():
        count = len(rids)
        if count <= 0:
            continue
        rows.append(
            {
                "segment": seg,
                "review_count": count,
                "coverage_rate": round(count * 100.0 / total, 2),
                "review_rows": sorted(rids),
                "representative_feedback": pick_representative_feedback(items_by_seg[seg]),
            }
        )
    rows.sort(key=lambda x: (-int(x["review_count"]), x["segment"]))
    limit = max(0, int(top_n or 0))
    if limit > 0:
        rows = rows[:limit]
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


def build_segment_combinations(
    items: list[dict],
    core_segments: list[dict],
    *,
    top_n: int = SEGMENT_COMBO_TOP_N,
) -> dict[str, list[str]]:
    """
    For each core segment, high-frequency co-occurring 消费人群 tags
    that truly appear in the same review_row. Labels like \"幼犬 + 小型犬\".
    """
    core_names = [str(s.get("segment") or "") for s in (core_segments or []) if s.get("segment")]
    if not core_names:
        return {}

    # review_row -> set of 消费人群 dims
    by_review: dict[int, set[str]] = defaultdict(set)
    for it in items or []:
        if _type(it) != SEGMENT_TYPE:
            continue
        dim = _dim(it)
        if not dim or dim == LABEL_OTHER:
            continue
        rid = _rid(it)
        if rid <= 0:
            continue
        by_review[rid].add(dim)

    # pair counts (unordered)
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for dims in by_review.values():
        if len(dims) < 2:
            continue
        for a, b in combinations(sorted(dims), 2):
            pair_counts[(a, b)] += 1

    out: dict[str, list[str]] = {name: [] for name in core_names}
    for name in core_names:
        scored: list[tuple[int, str]] = []
        for (a, b), cnt in pair_counts.items():
            if name not in (a, b) or cnt <= 0:
                continue
            other = b if a == name else a
            label = f"{name} + {other}"
            scored.append((cnt, label))
        scored.sort(key=lambda x: (-x[0], x[1]))
        out[name] = [lab for _, lab in scored[: max(0, int(top_n or 0))]]
    return out


def build_segment_related_dims(
    items: list[dict],
    core_segments: list[dict],
    *,
    related_types: list[str] | None = None,
    top_n: int = SEGMENT_RELATED_TOP_N,
) -> dict[str, dict[str, list[dict]]]:
    """
    For each core segment, related standard dims that co-occur in the same review.
    Returns: segment -> type -> [{dimension, mention_count, representative_feedback}]
    """
    types = list(related_types or SEGMENT_RELATED_TYPES)
    core_names = [str(s.get("segment") or "") for s in (core_segments or []) if s.get("segment")]
    if not core_names:
        return {}

    seg_reviews: dict[str, set[int]] = {
        str(s["segment"]): set(s.get("review_rows") or []) for s in (core_segments or [])
    }

    # type+dim -> review set (global)
    type_dim_reviews: dict[tuple[str, str], set[int]] = defaultdict(set)
    type_dim_items: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for it in items or []:
        t = _type(it)
        if t not in types:
            continue
        dim = _dim(it)
        if not dim or dim == LABEL_OTHER:
            continue
        rid = _rid(it)
        if rid <= 0:
            continue
        type_dim_reviews[(t, dim)].add(rid)
        type_dim_items[(t, dim)].append(it)

    result: dict[str, dict[str, list[dict]]] = {}
    for name in core_names:
        rids = seg_reviews.get(name) or set()
        per_type: dict[str, list[dict]] = {t: [] for t in types}
        for t in types:
            scored: list[dict] = []
            for (tt, dim), reviews in type_dim_reviews.items():
                if tt != t:
                    continue
                overlap = reviews & rids
                if not overlap:
                    continue
                # evidence items only from overlapping reviews
                ev_items = [it for it in type_dim_items[(t, dim)] if _rid(it) in overlap]
                scored.append(
                    {
                        "dimension": dim,
                        "mention_count": len(overlap),
                        "representative_feedback": pick_representative_feedback(ev_items),
                    }
                )
            scored.sort(key=lambda x: (-int(x["mention_count"]), x["dimension"]))
            per_type[t] = scored[: max(0, int(top_n or 0))]
        result[name] = per_type
    return result


def build_segment_stats_payload(
    items: list[dict],
    analyzed_reviews: int,
    *,
    top_n: int = SEGMENT_TOP_N,
) -> dict:
    """Full Python input package for the segment-insight AI prompt."""
    core = build_core_segments(items, analyzed_reviews, top_n=top_n)
    combos = build_segment_combinations(items, core)
    related = build_segment_related_dims(items, core)
    for row in core:
        name = row["segment"]
        row["combination_personas"] = combos.get(name) or []
        row["related_dimensions"] = related.get(name) or {}
    return {
        "analyzed_reviews": int(analyzed_reviews or 0),
        "core_segments": core,
        "segment_count": len(core),
    }


def format_segment_stats_block(payload: dict) -> str:
    """Plain-text block for the segment insight user prompt."""
    lines: list[str] = []
    analyzed = int(payload.get("analyzed_reviews") or 0)
    lines.append(f"有效分析评论数（analyzed_reviews）：{analyzed}")
    lines.append("说明：评论覆盖率 = 该人群 unique review / analyzed_reviews；非市场购买占比。")
    lines.append("")
    core = payload.get("core_segments") or []
    if not core:
        lines.append("（未识别到消费人群；可不做外部研究，segments 置空）")
        return "\n".join(lines)

    lines.append("## 01 核心购买人群（Python 已算好，禁止改数字）")
    for row in core:
        combos = row.get("combination_personas") or []
        combo_txt = "；".join(combos) if combos else "（无共现组合）"
        lines.append(
            f"- 排名{row.get('rank')}｜{row.get('segment')}｜"
            f"评论数={row.get('review_count')}｜"
            f"覆盖率={float(row.get('coverage_rate') or 0):.1f}%｜"
            f"高频组合={combo_txt}"
        )
    lines.append("")
    lines.append("## 每人关联的 Review 标准维度（同评共现，仅可引用下列维度）")
    for row in core:
        name = row.get("segment")
        lines.append(f"### {name}")
        fb = (row.get("representative_feedback") or "").strip()
        if fb:
            lines.append(f"代表反馈：{fb[:200]}")
        related = row.get("related_dimensions") or {}
        for t in SEGMENT_RELATED_TYPES:
            dims = related.get(t) or []
            if not dims:
                lines.append(f"- {t}：（无共现）")
                continue
            parts = [
                f"{d.get('dimension')}（{int(d.get('mention_count') or 0)}）"
                for d in dims
            ]
            lines.append(f"- {t}：{'、'.join(parts)}")
        lines.append("")
    return "\n".join(lines).strip()
