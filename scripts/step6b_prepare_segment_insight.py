# -*- coding: utf-8 -*-
"""
V6 Step 6b: prepare one-shot consumer segment insight AI batch.
Depends on AI-normalized extract_items.json.
Product name/category from meta are injected only into this module's prompt.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.io_util import (
    read_json,
    read_text,
    render_template,
    skill_root,
    write_json,
    write_model_output_placeholder,
)
from lib.segment_stats import (
    analyzed_review_count,
    build_segment_stats_payload,
    format_segment_stats_block,
)


def _product_context(meta: dict) -> tuple[str, str]:
    """Display product fields for segment insight only; empty → 未提供."""
    name = str((meta or {}).get("product_name") or "").strip() or "未提供"
    category = str((meta or {}).get("product_category") or "").strip() or "未提供"
    return name, category


def _load_normalized_items(workdir: Path) -> list[dict]:
    extract = workdir / "extract_items.json"
    mappings = workdir / "normalize_mappings.json"
    if extract.exists() and mappings.exists():
        items = read_json(extract)
        if isinstance(items, list) and items and any(it.get("merged_dimension") for it in items):
            return items
    raise SystemExit(
        "缺少 AI 归一结果。请先完成 step4 → step5，再运行本步骤。"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="V6 prepare consumer segment insight")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument(
        "--network-capability",
        default="unknown",
        help="online | offline | unknown — 写入提示，供 Agent 选择 research status",
    )
    parser.add_argument(
        "--force-reset",
        action="store_true",
        help="丢弃已填写的 consumer_segment_insight/MODEL_OUTPUT.json",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    items = _load_normalized_items(workdir)
    analyzed = analyzed_review_count(meta, fallback_total=int(meta.get("total_reviews") or 0))
    product_name, product_category = _product_context(meta)

    stats = build_segment_stats_payload(items, analyzed, top_n=max(0, int(args.top_n)))
    write_json(workdir / "segment_stats.json", stats)
    stats_block = format_segment_stats_block(stats)

    net = str(args.network_capability or "unknown").strip().lower()
    if net == "online":
        net_hint = "当前环境可联网：若存在核心人群，应主动检索并 status=ok。"
    elif net == "offline":
        net_hint = "当前环境无联网：status=unavailable，sources 必须为空，不得伪造。"
    else:
        net_hint = (
            "由 Agent 自行判断联网能力："
            "可联网且有核心人群 → 应研究并 status=ok；"
            "无联网 → unavailable；无值得外研的人群 → skipped。"
        )

    prompts = skill_root() / "prompts"
    system_tpl = read_text(prompts / "segment_insight_system.md")
    user_tpl = read_text(prompts / "segment_insight_user.md")
    user_msg = render_template(
        user_tpl,
        {
            "product_name": product_name,
            "product_category": product_category,
            "stats_block": stats_block,
            "network_capability": net_hint,
        },
    )

    sdir = workdir / "consumer_segment_insight"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "system.md").write_text(system_tpl, encoding="utf-8")
    (sdir / "user.md").write_text(user_msg, encoding="utf-8")
    write_json(
        sdir / "input_meta.json",
        {
            "analyzed_reviews": analyzed,
            "segment_count": int(stats.get("segment_count") or 0),
            "top_n": int(args.top_n),
            "allowed_segments": [s.get("segment") for s in (stats.get("core_segments") or [])],
            "product_name": product_name,
            "product_category": product_category,
            "network_capability": net,
        },
    )
    preserved = write_model_output_placeholder(
        sdir / "MODEL_OUTPUT.json",
        force_reset=bool(args.force_reset),
    )

    meta["consumer_segment_insight"] = {"path": "consumer_segment_insight"}
    meta["analyzed_reviews"] = analyzed
    write_json(workdir / "meta.json", meta)

    print(f"workdir={workdir}")
    print(f"analyzed_reviews={analyzed} core_segments={stats.get('segment_count')}")
    print(f"consumer_segment_insight={sdir}")
    if preserved:
        print("preserved_model_output=yes (use --force-reset to discard)")
    print("NEXT: Fill consumer_segment_insight/MODEL_OUTPUT.json（可联网时必须做外部研究）")
    print("THEN: python scripts/step7_finalize.py --workdir ... --output ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
