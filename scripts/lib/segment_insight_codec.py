# -*- coding: utf-8 -*-
"""Build / validate V6 consumer segment insight AI output."""
from __future__ import annotations

from .extract_codec import parse_json_content

_ALLOWED_STATUS = {"ok", "skipped", "unavailable"}


def _as_str_list(value, *, field: str) -> tuple[list[str] | None, str | None]:
    if not isinstance(value, list):
        return None, f"{field} 必须是数组"
    out: list[str] = []
    for i, item in enumerate(value):
        text = str(item or "").strip()
        if not text:
            return None, f"{field}[{i}] 必须是非空字符串"
        out.append(text)
    return out, None


def _as_sources(value, *, field: str) -> tuple[list[dict] | None, str | None]:
    if value is None:
        return [], None
    if not isinstance(value, list):
        return None, f"{field} 必须是数组"
    out: list[dict] = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            return None, f"{field}[{i}] 必须是对象"
        title = str(item.get("source_title") or "").strip()
        url = str(item.get("source_url") or "").strip()
        finding = str(item.get("finding") or "").strip()
        if not title or not url or not finding:
            return None, (
                f"{field}[{i}] 需要非空的 source_title / source_url / finding"
            )
        out.append(
            {
                "source_title": title,
                "source_url": url,
                "finding": finding,
            }
        )
    return out, None


def validate_segment_insight_payload(
    payload: dict,
    *,
    allowed_segments: list[str] | set[str] | None = None,
) -> str | None:
    if not isinstance(payload, dict):
        return "消费人群洞察输出必须是对象"

    status = str(payload.get("external_research_status") or "").strip()
    if status not in _ALLOWED_STATUS:
        return "external_research_status 必须是 ok / skipped / unavailable"

    segments = payload.get("segments")
    if not isinstance(segments, list):
        return "segments 必须是数组"

    # When allowed_segments is provided (incl. []), every segment must be in it.
    # allowed_segments=[] ⇒ segments must be empty.
    enforce_allowlist = allowed_segments is not None
    allowed = (
        {str(s).strip() for s in allowed_segments if str(s).strip()}
        if enforce_allowlist
        else None
    )
    seen: set[str] = set()
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            return f"segments[{i}] 必须是对象"
        name = str(seg.get("segment") or "").strip()
        if not name:
            return f"segments[{i}].segment 不能为空"
        if enforce_allowlist and name not in allowed:
            return f"segments[{i}].segment 不在核心人群列表：{name}"
        if name in seen:
            return f"重复人群：{name}"
        seen.add(name)

        for field in (
            "review_observations",
            "behavior_traits",
            "personality_traits",
            "usage_habits",
            "core_needs",
        ):
            vals, err = _as_str_list(seg.get(field), field=f"segments[{i}].{field}")
            if err:
                return err
            seg[field] = vals

        sources, err = _as_sources(seg.get("sources"), field=f"segments[{i}].sources")
        if err:
            return err
        seg["sources"] = sources

        if status == "ok" and not sources:
            return f"external_research_status=ok 时 segments[{i}].sources 不能为空"
        if status in ("skipped", "unavailable") and sources:
            return f"external_research_status={status} 时不得填写 sources"

    pd = payload.get("product_development")
    if not isinstance(pd, dict):
        return "product_development 必须是对象"
    for field in ("must_have_features", "product_moats"):
        vals, err = _as_str_list(pd.get(field), field=f"product_development.{field}")
        if err:
            return err
        pd[field] = vals

    if not segments and status == "ok":
        return "无核心人群时 external_research_status 不能为 ok"
    return None


def format_segment_insight_digest(payload: dict) -> str:
    """Plain-text digest for AI总结 Sheet cell A11."""
    if not isinstance(payload, dict):
        return ""
    lines: list[str] = ["消费人群洞察总结", ""]
    segments = payload.get("segments") or []
    if not segments:
        lines.append("· 未识别到足够的消费人群证据，从略")
        return "\n".join(lines).strip()

    lines.append("【谁在买】")
    for seg in segments:
        name = str(seg.get("segment") or "").strip()
        obs = seg.get("review_observations") or []
        head = obs[0] if obs else "见评论表现"
        lines.append(f"· {name}：{head}")

    lines.append("")
    lines.append("【这些人是什么样的人】")
    for seg in segments:
        name = str(seg.get("segment") or "").strip()
        traits = (seg.get("behavior_traits") or [])[:2]
        needs = (seg.get("core_needs") or [])[:2]
        bits = traits + needs
        if bits:
            lines.append(f"· {name}：{'；'.join(bits)}")
        else:
            lines.append(f"· {name}：证据有限")

    pd = payload.get("product_development") or {}
    features = pd.get("must_have_features") or []
    moats = pd.get("product_moats") or []
    lines.append("")
    lines.append("【产品应该怎么做】")
    if features:
        lines.append("必须具备：" + "；".join(features[:5]))
    if moats:
        lines.append("应建壁垒：" + "；".join(moats[:5]))
    if not features and not moats:
        lines.append("· 产品开发方向证据不足，从略")
    return "\n".join(lines).strip()


def parse_segment_insight_output(
    raw_text: str,
    *,
    allowed_segments: list[str] | set[str] | None = None,
) -> tuple[dict | None, str | None]:
    text = (raw_text or "").strip()
    if not text or text.startswith("/*"):
        return None, "消费人群洞察模型输出尚未填写"
    payload = parse_json_content(text)
    if payload is None:
        return None, "无法解析消费人群洞察 JSON"
    err = validate_segment_insight_payload(payload, allowed_segments=allowed_segments)
    if err:
        return None, err
    return payload, None
