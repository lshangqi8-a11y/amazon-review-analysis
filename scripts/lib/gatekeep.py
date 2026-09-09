# -*- coding: utf-8 -*-
"""V4 soft gatekeepers after AI extract (drop clearly misplaced items)."""
from __future__ import annotations

import re

_SUITABILITY = re.compile(r"(适合|不适合|仅限|不推荐|太.+不适合)")
# 品类中立：只列"明确的负面/故障词"，覆盖服装/电子/美妆/食品/家居等，避免单字误命中。
_FAULT = re.compile(
    r"(易脏|易坏|难装|难清洗|难清洁|不耐用|不结实|断裂|脱落|掉色|褪色|起球|开线|缩水|变形"
    r"|失灵|死机|卡顿|发烫|过敏|刺激|变质|过期|发霉|漏水|泄漏|坏掉|损坏|安全隐患|刮花|掉漆|生锈|异味)"
)
_MOTIVE_CUE = re.compile(
    r"(因.+而买|因为.+才选|冲着|bought because|chose because|attracted by|as a gift|买来当礼物|为了送礼)",
    re.I,
)
# 品类中立的地点词：家居/出行/户外/运动/工作/宠物等通用场所，用于「地点 vs 时刻」互斥判断。
_PLACE_HINT = re.compile(
    r"(厨房|台面|水槽|庭院|户外|室内|车内|办公室|浴室|卧室|客厅|阳台|健身房|餐厅|学校|医院"
    r"|工地|海边|山上|旅途中|窝里|笼子|床上|桌面|身上|kitchen|counter|yard|outdoor|indoor"
    r"|office|bathroom|bedroom|gym|car)",
    re.I,
)
# 品类中立的时间词，用于「地点 vs 时刻」互斥判断。
_TIME_HINT = re.compile(
    r"(每天|每天都|一天|早晨|早上|夜间|晚上|周末|工作日|碎片|睡前|起床|饭后|出门"
    r"|everyday|daily|night|morning|evening|weekend|twice a day|after work)",
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
        elif t in {"使用地点", "使用时刻", "使用场景"} and _FAULT.search(d):
            reason = f"{t}含体验/故障词"
        elif t == "使用地点" and _TIME_HINT.search(d) and not _PLACE_HINT.search(d):
            reason = "地点像时刻标签"
        elif t == "使用时刻" and _PLACE_HINT.search(d) and not _TIME_HINT.search(d):
            reason = "时刻像地点标签"
        elif t == "购买动机" and not _MOTIVE_CUE.search(blob):
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
        if t not in {"用户满意", "未被满足"}:
            dropped.append({**it, "drop_reason": "非满足类型"})
            continue
        d = str(it.get("dimension") or "").strip()
        if d in {"质量问题", "用户体验", "综合问题", "其他", "体验好", "质量差"}:
            dropped.append({**it, "drop_reason": "过宽空标签"})
            continue
        kept.append(it)
    return kept, dropped
