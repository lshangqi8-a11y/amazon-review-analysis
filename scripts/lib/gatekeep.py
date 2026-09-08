# -*- coding: utf-8 -*-
"""V3 soft gatekeepers after AI extract (drop clearly misplaced items)."""
from __future__ import annotations

import re

_SUITABILITY = re.compile(r"(适合|不适合|仅限|不推荐|太.+不适合)")
_SCENE_FAULT = re.compile(r"(易脏|难装|断裂|不耐|故障|漏|坏掉|损坏|说明书|安全隐患)")
_MOTIVE_CUE = re.compile(
    r"(因.+而买|因为.+才选|冲着|bought because|chose because|attracted by|as a gift|买来当礼物|为了送礼)",
    re.I,
)


def gatekeep_persona_items(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (kept, dropped)."""
    kept: list[dict] = []
    dropped: list[dict] = []
    for it in items:
        t = str(it.get("item_type") or "")
        d = str(it.get("dimension") or "")
        s = str(it.get("extracted_summary") or "")
        blob = d + s
        reason = ""
        if t == "消费人群" and _SUITABILITY.search(blob):
            reason = "人群含适性判断"
        elif t == "使用场景" and _SCENE_FAULT.search(blob):
            reason = "场景含体验/故障词"
        elif t == "购买动机" and not _MOTIVE_CUE.search(blob):
            # soft: if dimension looks like post-purchase value only
            if re.search(r"(不值|后悔|性价比低|用后)", blob):
                reason = "动机像购后评价"
        if reason:
            dropped.append({**it, "drop_reason": reason})
        else:
            kept.append(it)
    return kept, dropped


def gatekeep_fulfillment_items(items: list[dict]) -> tuple[list[dict], list[dict]]:
    kept: list[dict] = []
    dropped: list[dict] = []
    for it in items:
        t = str(it.get("item_type") or "")
        if t not in {"用户满意", "用户不满"}:
            dropped.append({**it, "drop_reason": "非满足类型"})
            continue
        d = str(it.get("dimension") or "").strip()
        if d in {"质量问题", "用户体验", "综合问题", "其他", "体验好", "质量差"}:
            dropped.append({**it, "drop_reason": "过宽空标签"})
            continue
        kept.append(it)
    return kept, dropped
