# -*- coding: utf-8 -*-
"""V5 Review Intelligence: build AI input, validate MODEL_OUTPUT, enrich with Python stats."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from .constants import (
    ATTRIBUTE_ASSESSMENTS,
    EXTERNAL_RESEARCH_STATUSES,
    INTELLIGENCE_SCHEMA_VERSION,
    LABEL_OTHER,
    OPPORTUNITY_SIGNAL_TYPES,
    PRIORITY_LEVELS,
    SEVERITY_LEVELS,
    VOC_TYPES,
)
from .extract_codec import parse_json_content
from .segment_stats import segment_dim_cooccur
from .statistics import mention_rate, unique_review_count

_ALLOWED_TITLES = set(VOC_TYPES)


def known_dimensions_by_type(summary_rows: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for r in summary_rows or []:
        t = (r.get("item_type") or "").strip()
        d = (r.get("dimension") or "").strip()
        if t and d and d != LABEL_OTHER:
            out[t].add(d)
    return dict(out)


def summary_lookup(summary_rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {
        ((r.get("item_type") or "").strip(), (r.get("dimension") or "").strip()): r
        for r in (summary_rows or [])
        if (r.get("item_type") or "").strip() and (r.get("dimension") or "").strip()
    }


def build_signal_block(items: list[dict], *, top_n: int = 8) -> str:
    """Plain-text signal-type breakdown for 用户满意 / 未被满足."""
    groups: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    for it in items or []:
        t = (it.get("item_type") or "").strip()
        if t not in {"用户满意", "未被满足"}:
            continue
        d = (it.get("merged_dimension") or it.get("dimension") or "").strip()
        sig = (it.get("signal_type") or "").strip() or "（未标注）"
        if not d:
            continue
        groups[(t, d, sig)].add(int(it.get("review_row") or 0))

    lines: list[str] = ["## 满足信号类型"]
    for t in ("用户满意", "未被满足"):
        lines.append(f"### {t}")
        rows = [
            (d, sig, len(rset))
            for (tt, d, sig), rset in groups.items()
            if tt == t
        ]
        rows.sort(key=lambda x: (-x[2], x[0], x[1]))
        if not rows:
            lines.append("（无）")
            continue
        for d, sig, cnt in rows[: max(1, int(top_n) * 3)]:
            lines.append(f"- {d}｜信号={sig}｜唯一评论={cnt}")
        lines.append("")
    return "\n".join(lines).strip()


def build_stats_block(summary_rows: list[dict], *, top_n: int = 8) -> str:
    """Plain-text block for the intelligence user prompt."""
    lines: list[str] = []
    for t in VOC_TYPES:
        rows = [
            r
            for r in (summary_rows or [])
            if (r.get("item_type") or "") == t and str(r.get("dimension") or "") != LABEL_OTHER
        ]
        rows.sort(
            key=lambda x: (
                -float(x.get("mention_rate") or 0),
                -int(x.get("mention_count") or 0),
                str(x.get("dimension") or ""),
            )
        )
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
            lines.append(f"- {dim}：{rate:.1f}%（唯一评论 {cnt}）｜{fb}")
        lines.append("")
    return "\n".join(lines).strip()


def compute_intelligence_input_hash(
    *,
    system_prompt: str,
    user_prompt: str,
    schema_version: str = INTELLIGENCE_SCHEMA_VERSION,
) -> str:
    """
    Stale-output hash based on what the AI actually receives:
    SHA256(system_prompt + user_prompt + schema_version).
    """
    raw = f"{system_prompt or ''}\n---\n{user_prompt or ''}\n---\n{schema_version or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Backward-compatible alias used by older tests / call sites
def compute_input_hash(payload: dict | str, *args, **kwargs) -> str:
    if isinstance(payload, dict) and "system_prompt" in payload:
        return compute_intelligence_input_hash(
            system_prompt=str(payload.get("system_prompt") or ""),
            user_prompt=str(payload.get("user_prompt") or ""),
            schema_version=str(payload.get("schema_version") or INTELLIGENCE_SCHEMA_VERSION),
        )
    # Legacy dict hash (tests that still pass structured payload)
    if isinstance(payload, dict):
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return hashlib.sha256(str(payload or "").encode("utf-8")).hexdigest()


def _as_str_list(value, *, field: str) -> tuple[list[str], str | None]:
    if not isinstance(value, list):
        return [], f"{field} 必须是数组"
    out: list[str] = []
    for i, v in enumerate(value):
        s = str(v or "").strip()
        if not s:
            return [], f"{field}[{i}] 必须是非空字符串"
        out.append(s)
    return out, None


def validate_segment_intelligence(
    si: dict | None,
    *,
    known_segments: set[str] | None = None,
    known_dims: dict[str, set[str]] | None = None,
    items: list[dict] | None = None,
) -> str | None:
    """Validate segment_intelligence block; None/missing is allowed when no segments."""
    if si is None:
        return None
    if not isinstance(si, dict):
        return "segment_intelligence 必须是对象"

    segs = si.get("segments")
    if segs is None:
        segs = []
    if not isinstance(segs, list):
        return "segment_intelligence.segments 必须是数组"
    for i, row in enumerate(segs):
        if not isinstance(row, dict):
            return f"segment_intelligence.segments[{i}] 必须是对象"
        name = str(row.get("segment") or "").strip()
        if not name:
            return f"segment_intelligence.segments[{i}].segment 不能为空"
        if known_segments is not None and name not in known_segments:
            return f"segment_intelligence.segments[{i}] 引用未知人群：{name}"
        summary = str(row.get("summary") or "").strip()
        if not summary:
            return f"segment_intelligence.segments[{i}].summary 不能为空"
        _, err = _as_str_list(
            row.get("important_attributes") or [],
            field=f"segment_intelligence.segments[{i}].important_attributes",
        )
        if err:
            return err
        impl = row.get("development_implications")
        if impl is None:
            impl = []
        if not isinstance(impl, list) or not impl:
            return f"segment_intelligence.segments[{i}].development_implications 必须为非空数组"
        for j, x in enumerate(impl):
            if not isinstance(x, str) or not x.strip():
                return f"segment_intelligence.segments[{i}].development_implications[{j}] 必须是非空字符串"

    comps = si.get("comparisons")
    if comps is None:
        comps = []
    if not isinstance(comps, list):
        return "segment_intelligence.comparisons 必须是数组"
    for i, row in enumerate(comps):
        if not isinstance(row, dict):
            return f"segment_intelligence.comparisons[{i}] 必须是对象"
        a = str(row.get("segment_a") or "").strip()
        b = str(row.get("segment_b") or "").strip()
        finding = str(row.get("finding") or "").strip()
        if not a or not b:
            return f"segment_intelligence.comparisons[{i}] 缺少 segment_a/segment_b"
        if known_segments is not None:
            if a not in known_segments:
                return f"segment_intelligence.comparisons[{i}] 引用未知人群：{a}"
            if b not in known_segments:
                return f"segment_intelligence.comparisons[{i}] 引用未知人群：{b}"
        if not finding:
            return f"segment_intelligence.comparisons[{i}].finding 不能为空"

    status = str(si.get("external_research_status") or "unavailable").strip()
    if status not in EXTERNAL_RESEARCH_STATUSES:
        return f"external_research_status 非法：{status}"
    ext = si.get("external_research")
    if ext is None:
        ext = []
    if not isinstance(ext, list):
        return "external_research 必须是数组"
    if status in {"unavailable", "skipped"} and ext:
        return "external_research_status 为 unavailable/skipped 时 external_research 必须为空"
    for i, row in enumerate(ext):
        if not isinstance(row, dict):
            return f"external_research[{i}] 必须是对象"
        topic = str(row.get("topic") or "").strip()
        finding = str(row.get("finding") or "").strip()
        title = str(row.get("source_title") or "").strip()
        url = str(row.get("source_url") or "").strip()
        supports = str(row.get("supports") or "").strip()
        if not topic or not finding or not title or not url or not supports:
            return (
                f"external_research[{i}] 必须包含 topic/finding/source_title/source_url/supports"
            )

    opps = si.get("segment_product_opportunities")
    if opps is None:
        opps = []
    if not isinstance(opps, list):
        return "segment_product_opportunities 必须是数组"
    all_known_dims: set[str] = set()
    if known_dims is not None:
        for s in known_dims.values():
            all_known_dims |= s
    for i, row in enumerate(opps):
        if not isinstance(row, dict):
            return f"segment_product_opportunities[{i}] 必须是对象"
        seg = str(row.get("segment") or "").strip()
        opp = str(row.get("opportunity") or "").strip()
        rec = str(row.get("recommendation") or "").strip()
        if not seg or not opp or not rec:
            return f"segment_product_opportunities[{i}] 缺少 segment/opportunity/recommendation"
        if known_segments is not None and seg not in known_segments:
            return f"segment_product_opportunities[{i}] 引用未知人群：{seg}"
        evidence, err = _as_str_list(
            row.get("review_evidence") or [],
            field=f"segment_product_opportunities[{i}].review_evidence",
        )
        if err:
            return err
        if not evidence:
            return f"segment_product_opportunities[{i}].review_evidence 不能为空"
        if known_dims is not None:
            for d in evidence:
                if d not in all_known_dims:
                    return f"segment_product_opportunities[{i}] 引用未知标准维度：{d}"
        # Hard rule: each evidence dim must co-occur with the segment on ≥1 review
        if items is not None:
            for d in evidence:
                if segment_dim_cooccur(items, seg, d) < 1:
                    return (
                        f"segment_product_opportunities[{i}] 证据「{d}」"
                        f"未与人群「{seg}」共现于同一评论"
                    )
    return None


def validate_intelligence_payload(
    payload: dict,
    *,
    known_dims: dict[str, set[str]] | None = None,
    known_segments: set[str] | None = None,
    items: list[dict] | None = None,
) -> str | None:
    """
    Strict schema + optional unknown-dimension rejection.
    AI must not invent percentages; Python ignores any rate fields if present.
    """
    if not isinstance(payload, dict):
        return "Intelligence 输出必须是对象"

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

    attrs = payload.get("attribute_performance")
    if attrs is None:
        attrs = []
    if not isinstance(attrs, list):
        return "attribute_performance 必须是数组"
    for i, row in enumerate(attrs):
        if not isinstance(row, dict):
            return f"attribute_performance[{i}] 必须是对象"
        attr = str(row.get("attribute") or "").strip()
        if not attr:
            return f"attribute_performance[{i}].attribute 不能为空"
        pos, err = _as_str_list(row.get("positive_dimensions") or [], field=f"attribute_performance[{i}].positive_dimensions")
        if err:
            return err
        neg, err = _as_str_list(row.get("negative_dimensions") or [], field=f"attribute_performance[{i}].negative_dimensions")
        if err:
            return err
        if not pos and not neg:
            return f"attribute_performance[{i}] 正负维度不能同时为空"
        assessment = str(row.get("assessment") or "").strip()
        if assessment and assessment not in ATTRIBUTE_ASSESSMENTS:
            return f"attribute_performance[{i}].assessment 非法：{assessment}"
        if known_dims is not None:
            for d in pos:
                if d not in (known_dims.get("用户满意") or set()):
                    return f"attribute_performance[{i}] 引用未知用户满意维度：{d}"
            for d in neg:
                if d not in (known_dims.get("未被满足") or set()):
                    return f"attribute_performance[{i}] 引用未知未被满足维度：{d}"

    pains = payload.get("pain_priorities")
    if pains is None:
        pains = []
    if not isinstance(pains, list):
        return "pain_priorities 必须是数组"
    for i, row in enumerate(pains):
        if not isinstance(row, dict):
            return f"pain_priorities[{i}] 必须是对象"
        dim = str(row.get("dimension") or "").strip()
        if not dim:
            return f"pain_priorities[{i}].dimension 不能为空"
        severity = str(row.get("severity") or "").strip()
        priority = str(row.get("priority") or "").strip()
        reason = str(row.get("reason") or "").strip()
        if severity not in SEVERITY_LEVELS:
            return f"pain_priorities[{i}].severity 非法：{severity}"
        if priority not in PRIORITY_LEVELS:
            return f"pain_priorities[{i}].priority 非法：{priority}"
        if not reason:
            return f"pain_priorities[{i}].reason 不能为空"
        if known_dims is not None and dim not in (known_dims.get("未被满足") or set()):
            return f"pain_priorities[{i}] 引用未知未被满足维度：{dim}"

    opps = payload.get("opportunities")
    if opps is None:
        opps = []
    if not isinstance(opps, list):
        return "opportunities 必须是数组"
    for i, row in enumerate(opps):
        if not isinstance(row, dict):
            return f"opportunities[{i}] 必须是对象"
        opp = str(row.get("opportunity") or "").strip()
        if not opp:
            return f"opportunities[{i}].opportunity 不能为空"
        sources, err = _as_str_list(
            row.get("source_dimensions") or [],
            field=f"opportunities[{i}].source_dimensions",
        )
        if err:
            return err
        if not sources:
            return f"opportunities[{i}].source_dimensions 不能为空"
        reason = str(row.get("reason") or "").strip()
        if not reason:
            return f"opportunities[{i}].reason 不能为空"
        if known_dims is not None:
            for d in sources:
                if d not in (known_dims.get("未被满足") or set()):
                    return f"opportunities[{i}] 引用未知未被满足维度：{d}"

    recs = payload.get("recommendations")
    if recs is None:
        recs = {}
    if not isinstance(recs, dict):
        return "recommendations 必须是对象"
    for key in ("priority_improvements", "keep_strengths", "explore_opportunities"):
        arr = recs.get(key)
        if arr is None:
            continue
        if not isinstance(arr, list):
            return f"recommendations.{key} 必须是数组"
        for i, row in enumerate(arr):
            if isinstance(row, str):
                if not row.strip():
                    return f"recommendations.{key}[{i}] 不能为空"
                continue
            if not isinstance(row, dict):
                return f"recommendations.{key}[{i}] 必须是对象或字符串"
            action = str(row.get("action") or row.get("recommendation") or "").strip()
            if not action:
                return f"recommendations.{key}[{i}].action 不能为空"
            evidence = str(row.get("evidence") or row.get("basis") or "").strip()
            if not evidence:
                return f"recommendations.{key}[{i}].evidence 不能为空"
            dims = row.get("source_dimensions") or row.get("dimensions") or []
            if dims:
                _, err = _as_str_list(dims, field=f"recommendations.{key}[{i}].source_dimensions")
                if err:
                    return err
                if known_dims is not None:
                    all_known = set()
                    for s in known_dims.values():
                        all_known |= s
                    for d in dims:
                        ds = str(d or "").strip()
                        if ds and ds not in all_known:
                            return f"recommendations.{key}[{i}] 引用未知标准维度：{ds}"

    si_err = validate_segment_intelligence(
        payload.get("segment_intelligence"),
        known_segments=known_segments,
        known_dims=known_dims,
        items=items,
    )
    if si_err:
        return si_err

    return None


def enrich_intelligence(
    payload: dict,
    *,
    items: list[dict],
    summary_rows: list[dict],
    analyzed_reviews: int,
    segment_analysis: dict | None = None,
) -> dict:
    """
    Attach Python-computed mention_count / mention_rate.
    Never trust AI-generated percentages.
    """
    lookup = summary_lookup(summary_rows)
    denom = max(1, int(analyzed_reviews or 1))

    attrs_out = []
    for row in payload.get("attribute_performance") or []:
        if not isinstance(row, dict):
            continue
        pos = [str(x).strip() for x in (row.get("positive_dimensions") or []) if str(x).strip()]
        neg = [str(x).strip() for x in (row.get("negative_dimensions") or []) if str(x).strip()]
        pos_count = unique_review_count(items, item_type="用户满意", dimensions=pos)
        neg_count = unique_review_count(items, item_type="未被满足", dimensions=neg)
        assessment = str(row.get("assessment") or "").strip()
        if not assessment:
            if pos_count and not neg_count:
                assessment = "整体优势"
            elif neg_count and not pos_count:
                assessment = "整体短板"
            elif pos_count and neg_count:
                assessment = "优劣势并存"
            else:
                assessment = "证据不足"
        attrs_out.append(
            {
                "attribute": str(row.get("attribute") or "").strip(),
                "positive_dimensions": pos,
                "negative_dimensions": neg,
                "positive_mention_count": pos_count,
                "positive_mention_rate": mention_rate(pos_count, denom),
                "negative_mention_count": neg_count,
                "negative_mention_rate": mention_rate(neg_count, denom),
                "assessment": assessment,
            }
        )
    attrs_out.sort(
        key=lambda x: (
            -(float(x["positive_mention_rate"]) + float(x["negative_mention_rate"])),
            x["attribute"],
        )
    )

    pains_out = []
    for row in payload.get("pain_priorities") or []:
        if not isinstance(row, dict):
            continue
        dim = str(row.get("dimension") or "").strip()
        base = lookup.get(("未被满足", dim)) or {}
        count = int(base.get("mention_count") or 0)
        rate = float(base.get("mention_rate") or 0)
        if not base:
            count = unique_review_count(items, item_type="未被满足", dimensions=[dim])
            rate = mention_rate(count, denom)
        pains_out.append(
            {
                "dimension": dim,
                "severity": str(row.get("severity") or "").strip(),
                "priority": str(row.get("priority") or "").strip(),
                "reason": str(row.get("reason") or "").strip(),
                "mention_count": count,
                "mention_rate": rate,
            }
        )
    pains_out.sort(
        key=lambda x: (
            {"高": 0, "中": 1, "低": 2}.get(x["priority"], 9),
            -float(x["mention_rate"]),
            x["dimension"],
        )
    )

    opps_out = []
    for row in payload.get("opportunities") or []:
        if not isinstance(row, dict):
            continue
        sources = [str(x).strip() for x in (row.get("source_dimensions") or []) if str(x).strip()]
        # Prefer reviews that hit source dims AND opportunity-relevant signals when available
        hit_rows: set[int] = set()
        signal_labels: set[str] = set()
        for it in items or []:
            if (it.get("item_type") or "").strip() != "未被满足":
                continue
            d = (it.get("merged_dimension") or it.get("dimension") or "").strip()
            if d not in sources:
                continue
            sig = (it.get("signal_type") or "").strip()
            if sig:
                signal_labels.add(sig)
            # If signal present, prefer opportunity-relevant; else count all
            if not sig or sig in OPPORTUNITY_SIGNAL_TYPES or sig == "明确问题":
                hit_rows.add(int(it.get("review_row") or 0))
        count = len({r for r in hit_rows if r})
        if count <= 0:
            count = unique_review_count(items, item_type="未被满足", dimensions=sources)
        rate = mention_rate(count, denom)
        # evidence signals: intersection with opportunity types, else all seen
        evidence = sorted(s for s in signal_labels if s in OPPORTUNITY_SIGNAL_TYPES) or sorted(signal_labels)
        opps_out.append(
            {
                "opportunity": str(row.get("opportunity") or "").strip(),
                "source_dimensions": sources,
                "reason": str(row.get("reason") or "").strip(),
                "mention_count": count,
                "mention_rate": rate,
                "evidence_signals": evidence,
            }
        )
    opps_out.sort(key=lambda x: (-float(x["mention_rate"]), x["opportunity"]))

    def _norm_rec_list(arr) -> list[dict]:
        out = []
        for row in arr or []:
            if isinstance(row, str):
                text = row.strip()
                if text:
                    out.append({"action": text, "evidence": "", "source_dimensions": []})
                continue
            if not isinstance(row, dict):
                continue
            action = str(row.get("action") or row.get("recommendation") or "").strip()
            evidence = str(row.get("evidence") or row.get("basis") or "").strip()
            dims = [
                str(x).strip()
                for x in (row.get("source_dimensions") or row.get("dimensions") or [])
                if str(x).strip()
            ]
            if action:
                out.append(
                    {
                        "action": action,
                        "evidence": evidence,
                        "source_dimensions": dims,
                    }
                )
        return out

    recs_in = payload.get("recommendations") if isinstance(payload.get("recommendations"), dict) else {}
    recommendations = {
        "priority_improvements": _norm_rec_list(recs_in.get("priority_improvements")),
        "keep_strengths": _norm_rec_list(recs_in.get("keep_strengths")),
        "explore_opportunities": _norm_rec_list(recs_in.get("explore_opportunities")),
    }

    # Attach Python segment stats (never trust AI percentages for segments)
    si_in = payload.get("segment_intelligence") if isinstance(payload.get("segment_intelligence"), dict) else {}
    py_seg = segment_analysis or {}
    py_by_name = {s.get("segment"): s for s in (py_seg.get("segments") or []) if isinstance(s, dict)}
    seg_out = []
    for row in si_in.get("segments") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("segment") or "").strip()
        base = py_by_name.get(name) or {}
        seg_out.append(
            {
                "segment": name,
                "summary": str(row.get("summary") or "").strip(),
                "important_attributes": [
                    str(x).strip() for x in (row.get("important_attributes") or []) if str(x).strip()
                ],
                "development_implications": [
                    str(x).strip() for x in (row.get("development_implications") or []) if str(x).strip()
                ],
                "mention_count": int(base.get("mention_count") or 0),
                "mention_rate": float(base.get("mention_rate") or 0),
                "associations": base.get("associations") or {},
            }
        )
    comps_out = []
    for row in si_in.get("comparisons") or []:
        if not isinstance(row, dict):
            continue
        comps_out.append(
            {
                "segment_a": str(row.get("segment_a") or "").strip(),
                "segment_b": str(row.get("segment_b") or "").strip(),
                "finding": str(row.get("finding") or "").strip(),
                "external_research_needed": bool(row.get("external_research_needed")),
            }
        )
    ext_status = str(si_in.get("external_research_status") or "unavailable").strip()
    if ext_status not in EXTERNAL_RESEARCH_STATUSES:
        ext_status = "unavailable"
    ext_items = []
    if ext_status == "ok":
        for row in si_in.get("external_research") or []:
            if not isinstance(row, dict):
                continue
            ext_items.append(
                {
                    "topic": str(row.get("topic") or "").strip(),
                    "finding": str(row.get("finding") or "").strip(),
                    "source_title": str(row.get("source_title") or "").strip(),
                    "source_url": str(row.get("source_url") or "").strip(),
                    "supports": str(row.get("supports") or "").strip(),
                }
            )
    seg_opps = []
    for row in si_in.get("segment_product_opportunities") or []:
        if not isinstance(row, dict):
            continue
        seg_opps.append(
            {
                "segment": str(row.get("segment") or "").strip(),
                "opportunity": str(row.get("opportunity") or "").strip(),
                "review_evidence": [
                    str(x).strip() for x in (row.get("review_evidence") or []) if str(x).strip()
                ],
                "external_evidence": [
                    str(x).strip() for x in (row.get("external_evidence") or []) if str(x).strip()
                ],
                "recommendation": str(row.get("recommendation") or "").strip(),
            }
        )
    segment_intelligence = {
        "segments": seg_out,
        "comparisons": comps_out,
        "external_research_status": ext_status,
        "external_research": ext_items,
        "segment_product_opportunities": seg_opps,
        "python_comparisons": py_seg.get("comparisons") or [],
        "python_segments": py_seg.get("segments") or [],
    }

    return {
        "sections": payload.get("sections") or [],
        "attribute_performance": attrs_out,
        "pain_priorities": pains_out,
        "opportunities": opps_out,
        "recommendations": recommendations,
        "segment_intelligence": segment_intelligence,
        "analyzed_reviews": int(analyzed_reviews or 0),
    }


def format_intelligence_text(enriched: dict) -> str:
    """Plain-text copyable summary for AI总结 sheet / overview column."""
    chunks: list[str] = ["AI评论洞察总结", ""]

    sections = enriched.get("sections") if isinstance(enriched, dict) else None
    if isinstance(sections, list):
        by_title = {
            str(s.get("title") or "").strip(): s
            for s in sections
            if isinstance(s, dict)
        }
        for title in VOC_TYPES:
            sec = by_title.get(title) or {}
            chunks.append(f"【{title}】")
            bullets = sec.get("bullets") if isinstance(sec, dict) else None
            if not isinstance(bullets, list) or not bullets:
                chunks.append("· 证据不足")
            else:
                for b in bullets:
                    text = str(b or "").strip()
                    if text:
                        chunks.append(f"· {text}")
            chunks.append("")

    chunks.append("【核心产品属性表现】")
    attrs = enriched.get("attribute_performance") or []
    if not attrs:
        chunks.append("· 证据不足")
    else:
        for a in attrs:
            chunks.append(
                f"· {a.get('attribute')}："
                f"正向 {float(a.get('positive_mention_rate') or 0):.1f}%"
                f"（{'、'.join(a.get('positive_dimensions') or []) or '无'}）｜"
                f"负向 {float(a.get('negative_mention_rate') or 0):.1f}%"
                f"（{'、'.join(a.get('negative_dimensions') or []) or '无'}）｜"
                f"{a.get('assessment') or ''}"
            )
    chunks.append("")

    chunks.append("【痛点优先级】")
    pains = enriched.get("pain_priorities") or []
    if not pains:
        chunks.append("· 证据不足")
    else:
        for p in pains:
            chunks.append(
                f"· {p.get('dimension')}：{float(p.get('mention_rate') or 0):.1f}%｜"
                f"严重程度 {p.get('severity')}｜优先级 {p.get('priority')}｜"
                f"{p.get('reason')}"
            )
    chunks.append("")

    chunks.append("【用户明确需求 / 产品机会】")
    opps = enriched.get("opportunities") or []
    if not opps:
        chunks.append("· 证据不足")
    else:
        for o in opps:
            sig = "、".join(o.get("evidence_signals") or []) or "—"
            chunks.append(
                f"· {o.get('opportunity')}：{float(o.get('mention_rate') or 0):.1f}%｜"
                f"来源 {'、'.join(o.get('source_dimensions') or [])}｜信号 {sig}｜"
                f"{o.get('reason')}"
            )
    chunks.append("")

    chunks.append("【产品改进建议】")
    recs = enriched.get("recommendations") or {}
    mapping = [
        ("优先优化", "priority_improvements"),
        ("建议保留", "keep_strengths"),
        ("可探索机会", "explore_opportunities"),
    ]
    any_rec = False
    for label, key in mapping:
        arr = recs.get(key) or []
        if not arr:
            continue
        any_rec = True
        chunks.append(f"· {label}：")
        for row in arr:
            if isinstance(row, dict):
                action = row.get("action") or ""
                evidence = row.get("evidence") or ""
                if evidence:
                    chunks.append(f"  - {action}（依据：{evidence}）")
                else:
                    chunks.append(f"  - {action}")
            else:
                chunks.append(f"  - {row}")
    if not any_rec:
        chunks.append("· 证据不足")
    chunks.append("")

    chunks.append("【消费人群深度分析】")
    si = enriched.get("segment_intelligence") if isinstance(enriched, dict) else None
    if not isinstance(si, dict) or not (si.get("segments") or si.get("python_segments")):
        chunks.append("· 证据不足")
    else:
        chunks.append("· 主要人群：")
        for s in si.get("segments") or si.get("python_segments") or []:
            if not isinstance(s, dict):
                continue
            name = s.get("segment") or ""
            n = s.get("mention_count")
            rate = s.get("mention_rate")
            summary = s.get("summary") or ""
            line = f"  - {name}"
            if n is not None:
                line += f"（n={n}，{float(rate or 0):.1f}%）"
            if summary:
                line += f"：{summary}"
            chunks.append(line)
        chunks.append("· 人群差异：")
        comps = si.get("comparisons") or []
        if not comps:
            chunks.append("  - 暂无可解释的人群对比")
        else:
            for c in comps:
                if not isinstance(c, dict):
                    continue
                chunks.append(
                    f"  - {c.get('segment_a')} vs {c.get('segment_b')}：{c.get('finding')}"
                )
        chunks.append("· 外部研究解释：")
        status = si.get("external_research_status") or "unavailable"
        if status != "ok" or not (si.get("external_research") or []):
            chunks.append(f"  - 【外部研究】状态={status}（未使用或不可用，未伪造来源）")
        else:
            for e in si.get("external_research") or []:
                if not isinstance(e, dict):
                    continue
                chunks.append(
                    f"  - 【外部研究】{e.get('topic')}：{e.get('finding')} "
                    f"（{e.get('source_title')} | {e.get('source_url')}）"
                    f"｜支持：{e.get('supports')}"
                )
        chunks.append("· 人群细分产品开发方向：")
        opps = si.get("segment_product_opportunities") or []
        if not opps:
            chunks.append("  - 暂无")
        else:
            for o in opps:
                if not isinstance(o, dict):
                    continue
                chunks.append(
                    f"  - 【产品开发推论】[{o.get('segment')}] {o.get('opportunity')} → "
                    f"{o.get('recommendation')}｜评论证据：{'、'.join(o.get('review_evidence') or [])}"
                )

    return "\n".join(chunks).strip()


def parse_intelligence_output(
    raw_text: str,
    *,
    summary_rows: list[dict],
    items: list[dict],
    analyzed_reviews: int,
    segment_analysis: dict | None = None,
) -> tuple[dict | None, str, str | None]:
    """
    Returns (enriched_payload, summary_text, error).
    """
    text = (raw_text or "").strip()
    if not text or text.startswith("/*"):
        return None, "", "Intelligence 模型输出尚未填写"
    payload = parse_json_content(text)
    if payload is None:
        return None, "", "无法解析 Intelligence JSON"
    known = known_dimensions_by_type(summary_rows)
    # Always pass set (possibly empty): empty ⇒ any AI segment name is rejected
    known_segments = set((segment_analysis or {}).get("known_segments") or [])
    err = validate_intelligence_payload(
        payload,
        known_dims=known,
        known_segments=known_segments,
        items=items,
    )
    if err:
        return None, "", err
    enriched = enrich_intelligence(
        payload,
        items=items,
        summary_rows=summary_rows,
        analyzed_reviews=analyzed_reviews,
        segment_analysis=segment_analysis,
    )
    return enriched, format_intelligence_text(enriched), None


# --- thin aliases used by older summary_codec call sites ---
def validate_summary_payload(payload: dict) -> str | None:
    return validate_intelligence_payload(payload, known_dims=None)


def format_summary_text(payload: dict) -> str:
    # Sections-only formatting for unit tests that only pass sections
    if not isinstance(payload, dict):
        return ""
    if "attribute_performance" in payload or "pain_priorities" in payload:
        return format_intelligence_text(payload)
    chunks: list[str] = ["AI评论洞察总结", ""]
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return ""
    by_title = {
        str(s.get("title") or "").strip(): s
        for s in sections
        if isinstance(s, dict)
    }
    for title in VOC_TYPES:
        sec = by_title.get(title)
        chunks.append(f"【{title}】")
        if not sec:
            chunks.append("· 证据不足")
        else:
            bullets = sec.get("bullets") or []
            if not bullets:
                chunks.append("· 证据不足")
            else:
                for b in bullets:
                    t = str(b or "").strip()
                    if t:
                        chunks.append(f"· {t}")
        chunks.append("")
    return "\n".join(chunks).strip()


def parse_summary_output(raw_text: str) -> tuple[str | None, str | None]:
    text = (raw_text or "").strip()
    if not text or text.startswith("/*"):
        return None, "总结模型输出尚未填写"
    payload = parse_json_content(text)
    if payload is None:
        return None, "无法解析总结 JSON"
    err = validate_summary_payload(payload)
    if err:
        return None, err
    return format_summary_text(payload), None
