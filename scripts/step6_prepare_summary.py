# -*- coding: utf-8 -*-
"""
V5 Step 6: prepare one-shot Review Intelligence AI input from normalized summary.
Writes review_intelligence/; invalidates stale MODEL_OUTPUT via input_hash.
Includes Python-prepared 消费人群深度分析 block.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import (
    INTELLIGENCE_DIR_NAME,
    INTELLIGENCE_SCHEMA_VERSION,
    SKILL_VERSION_NUMBER,
)
from lib.intelligence_codec import (
    build_signal_block,
    build_stats_block,
    compute_intelligence_input_hash,
)
from lib.io_util import (
    is_model_output_placeholder,
    read_json,
    read_text,
    render_template,
    skill_root,
    write_json,
    write_model_output_placeholder,
)
from lib.segment_stats import build_segment_analysis, build_segment_block
from lib.statistics import aggregate_statistics


def _analyzed_reviews(meta: dict) -> int:
    for key in ("analyzed_reviews", "ai_reviews"):
        if meta.get(key) is not None:
            return int(meta.get(key) or 0)
    return int(meta.get("total_reviews") or 0)


def _load_normalized_items(workdir: Path) -> list[dict]:
    extract = workdir / "extract_items.json"
    mappings = workdir / "normalize_mappings.json"
    if extract.exists() and mappings.exists():
        items = read_json(extract)
        if isinstance(items, list) and items and any(it.get("merged_dimension") for it in items):
            return items
    raise SystemExit(
        "缺少 AI 归一结果。请先：\n"
        "  python scripts/step4_prepare_normalize.py --workdir ...\n"
        "  # 填写 normalize_batches/*/MODEL_OUTPUT.json\n"
        "  python scripts/step5_ingest_normalize.py --workdir ..."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="V5 prepare Review Intelligence AI input")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument(
        "--force-reset",
        action="store_true",
        help="丢弃已填写的 review_intelligence/MODEL_OUTPUT.json",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    items = _load_normalized_items(workdir)
    analyzed = _analyzed_reviews(meta)
    total_reviews = int(meta.get("total_reviews") or 0)

    summary_rows = aggregate_statistics(items, analyzed, consolidate=False)
    write_json(workdir / "summary.json", summary_rows)

    segment_analysis = build_segment_analysis(items, analyzed)
    # Strip review_rows from persisted segments for smaller JSON (keep in comparisons via n)
    persist_seg = {
        "analyzed_reviews": segment_analysis.get("analyzed_reviews"),
        "known_segments": segment_analysis.get("known_segments"),
        "rules": segment_analysis.get("rules"),
        "segments": [
            {k: v for k, v in s.items() if k != "review_rows"}
            for s in (segment_analysis.get("segments") or [])
        ],
        "comparisons": segment_analysis.get("comparisons") or [],
    }
    write_json(workdir / "segment_analysis.json", persist_seg)

    stats_block = build_stats_block(summary_rows, top_n=max(1, int(args.top_n)))
    signal_block = build_signal_block(items, top_n=max(1, int(args.top_n)))
    segment_block = build_segment_block(segment_analysis)
    prompts = skill_root() / "prompts"
    system_tpl = read_text(prompts / "overview_summary_system.md")
    user_tpl = read_text(prompts / "overview_summary_user.md")
    user_msg = render_template(
        user_tpl,
        {
            "total_reviews": str(total_reviews),
            "analyzed_reviews": str(analyzed),
            "stats_block": stats_block,
            "signal_block": signal_block,
            "segment_block": segment_block,
        },
    )

    input_hash = compute_intelligence_input_hash(
        system_prompt=system_tpl,
        user_prompt=user_msg,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
    )

    sdir = workdir / INTELLIGENCE_DIR_NAME
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "system.md").write_text(system_tpl, encoding="utf-8")
    (sdir / "user.md").write_text(user_msg, encoding="utf-8")
    write_json(sdir / "segment_analysis.json", persist_seg)

    meta_path = sdir / "input_meta.json"
    prev_hash = ""
    if meta_path.exists():
        try:
            prev = read_json(meta_path)
            prev_hash = str(prev.get("input_hash") or "")
        except Exception:
            prev_hash = ""

    write_json(
        meta_path,
        {
            "input_hash": input_hash,
            "skill_version": SKILL_VERSION_NUMBER,
            "schema_version": INTELLIGENCE_SCHEMA_VERSION,
            "total_reviews": total_reviews,
            "analyzed_reviews": analyzed,
            "dimensions": len(summary_rows),
            "segments": len(segment_analysis.get("known_segments") or []),
            "top_n": int(args.top_n),
        },
    )

    mop = sdir / "MODEL_OUTPUT.json"
    hash_changed = bool(prev_hash) and prev_hash != input_hash
    force = bool(args.force_reset) or hash_changed
    preserved = write_model_output_placeholder(mop, force_reset=force)
    if hash_changed and not args.force_reset:
        if not is_model_output_placeholder(mop):
            write_model_output_placeholder(mop, force_reset=True)
            preserved = False

    meta["review_intelligence"] = {"path": INTELLIGENCE_DIR_NAME, "input_hash": input_hash}
    meta["overview_summary"] = {"path": INTELLIGENCE_DIR_NAME, "alias_of": "review_intelligence"}
    meta["segment_analysis"] = {"path": "segment_analysis.json"}
    write_json(workdir / "meta.json", meta)

    print(f"workdir={workdir}")
    print(
        f"summary_dimensions={len(summary_rows)} analyzed_reviews={analyzed} "
        f"segments={len(segment_analysis.get('known_segments') or [])}"
    )
    print(f"review_intelligence={sdir}")
    print(f"input_hash={input_hash[:16]}…")
    if hash_changed:
        print("stale_model_output=invalidated (input_hash changed)")
    elif preserved:
        print("preserved_model_output=yes (use --force-reset to discard)")
    print("NEXT: Fill review_intelligence/MODEL_OUTPUT.json（含 segment_intelligence）")
    print("THEN: python scripts/step7_finalize.py --workdir ... --output ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
