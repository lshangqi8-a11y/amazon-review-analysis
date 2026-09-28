# -*- coding: utf-8 -*-
"""
Consumer-segment deep analysis (Python-side, category-agnostic).

Segments = normalized 「消费人群」 standard dimensions (no fixed dictionaries).
All rates use unique review_row counts.
"""
from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

from .constants import LABEL_OTHER
from .statistics import mention_rate

SEGMENT_TYPE = "消费人群"
ASSOC_TYPES = ["产品用途", "使用场景", "购买动机", "用户满意", "未被满足"]

# Sample protection
MIN_DISPLAY_N = 1
MIN_DIRECTIONAL_N = 10
# Cap segments / associations for prompt & Excel reviewability
MAX_SEGMENTS = 8
MAX_ASSOC_PER_TYPE = 5
MAX_COMPARE_SEGMENTS = 4
MAX_COMPARISONS = 12
LARGE_PP_THRESHOLD = 10.0  # percentage points — surface even if p>0.05


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
    """
    Discover segments from normalized 消费人群 dimensions.
    No category lexicon — whatever dims AI normalize produced.
    """
    by_dim = _review_sets_by_dim(items, SEGMENT_TYPE)
    denom = max(1, int(analyzed_reviews or 1))
    rows = []
    for seg, rset in by_dim.items():
        n = len(rset)
        if n < MIN_DISPLAY_N:
            continue
        rows.append(
            {
                "segment": seg,
                "mention_count": n,
                "mention_rate": round(n * 100.0 / denom, 2),
                "sample_status": "样本不足" if n < MIN_DIRECTIONAL_N else "可比较",
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
    For one segment, associate 用途/场景/动机/满意/未满足 (+ optional 产品属性).
    Rates = unique reviews in segment that also hit the dim / |segment|.
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

    # Product attributes: union of mapped pos/neg dims (optional, after AI mapping)
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


# ---- statistical tests (pure Python, no scipy) ----

def _log_factorial(n: int) -> float:
    if n < 0:
        raise ValueError("n must be >= 0")
    return sum(math.log(i) for i in range(2, n + 1))


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> dict:
    """
    Two-sided Fisher's exact test for 2x2 table:
        | a | b |
        | c | d |
    Returns p_value, odds_ratio, method.
    """
    a, b, c, d = int(a), int(b), int(c), int(d)
    if min(a, b, c, d) < 0:
        raise ValueError("counts must be non-negative")
    # Odds ratio (Haldane-Anscombe if zero cell)
    if a * d == 0 or b * c == 0:
        aa, bb, cc, dd = a + 0.5, b + 0.5, c + 0.5, d + 0.5
        odds = (aa * dd) / (bb * cc)
    else:
        odds = (a * d) / (b * c)

    n = a + b + c + d
    if n == 0:
        return {"method": "fisher", "p_value": 1.0, "odds_ratio": None, "applicable": False}

    r1 = a + b
    c1 = a + c
    # Hypergeometric support
    lo = max(0, r1 + c1 - n)
    hi = min(r1, c1)

    def log_pmf(k: int) -> float:
        # C(c1,k)*C(n-c1,r1-k) / C(n,r1)
        return (
            _log_factorial(c1)
            - _log_factorial(k)
            - _log_factorial(c1 - k)
            + _log_factorial(n - c1)
            - _log_factorial(r1 - k)
            - _log_factorial((n - c1) - (r1 - k))
            - _log_factorial(n)
            + _log_factorial(r1)
            + _log_factorial(n - r1)
        )

    log_p_obs = log_pmf(a)
    p = 0.0
    for k in range(lo, hi + 1):
        lp = log_pmf(k)
        if lp <= log_p_obs + 1e-12:
            p += math.exp(lp)
    p = min(1.0, max(0.0, p))
    return {
        "method": "fisher",
        "p_value": round(p, 6),
        "odds_ratio": round(float(odds), 4),
        "applicable": True,
        "table": [[a, b], [c, d]],
    }


def chi_square_2x2(a: int, b: int, c: int, d: int) -> dict:
    """χ² with Yates correction; only when all expected >= 5."""
    a, b, c, d = int(a), int(b), int(c), int(d)
    n = a + b + c + d
    if n == 0:
        return {"method": "chi2", "p_value": None, "applicable": False, "reason": "empty"}
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d
    expected = [
        [r1 * c1 / n, r1 * c2 / n],
        [r2 * c1 / n, r2 * c2 / n],
    ]
    if any(e < 5 for row in expected for e in row):
        return {
            "method": "chi2",
            "p_value": None,
            "applicable": False,
            "reason": "expected<5",
            "expected": expected,
        }
    # Yates-corrected chi-square
    chi2 = n * (abs(a * d - b * c) - n / 2.0) ** 2 / (r1 * r2 * c1 * c2) if r1 and r2 and c1 and c2 else 0.0
    # df=1 survival function via erfc
    # P(χ²_1 > x) = erfc(sqrt(x/2))
    p = math.erfc(math.sqrt(max(chi2, 0.0) / 2.0))
    return {
        "method": "chi2",
        "p_value": round(p, 6),
        "chi2": round(chi2, 4),
        "applicable": True,
        "table": [[a, b], [c, d]],
        "expected": [[round(e, 3) for e in row] for row in expected],
    }


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
    """Build one A vs B comparison row with pp + optional Fisher/χ²."""
    na, nb = len(reviews_a), len(reviews_b)
    ha = len(reviews_a & hit_reviews)
    hb = len(reviews_b & hit_reviews)
    rate_a = _within_rate(ha, na)
    rate_b = _within_rate(hb, nb)
    pp = round(rate_a - rate_b, 2)

    a, b = ha, na - ha
    c, d = hb, nb - hb

    note_parts = []
    strong_ok = na >= MIN_DIRECTIONAL_N and nb >= MIN_DIRECTIONAL_N
    if not strong_ok:
        note_parts.append("样本不足，仅展示，不生成强结论")

    fisher = fisher_exact_2x2(a, b, c, d)
    chi2 = chi_square_2x2(a, b, c, d)

    # Prefer Fisher always for small/medium; attach χ² when applicable
    test = {
        "fisher": fisher,
        "chi2": chi2 if chi2.get("applicable") else {"method": "chi2", "applicable": False, "reason": chi2.get("reason")},
        "primary": "chi2" if chi2.get("applicable") and min(na, nb) >= 20 else "fisher",
    }
    primary = test["fisher"] if test["primary"] == "fisher" else test["chi2"]
    p_value = primary.get("p_value")
    effect = {
        "pp_diff": pp,
        "odds_ratio": fisher.get("odds_ratio"),
    }
    if abs(pp) >= LARGE_PP_THRESHOLD and (p_value is None or p_value > 0.05):
        note_parts.append("差异幅度较大（≥10pp），即使未达显著仍值得关注")

    return {
        "segment_a": segment_a,
        "segment_b": segment_b,
        "metric_type": metric_type,
        "dimension": dimension,
        "rate_a": rate_a,
        "rate_b": rate_b,
        "pp_diff": pp,
        "n_a": na,
        "n_b": nb,
        "hit_a": ha,
        "hit_b": hb,
        "sample_status": "可比较" if strong_ok else "样本不足",
        "allow_strong_conclusion": strong_ok,
        "effect_size": effect,
        "test": test,
        "p_value": p_value,
        "test_method": test["primary"],
        "note": "；".join(note_parts) if note_parts else "",
    }


def build_comparisons(
    items: list[dict],
    segments: list[dict],
    *,
    max_compare_segments: int = MAX_COMPARE_SEGMENTS,
    max_comparisons: int = MAX_COMPARISONS,
    attribute_specs: list[dict] | None = None,
) -> list[dict]:
    """Pairwise comparisons among top segments on shared association dims."""
    top = sorted(
        segments,
        key=lambda x: (-int(x["mention_count"]), x["segment"]),
    )[: max(0, int(max_compare_segments))]
    if len(top) < 2:
        return []

    seg_sets = {s["segment"]: set(s.get("review_rows") or []) for s in top}
    # Candidate metrics: dims appearing in any of these segments' associations
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
            # Only compare if at least one side has hits (avoid noise)
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
            # Keep meaningful diffs or any with hits on both sides
            if abs(row["pp_diff"]) < 1.0 and row["hit_a"] + row["hit_b"] < 2:
                continue
            comps.append(row)

    comps.sort(
        key=lambda x: (
            0 if x["allow_strong_conclusion"] else 1,
            -abs(float(x["pp_diff"])),
            x["segment_a"],
            x["segment_b"],
            x["metric_type"],
            x["dimension"],
        )
    )
    return comps[: max(1, int(max_comparisons))]


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
                "sample_status": s["sample_status"],
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
            "min_directional_n": MIN_DIRECTIONAL_N,
            "denominator": "analyzed_reviews for segment share; within-segment n for association rates",
            "dedup": "unique review_row",
            "category_lexicon": False,
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
            f"占有效评论 {float(s['mention_rate']):.1f}%｜{s['sample_status']}"
        )
    lines.append("")

    lines.append("### 人群关联（组内提及率，分母=该人群样本数）")
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
    lines.append("### 人群差异（百分点差异 + 检验辅助）")
    if not comps:
        lines.append("（无可比较人群对）")
    else:
        for c in comps:
            p = c.get("p_value")
            ptxt = f"p={p}" if p is not None else "p=n/a"
            lines.append(
                f"- [{c['metric_type']}/{c['dimension']}] "
                f"{c['segment_a']} {float(c['rate_a']):.1f}% vs "
                f"{c['segment_b']} {float(c['rate_b']):.1f}%｜"
                f"Δ={float(c['pp_diff']):+.1f}pp｜"
                f"n={c['n_a']}/{c['n_b']}｜{c.get('test_method')} {ptxt}｜"
                f"OR={((c.get('effect_size') or {}).get('odds_ratio'))}｜"
                f"{c.get('sample_status')}｜{c.get('note') or ''}"
            )
    lines.append("")
    lines.append(
        "规则：n<10 标记样本不足，不写强结论；"
        "统计检验只是辅助；大 pp 差异即使 p>0.05 也要关注；"
        "外部研究不可改写上述内部数字。"
    )
    return "\n".join(lines).strip()
