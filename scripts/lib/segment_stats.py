# -*- coding: utf-8 -*-
"""
Consumer-segment deep analysis (Python-side, category-agnostic).

Segments = normalized 「消费人群」 standard dimensions (no fixed dictionaries).
All rates use unique review_row counts. No Fisher / χ² / sample gates.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from .constants import LABEL_OTHER

SEGMENT_TYPE = "消费人群"
ASSOC_TYPES = ["产品用途", "使用场景", "购买动机", "用户满意", "未被满足"]

MAX_SEGMENTS = 8
MAX_ASSOC_PER_TYPE = 5
MAX_COMPARE_SEGMENTS = 4
MAX_COMPARISONS = 12


def _review_sets_by_dim(items: list[dict], item_type: str) -> dict[str, set[int]]:
    out: dict[str, set[int]] = defaultdict(set)
    for it in items or []:
        if (it.get("item_type") or "").strip() != item_type:
            continue
        d = (it.get("merged_dimension") or it.get("dimension") or "").strip()
        if not d or d == LABEL_OTHER:
            continue
        rid = int(it.get("review_row") or 0)
        if rid:
            out[d].add(rid)
    return dict(out)


def discover_segments(
    items: list[dict],
    analyzed_reviews: int,
    *,
    max_segments: int = MAX_SEGMENTS,
) -> list[dict]:
    """Discover segments from normalized 消费人群 dims (n >= 1)."""
    by_dim = _review_sets_by_dim(items, SEGMENT_TYPE)
    denom = max(1, int(analyzed_reviews or 1))
    rows = []
    for seg, rset in by_dim.items():
        n = len(rset)
        if n < 1:
            continue
        rows.append(
            {
                "segment": seg,
                "mention_count": n,
                "mention_rate": round(n * 100.0 / denom, 2),
                "review_rows": sorted(rset),
            }
        )
    rows.sort(key=lambda x: (-float(x["mention_rate"]), -int(x["mention_count"]), x["segment"]))
    return rows[: max(1, int(max_segments))]


def _within_rate(hit: int, segment_n: int) -> float:
    if segment_n <= 0:
        return 0.0
    return round(hit * 100.0 / segment_n, 2)


def segment_associations(
    items: list[dict],
    segment_reviews: set[int],
    *,
    top_n: int = MAX_ASSOC_PER_TYPE,
    attribute_specs: list[dict] | None = None,
) -> dict:
    """
    Within-segment associations. Rate = unique reviews in segment ∩ dim / |segment|.
    """
    seg_set = set(segment_reviews or [])
    n = len(seg_set)
    result: dict[str, list[dict]] = {}
    for t in ASSOC_TYPES:
        by_dim = _review_sets_by_dim(items, t)
        rows = []
        for dim, rset in by_dim.items():
            hit = len(rset & seg_set)
            if hit <= 0:
                continue
            rows.append(
                {
                    "dimension": dim,
                    "mention_count": hit,
                    "mention_rate": _within_rate(hit, n),
                }
            )
        rows.sort(key=lambda x: (-float(x["mention_rate"]), -int(x["mention_count"]), x["dimension"]))
        result[t] = rows[: max(1, int(top_n))]

    attr_rows = []
    for spec in attribute_specs or []:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("attribute") or "").strip()
        if not name:
            continue
        dims = set()
        for d in list(spec.get("positive_dimensions") or []) + list(spec.get("negative_dimensions") or []):
            ds = str(d or "").strip()
            if ds:
                dims.add(ds)
        if not dims:
            continue
        hit_rows: set[int] = set()
        for it in items or []:
            t = (it.get("item_type") or "").strip()
            if t not in {"用户满意", "未被满足"}:
                continue
            d = (it.get("merged_dimension") or it.get("dimension") or "").strip()
            if d not in dims:
                continue
            rid = int(it.get("review_row") or 0)
            if rid in seg_set:
                hit_rows.add(rid)
        hit = len(hit_rows)
        if hit <= 0:
            continue
        attr_rows.append(
            {
                "dimension": name,
                "mention_count": hit,
                "mention_rate": _within_rate(hit, n),
                "source_dimensions": sorted(dims),
            }
        )
    attr_rows.sort(key=lambda x: (-float(x["mention_rate"]), x["dimension"]))
    result["产品属性"] = attr_rows[: max(1, int(top_n))]
    return result


def compare_metric(
    *,
    segment_a: str,
    segment_b: str,
    metric_type: str,
    dimension: str,
    reviews_a: set[int],
    reviews_b: set[int],
    hit_reviews: set[int],
) -> dict:
    """A vs B rates + percentage-point difference only."""
    na, nb = len(reviews_a), len(reviews_b)
    ha = len(reviews_a & hit_reviews)
    hb = len(reviews_b & hit_reviews)
    rate_a = _within_rate(ha, na)
    rate_b = _within_rate(hb, nb)
    return {
        "segment_a": segment_a,
        "segment_b": segment_b,
        "metric_type": metric_type,
        "dimension": dimension,
        "rate_a": rate_a,
        "rate_b": rate_b,
        "pp_diff": round(rate_a - rate_b, 2),
        "n_a": na,
        "n_b": nb,
        "hit_a": ha,
        "hit_b": hb,
    }


def build_comparisons(
    items: list[dict],
    segments: list[dict],
    *,
    max_compare_segments: int = MAX_COMPARE_SEGMENTS,
    max_comparisons: int = MAX_COMPARISONS,
    attribute_specs: list[dict] | None = None,
) -> list[dict]:
    """Pairwise comparisons among top segments."""
    top = sorted(
        segments,
        key=lambda x: (-int(x["mention_count"]), x["segment"]),
    )[: max(0, int(max_compare_segments))]
    if len(top) < 2:
        return []

    seg_sets = {s["segment"]: set(s.get("review_rows") or []) for s in top}
    metric_hits: dict[tuple[str, str], set[int]] = {}
    for t in ASSOC_TYPES:
        for dim, rset in _review_sets_by_dim(items, t).items():
            metric_hits[(t, dim)] = rset
    for spec in attribute_specs or []:
        name = str(spec.get("attribute") or "").strip()
        if not name:
            continue
        dims = {
            str(d).strip()
            for d in list(spec.get("positive_dimensions") or []) + list(spec.get("negative_dimensions") or [])
            if str(d).strip()
        }
        hit: set[int] = set()
        for it in items or []:
            if (it.get("item_type") or "").strip() not in {"用户满意", "未被满足"}:
                continue
            d = (it.get("merged_dimension") or it.get("dimension") or "").strip()
            if d in dims:
                rid = int(it.get("review_row") or 0)
                if rid:
                    hit.add(rid)
        if hit:
            metric_hits[("产品属性", name)] = hit

    comps: list[dict] = []
    for sa, sb in combinations([s["segment"] for s in top], 2):
        for (mtype, dim), hits in metric_hits.items():
            if not (hits & seg_sets[sa]) and not (hits & seg_sets[sb]):
                continue
            row = compare_metric(
                segment_a=sa,
                segment_b=sb,
                metric_type=mtype,
                dimension=dim,
                reviews_a=seg_sets[sa],
                reviews_b=seg_sets[sb],
                hit_reviews=hits,
            )
            if abs(row["pp_diff"]) < 1.0 and row["hit_a"] + row["hit_b"] < 2:
                continue
            comps.append(row)

    comps.sort(
        key=lambda x: (
            -abs(float(x["pp_diff"])),
            x["segment_a"],
            x["segment_b"],
            x["metric_type"],
            x["dimension"],
        )
    )
    return comps[: max(1, int(max_comparisons))]


def segment_dim_cooccur(
    items: list[dict],
    segment: str,
    dimension: str,
) -> int:
    """
    Count unique review_rows that hit both the segment (消费人群) and the dimension
    (any VOC type except must match merged/raw dim name).
    """
    seg = (segment or "").strip()
    dim = (dimension or "").strip()
    if not seg or not dim:
        return 0
    seg_rows = _review_sets_by_dim(items, SEGMENT_TYPE).get(seg) or set()
    if not seg_rows:
        return 0
    # Gather all review rows for this dimension across types
    dim_rows: set[int] = set()
    for it in items or []:
        d = (it.get("merged_dimension") or it.get("dimension") or "").strip()
        if d != dim:
            continue
        rid = int(it.get("review_row") or 0)
        if rid:
            dim_rows.add(rid)
    return len(seg_rows & dim_rows)


def build_segment_analysis(
    items: list[dict],
    analyzed_reviews: int,
    *,
    attribute_specs: list[dict] | None = None,
) -> dict:
    """Full Python segment package for Step6 prompt + Step7 Excel."""
    segments = discover_segments(items, analyzed_reviews)
    detailed = []
    for s in segments:
        assoc = segment_associations(
            items,
            set(s.get("review_rows") or []),
            attribute_specs=attribute_specs,
        )
        detailed.append(
            {
                "segment": s["segment"],
                "mention_count": s["mention_count"],
                "mention_rate": s["mention_rate"],
                "associations": assoc,
            }
        )
    comparisons = build_comparisons(
        items,
        segments,
        attribute_specs=attribute_specs,
    )
    return {
        "analyzed_reviews": int(analyzed_reviews or 0),
        "segments": detailed,
        "comparisons": comparisons,
        "known_segments": [s["segment"] for s in detailed],
        "rules": {
            "min_n": 1,
            "denominator": "analyzed_reviews for segment share; within-segment n for association rates",
            "dedup": "unique review_row",
            "category_lexicon": False,
            "statistics": "pp difference only; no Fisher/chi2/p-value",
        },
    }


def build_segment_block(analysis: dict, *, top_assoc: int = 3) -> str:
    """Plain-text block for Intelligence user prompt."""
    lines = ["## 消费人群深度分析（Python 统计，禁止改算）", ""]
    segs = analysis.get("segments") or []
    if not segs:
        lines.append("（无消费人群维度，跳过人群深度分析）")
        return "\n".join(lines)

    lines.append("### 人群概览")
    for s in segs:
        lines.append(
            f"- {s['segment']}：n={s['mention_count']}｜"
            f"占有效评论 {float(s['mention_rate']):.1f}%"
        )
    lines.append("")

    lines.append("### 人群关联（组内提及率，分母=该人群评论数 n）")
    for s in segs:
        lines.append(f"#### {s['segment']}（n={s['mention_count']}）")
        assoc = s.get("associations") or {}
        for t in ASSOC_TYPES + ["产品属性"]:
            rows = (assoc.get(t) or [])[:top_assoc]
            if not rows:
                continue
            parts = [f"{r['dimension']} {float(r['mention_rate']):.1f}%" for r in rows]
            lines.append(f"- {t}：{'；'.join(parts)}")
        lines.append("")

    comps = analysis.get("comparisons") or []
    lines.append("### 人群差异（百分点差异，无显著性检验）")
    if not comps:
        lines.append("（无可比较人群对）")
    else:
        for c in comps:
            lines.append(
                f"- [{c['metric_type']}/{c['dimension']}] "
                f"{c['segment_a']} {float(c['rate_a']):.1f}% vs "
                f"{c['segment_b']} {float(c['rate_b']):.1f}%｜"
                f"Δ={float(c['pp_diff']):+.1f}pp｜"
                f"n={c['n_a']}/{c['n_b']}"
            )
    lines.append("")
    lines.append(
        "规则：n≥1 即可分析；Excel 展示 n，由使用者自行判断样本量；"
        "产品机会的 review_evidence 必须与该人群共现于同一评论；"
        "外部研究不可改写上述内部数字。"
    )
    return "\n".join(lines).strip()
