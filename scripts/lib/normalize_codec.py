# -*- coding: utf-8 -*-
"""V5 normalize mapping parse/validate (AI-driven dimension merge)."""
from __future__ import annotations

import json
import re
from collections import defaultdict

from .constants import ALLOWED_TYPES, NORMALIZE_SEMANTIC_REF_LIMIT, VOC_TYPES
from .extract_codec import parse_json_content

_SAFE_DIR = re.compile(r"[^\w\u4e00-\u9fff\-]+")


def type_dir_name(item_type: str) -> str:
    """Filesystem-safe folder name for a VOC type."""
    t = str(item_type or "").strip() or "unknown"
    return _SAFE_DIR.sub("_", t)


def _uniform_pick_texts(candidates: list[tuple[int, str]], *, max_n: int) -> list[str]:
    """
    Deterministic uniform sample of (review_row, text) pairs.
    Prefer different reviews; max_n texts.
    """
    if max_n <= 0 or not candidates:
        return []
    # unique by review_row, keep first text for that row
    by_row: dict[int, str] = {}
    for rid, text in sorted(candidates, key=lambda x: x[0]):
        text = (text or "").strip()
        if not text or rid in by_row:
            continue
        by_row[rid] = text
    rows = sorted(by_row.items(), key=lambda x: x[0])
    if len(rows) <= max_n:
        return [t for _, t in rows]
    # Pick at evenly spaced percentiles (0%, 25%, 50%, 75%, 100% style for max_n)
    n = len(rows)
    idxs: list[int] = []
    for i in range(max_n):
        if max_n == 1:
            pos = 0
        else:
            pos = int(round(i * (n - 1) / (max_n - 1)))
        idxs.append(pos)
    # de-dupe indices while preserving order
    seen_i: set[int] = set()
    out: list[str] = []
    for i in idxs:
        if i in seen_i:
            continue
        seen_i.add(i)
        out.append(rows[i][1])
    return out


def build_normalize_input_rows(items: list[dict]) -> list[dict]:
    """Unique (类型, 原始维度) with up to 3 semantic refs + mention count."""
    candidates: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    counts: dict[tuple[str, str], set[int]] = defaultdict(set)
    for it in items:
        t = (it.get("item_type") or "").strip()
        raw = (it.get("dimension") or "").strip()
        if t not in ALLOWED_TYPES or not raw:
            continue
        key = (t, raw)
        rid = int(it.get("review_row") or 0)
        counts[key].add(rid)
        text = (it.get("extracted_summary") or "").strip()
        if text:
            candidates[key].append((rid, text))

    rows = []
    for key, cands in candidates.items():
        t, raw = key
        refs = _uniform_pick_texts(cands, max_n=NORMALIZE_SEMANTIC_REF_LIMIT)
        rows.append(
            {
                "类型": t,
                "原始维度": raw,
                "提及次数": len(counts.get(key) or []),
                "语义参考": refs,
            }
        )
    # Also include dims that somehow have counts but no text
    for key, rset in counts.items():
        if key in candidates:
            continue
        t, raw = key
        rows.append(
            {
                "类型": t,
                "原始维度": raw,
                "提及次数": len(rset),
                "语义参考": [],
            }
        )
    rows.sort(
        key=lambda x: (
            VOC_TYPES.index(x["类型"]) if x["类型"] in VOC_TYPES else 99,
            -int(x["提及次数"]),
            x["原始维度"],
        )
    )
    return rows


def build_normalize_voc_items_block(rows: list[dict]) -> str:
    payload = [
        {
            "类型": r.get("类型") or "",
            "原始维度": r.get("原始维度") or "",
            "提及次数": int(r.get("提及次数") or 0),
            "语义参考": list(r.get("语义参考") or []),
        }
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
        if std in {"其他", "综合问题", "质量问题", "用户体验", "产品质量", "产品功能", "整体表现"}:
            return f"标准维度禁止空泛标签：{std}"
        # Opposite-polarity vague buckets are also banned as std names
        if std in {"尺寸问题", "硬度问题", "重量问题", "安装问题", "松紧问题", "明暗问题"}:
            return f"标准维度禁止把相反改进动作合并为空泛属性：{std}"
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
    out = []
    for it in items:
        row = dict(it)
        t = (row.get("item_type") or "").strip()
        raw = (row.get("dimension") or "").strip()
        if not t or not raw:
            out.append(row)
            continue
        if (t, raw) not in mapping:
            raise RuntimeError(f"维度归一缺少映射：{t}/{raw}")
        row["merged_dimension"] = mapping[(t, raw)]
        out.append(row)
    return out


def parse_and_validate_normalize(raw_text: str, expected_pairs: set[tuple[str, str]]) -> list[dict]:
    payload = parse_json_content(raw_text)
    if payload is None:
        raise RuntimeError("维度归一返回无法解析为 JSON")
    mappings = parse_normalize_payload(payload)
    err = validate_normalize_mappings(mappings, expected_pairs)
    if err:
        raise RuntimeError(f"维度归一完整性失败：{err}")
    return mappings


def mapping_compression_stats(mappings: list[dict]) -> dict[str, dict]:
    """raw→std compression per type (for logs / meta)."""
    by_type: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"raw": set(), "std": set()})
    for m in mappings:
        t = m["类型"]
        by_type[t]["raw"].add(m["原始维度"])
        by_type[t]["std"].add(m["标准维度"])
    return {
        t: {"raw": len(v["raw"]), "std": len(v["std"])}
        for t, v in by_type.items()
    }
