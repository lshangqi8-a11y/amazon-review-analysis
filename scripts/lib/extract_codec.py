# -*- coding: utf-8 -*-
"""Extract JSON parse/validate → voc items (deterministic)."""
from __future__ import annotations

import json
import re

from .constants import ALLOWED_TYPES, FULFILLMENT_ALLOWED, SIGNAL_TYPES_BY_ITEM_TYPE


def parse_json_content(content: str):
    text = (content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
            m = re.search(pattern, text)
            if not m:
                continue
            try:
                return json.loads(m.group(0))
            except Exception:
                continue
        return None


def extract_item_fields(ex: dict) -> tuple[str, str, str, str]:
    """Return 类型, 原始维度, 单条提炼, 信号类型 (可能为空)."""
    return (
        str(ex.get("类型") or "").strip(),
        str(ex.get("原始维度") or "").strip(),
        str(ex.get("单条提炼") or "").strip(),
        str(ex.get("信号类型") or "").strip(),
    )


def normalize_extract_payload(payload):
    if isinstance(payload, list):
        return {"results": payload}
    if not isinstance(payload, dict):
        return payload
    if isinstance(payload.get("results"), list):
        return payload
    if payload.get("review_id"):
        return {"results": [payload]}
    return payload


def _validate_signal_type(item_type: str, signal: str, *, require_fulfillment_signal: bool) -> str:
    if item_type not in FULFILLMENT_ALLOWED:
        if signal:
            return f"非满足类型不应带信号类型：{item_type}/{signal}"
        return ""
    allowed = SIGNAL_TYPES_BY_ITEM_TYPE.get(item_type) or set()
    if not signal:
        if require_fulfillment_signal:
            return f"{item_type} 的 item 必须包含信号类型（允许：{'/'.join(sorted(allowed))}）"
        return ""
    if signal not in allowed:
        return (
            f"{item_type} 的信号类型非法：{signal}"
            f"（允许：{'/'.join(sorted(allowed))}）"
        )
    return ""


def validate_extract_payload(
    payload,
    expected_ids: set[str],
    *,
    allowed_types: set[str] | None = None,
    require_fulfillment_signal: bool | None = None,
) -> str:
    allowed = allowed_types if allowed_types is not None else ALLOWED_TYPES
    if require_fulfillment_signal is None:
        # Fulfillment-only batches require signal; persona / mixed default off.
        require_fulfillment_signal = allowed <= FULFILLMENT_ALLOWED
    payload = normalize_extract_payload(payload)
    if not isinstance(payload, dict):
        return "抽取结果不是 JSON 对象"
    if "results" not in payload or not isinstance(payload.get("results"), list):
        return "抽取结果缺少 results 数组"
    found_set: set[str] = set()
    for entry in payload.get("results") or []:
        if not isinstance(entry, dict):
            return "results 元素必须是对象"
        rid = str(entry.get("review_id") or "").strip()
        if not rid:
            return "results 元素缺少 review_id"
        if rid in found_set:
            return f"抽取结果存在重复 review_id：{rid}"
        found_set.add(rid)
        items = entry.get("items")
        if not isinstance(items, list):
            return f"{rid} 的 items 必须是数组"
        for ex in items:
            if not isinstance(ex, dict):
                return f"{rid} 的 items 元素必须是对象"
            t, d, s, sig = extract_item_fields(ex)
            if not t or not d or not s:
                return f"{rid} 的 item 必须包含中文字段：类型/单条提炼/原始维度"
            if t not in allowed:
                return f"{rid} 存在非法类型：{t}（本轮允许：{'/'.join(sorted(allowed))}）"
            sig_err = _validate_signal_type(
                t, sig, require_fulfillment_signal=bool(require_fulfillment_signal)
            )
            if sig_err:
                return f"{rid} {sig_err}"
    missing = expected_ids - found_set
    if missing:
        return f"抽取结果缺少 review_id：{', '.join(sorted(missing)[:8])}"
    extra = found_set - expected_ids
    if extra:
        return f"抽取结果含未知 review_id：{', '.join(sorted(extra)[:8])}"
    if len(found_set) != len(expected_ids):
        return f"抽取结果 review_id 数量不一致：期望 {len(expected_ids)}，实际 {len(found_set)}"
    return ""


def to_internal_voc_payload(
    payload,
    expected_ids: set[str] | None = None,
    *,
    allowed_types: set[str] | None = None,
    require_fulfillment_signal: bool | None = None,
) -> list[dict]:
    allowed = allowed_types if allowed_types is not None else ALLOWED_TYPES
    if require_fulfillment_signal is None:
        require_fulfillment_signal = allowed <= FULFILLMENT_ALLOWED
    payload = normalize_extract_payload(payload)
    entries = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        return []
    out = []
    seen_reviews = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rid = str(entry.get("review_id") or "").strip()
        if not rid:
            continue
        if expected_ids is not None and rid not in expected_ids:
            continue
        if rid not in seen_reviews:
            out.append({"review_id": rid, "items": []})
            seen_reviews.add(rid)
        target = next(x for x in out if x["review_id"] == rid)
        item_seen = {
            (i["类型"], i["原始维度"], i["单条提炼"], i.get("信号类型") or "")
            for i in target["items"]
        }
        for ex in entry.get("items") or []:
            if not isinstance(ex, dict):
                continue
            t, d, s, sig = extract_item_fields(ex)
            if t not in allowed or not d or not s:
                continue
            if _validate_signal_type(
                t, sig, require_fulfillment_signal=bool(require_fulfillment_signal)
            ):
                continue
            key = (t, d, s, sig)
            if key in item_seen:
                continue
            item_seen.add(key)
            row = {"类型": t, "单条提炼": s, "原始维度": d}
            if sig:
                row["信号类型"] = sig
            target["items"].append(row)
    return out


def internal_to_voc_items(
    internal: list[dict],
    chunk: list[dict],
    *,
    allowed_types: set[str] | None = None,
) -> list[dict]:
    allowed = allowed_types if allowed_types is not None else ALLOWED_TYPES
    by_id = {c["review_id"]: c for c in chunk}
    out = []
    seen = set()
    for entry in internal:
        rid = entry.get("review_id")
        src = by_id.get(rid)
        if not src:
            continue
        for ex in entry.get("items") or []:
            t = str(ex.get("类型") or "").strip()
            d = str(ex.get("原始维度") or "").strip()
            s = str(ex.get("单条提炼") or "").strip()
            sig = str(ex.get("信号类型") or "").strip()
            if t not in allowed or not d or not s:
                continue
            key = (rid, t, d, s, sig)
            if key in seen:
                continue
            seen.add(key)
            row = {
                "review_row": src["review_row"],
                "review_id": rid,
                "review_text": src.get("review_text") or "",
                "review_title": src.get("title") or "",
                "review_content": src.get("content") or "",
                "item_type": t,
                "dimension": d,
                "extracted_summary": s,
                "merged_dimension": d,
            }
            if sig:
                row["signal_type"] = sig
            out.append(row)
    return out
