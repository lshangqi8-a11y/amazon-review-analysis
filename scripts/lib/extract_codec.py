# -*- coding: utf-8 -*-
"""Extract JSON parse/validate → voc items (deterministic)."""
from __future__ import annotations

import json
import re

from .constants import ALLOWED_TYPES


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


def extract_item_fields(ex: dict) -> tuple[str, str, str]:
    return (
        str(ex.get("类型") or "").strip(),
        str(ex.get("原始维度") or "").strip(),
        str(ex.get("单条提炼") or "").strip(),
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


def validate_extract_payload(payload, expected_ids: set[str]) -> str:
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
            t, d, s = extract_item_fields(ex)
            if not t or not d or not s:
                return f"{rid} 的 item 必须包含中文字段：类型/单条提炼/原始维度"
            if t not in ALLOWED_TYPES:
                return f"{rid} 存在非法类型：{t}"
    missing = expected_ids - found_set
    if missing:
        return f"抽取结果缺少 review_id：{', '.join(sorted(missing)[:8])}"
    extra = found_set - expected_ids
    if extra:
        return f"抽取结果含未知 review_id：{', '.join(sorted(extra)[:8])}"
    if len(found_set) != len(expected_ids):
        return f"抽取结果 review_id 数量不一致：期望 {len(expected_ids)}，实际 {len(found_set)}"
    return ""


def to_internal_voc_payload(payload, expected_ids: set[str] | None = None) -> list[dict]:
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
        item_seen = {(i["类型"], i["原始维度"], i["单条提炼"]) for i in target["items"]}
        for ex in entry.get("items") or []:
            if not isinstance(ex, dict):
                continue
            t, d, s = extract_item_fields(ex)
            if t not in ALLOWED_TYPES or not d or not s:
                continue
            key = (t, d, s)
            if key in item_seen:
                continue
            item_seen.add(key)
            target["items"].append({"类型": t, "单条提炼": s, "原始维度": d})
    return out


def internal_to_voc_items(internal: list[dict], chunk: list[dict]) -> list[dict]:
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
            if t not in ALLOWED_TYPES or not d or not s:
                continue
            key = (rid, t, d, s)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
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
            )
    return out
