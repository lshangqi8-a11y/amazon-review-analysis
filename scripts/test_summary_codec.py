# -*- coding: utf-8 -*-
"""Unit tests for lib/summary_codec.py (Pass3 AI summary: build / parse / validate)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import VOC_TYPES
from lib.summary_codec import (
    build_stats_block,
    format_summary_text,
    parse_summary_output,
    validate_summary_payload,
)


def _row(item_type: str, dimension: str, count: int, total: int = 100) -> dict:
    return {
        "item_type": item_type,
        "dimension": dimension,
        "mention_count": count,
        "mention_rate": round(count / total * 100, 1),
        "representative_feedback": f"{dimension}的代表反馈",
    }


def _full_payload() -> dict:
    return {
        "sections": [
            {"title": t, "bullets": [f"{t}要点"]} for t in VOC_TYPES
        ]
    }


def test_build_stats_block_has_all_eight_sections() -> None:
    rows = [_row("消费人群", "幼犬", 28), _row("产品用途", "消耗精力", 18)]
    block = build_stats_block(rows)
    for t in VOC_TYPES:
        assert f"## {t}" in block, f"缺少小节：{t}"
    # 无数据的维度必须显式标注，而不是静默消失
    assert "（无统计条目）" in block
    assert "幼犬" in block and "28.0%" in block


def test_build_stats_block_respects_top_n() -> None:
    rows = [_row("用户满意", f"维度{i:02d}", 50 - i) for i in range(20)]
    block = build_stats_block(rows, top_n=3)
    assert "维度00" in block
    assert "维度02" in block
    # 第 4 名之后应被截断
    assert "维度03" not in block


def test_build_stats_block_truncates_long_feedback() -> None:
    row = _row("未被满足", "配件易损", 7)
    row["representative_feedback"] = "长" * 300
    block = build_stats_block([row])
    assert "…" in block
    # 节选应被截到 120 字符以内
    line = [ln for ln in block.splitlines() if ln.startswith("- 配件易损")][0]
    assert len(line) < 200


def test_build_stats_block_sorts_by_mention_count() -> None:
    rows = [_row("消费人群", "少数", 2), _row("消费人群", "多数", 30)]
    block = build_stats_block(rows)
    assert block.index("多数") < block.index("少数")


def test_validate_summary_payload_accepts_full() -> None:
    assert validate_summary_payload(_full_payload()) is None


def test_validate_summary_payload_rejects_missing_and_bad() -> None:
    # 缺维
    bad = {"sections": [{"title": "消费人群", "bullets": ["x"]}]}
    err = validate_summary_payload(bad)
    assert err and "缺少维" in err
    # 非法 title
    bad2 = {"sections": [{"title": "错误维度", "bullets": ["x"]} for _ in range(8)]}
    err2 = validate_summary_payload(bad2)
    assert err2 and "非法" in err2
    # 重复维
    dup = {"sections": [{"title": "消费人群", "bullets": ["x"]} for _ in range(8)]}
    err3 = validate_summary_payload(dup)
    assert err3 and "重复维" in err3
    # 空 bullet
    empty = _full_payload()
    empty["sections"][0]["bullets"] = [""]
    err4 = validate_summary_payload(empty)
    assert err4 and "非空字符串" in err4
    # 非对象
    assert validate_summary_payload("not a dict") is not None
    assert validate_summary_payload({}) is not None


def test_parse_summary_output_ok() -> None:
    import json

    text, err = parse_summary_output(json.dumps(_full_payload(), ensure_ascii=False))
    assert err is None
    assert text is not None
    assert "AI总结（全量）" in text
    for t in VOC_TYPES:
        assert f"【{t}】" in text


def test_parse_summary_output_placeholder_and_garbage() -> None:
    text, err = parse_summary_output("/* not filled */")
    assert text is None and err == "总结模型输出尚未填写"
    text2, err2 = parse_summary_output("")
    assert text2 is None and err2 == "总结模型输出尚未填写"
    text3, err3 = parse_summary_output("not json at all")
    assert text3 is None and err3 == "无法解析总结 JSON"


def test_format_summary_text_empty_bullets() -> None:
    payload = {"sections": [{"title": t, "bullets": []} for t in VOC_TYPES]}
    text = format_summary_text(payload)
    assert "证据不足，从略" in text
    assert format_summary_text({}) == ""
    assert format_summary_text({"sections": "nope"}) == ""


def run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok: {t.__name__}")
    print(f"SUMMARY_CODEC_TESTS_PASSED ({len(tests)})")


if __name__ == "__main__":
    run_all()
