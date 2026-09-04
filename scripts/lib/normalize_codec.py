# -*- coding: utf-8 -*-
"""Normalize mapping parse/validate (deterministic)."""
from __future__ import annotations

import json

from .constants import ALLOWED_TYPES
from .extract_codec import parse_json_content


def build_normalize_input_rows(items: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], dict] = {}
    for it in items:
        t = (it.get("item_type") or "").strip()
        raw = (it.get("dimension") or "").strip()
        if t not in ALLOWED_TYPES or not raw:
            continue
        key = (t, raw)
        row_no = int(it.get("review_row") or 0)
        prev = groups.get(key)
        if prev is None or row_no < int(prev.get("_row") or 10**9):
            groups[key] = {
                "类型": t,
                "原始维度": raw,
                "语义参考": (it.get("extracted_summary") or "").strip(),
                "_row": row_no,
            }
    rows = sorted(groups.values(), key=lambda x: (x["类型"], x["原始维度"]))
    for r in rows:
        r.pop("_row", None)
    return rows


def build_normalize_voc_items_block(rows: list[dict]) -> str:
    payload = [
        {"类型": r.get("类型") or "", "原始维度": r.get("原始维度") or "", "语义参考": r.get("语义参考") or ""}
        for r in rows
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_normalize_payload(payload) -> list[dict]:
    rows = []
    if isinstance(payload, dict):
        for key in ("mappings", "归一结果", "mapping", "results"):
            if isinstance(payload.get(key), list):
                rows = payload.get(key)
                break
    elif isinstance(payload, list):
        rows = payload
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item_type = str(row.get("类型") or "").strip()
        raw = str(row.get("原始维度") or "").strip()
        std = str(row.get("标准维度") or "").strip()
        if item_type not in ALLOWED_TYPES or not raw or not std:
            continue
        out.append({"类型": item_type, "原始维度": raw, "标准维度": std})
    return out


def validate_normalize_mappings(mappings: list[dict], expected_pairs: set[tuple[str, str]]) -> str:
    if not isinstance(mappings, list) or not mappings:
        return "归一结果 mappings 为空"
    covered: set[tuple[str, str]] = set()
    for row in mappings:
        if not isinstance(row, dict):
            return "mappings 元素必须是对象"
        t = str(row.get("类型") or "").strip()
        raw = str(row.get("原始维度") or "").strip()
        std = str(row.get("标准维度") or "").strip()
        if t not in ALLOWED_TYPES:
            return f"归一结果存在非法类型：{t}"
        if not raw:
            return "归一结果存在空原始维度"
        if not std:
            return f"归一结果原始维度「{raw}」缺少标准维度"
        key = (t, raw)
        if key in covered:
            return f"原始维度重复映射：{t}/{raw}"
        covered.add(key)
    missing = expected_pairs - covered
    if missing:
        sample = ", ".join(f"{t}/{r}" for t, r in sorted(missing)[:8])
        return f"归一结果缺少原始维度映射：{sample}"
    extra = covered - expected_pairs
    if extra:
        sample = ", ".join(f"{t}/{r}" for t, r in sorted(extra)[:8])
        return f"归一结果含未知原始维度：{sample}"
    return ""


def apply_mappings(items: list[dict], mappings: list[dict]) -> list[dict]:
    mapping = {(m["类型"], m["原始维度"]): m["标准维度"] for m in mappings}
    for it in items:
        t = (it.get("item_type") or "").strip()
        raw = (it.get("dimension") or "").strip()
        if not t or not raw:
            continue
        if (t, raw) not in mapping:
            raise RuntimeError(f"维度归一缺少映射：{t}/{raw}")
        it["merged_dimension"] = mapping[(t, raw)]
    return items


def parse_and_validate_normalize(raw_text: str, expected_pairs: set[tuple[str, str]]) -> list[dict]:
    payload = parse_json_content(raw_text)
    if payload is None:
        raise RuntimeError("维度归一返回无法解析为 JSON")
    mappings = parse_normalize_payload(payload)
    err = validate_normalize_mappings(mappings, expected_pairs)
    if err:
        raise RuntimeError(f"维度归一完整性失败：{err}")
    return mappings
