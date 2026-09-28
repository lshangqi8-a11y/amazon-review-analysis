# -*- coding: utf-8 -*-
"""
V4 Step 6: prepare one-shot overview summary AI batch from normalized summary.
Does not require product name / category.
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
from lib.statistics import aggregate_statistics
from lib.summary_codec import build_stats_block


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
    parser = argparse.ArgumentParser(description="V4 prepare one-shot overview AI summary")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument(
        "--force-reset",
        action="store_true",
        help="丢弃已填写的 overview_summary/MODEL_OUTPUT.json",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    items = _load_normalized_items(workdir)
    total_reviews = int(meta.get("total_reviews") or 0)

    summary_path = workdir / "summary.json"
    if summary_path.exists():
        summary_rows = read_json(summary_path)
        if not isinstance(summary_rows, list):
            raise SystemExit("summary.json 必须是数组")
    else:
        summary_rows = aggregate_statistics(items, total_reviews, consolidate=False)
        write_json(summary_path, summary_rows)

    stats_block = build_stats_block(summary_rows, top_n=max(1, int(args.top_n)))
    prompts = skill_root() / "prompts"
    system_tpl = read_text(prompts / "overview_summary_system.md")
    user_tpl = read_text(prompts / "overview_summary_user.md")
    user_msg = render_template(
        user_tpl,
        {
            "total_reviews": str(total_reviews),
            "stats_block": stats_block,
        },
    )

    sdir = workdir / "overview_summary"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "system.md").write_text(system_tpl, encoding="utf-8")
    (sdir / "user.md").write_text(user_msg, encoding="utf-8")
    write_json(
        sdir / "input_meta.json",
        {
            "total_reviews": total_reviews,
            "dimensions": len(summary_rows),
            "top_n": int(args.top_n),
        },
    )
    preserved = write_model_output_placeholder(
        sdir / "MODEL_OUTPUT.json",
        force_reset=bool(args.force_reset),
    )

    meta["overview_summary"] = {"path": "overview_summary"}
    write_json(workdir / "meta.json", meta)

    print(f"workdir={workdir}")
    print(f"summary_dimensions={len(summary_rows)} total_reviews={total_reviews}")
    print(f"overview_summary={sdir}")
    if preserved:
        print("preserved_model_output=yes (use --force-reset to discard)")
    print("NEXT: Fill overview_summary/MODEL_OUTPUT.json（基于归一后的八维汇总）")
    print("THEN: python scripts/step6b_prepare_segment_insight.py --workdir ...")
    print("THEN: Fill consumer_segment_insight/MODEL_OUTPUT.json")
    print("THEN: python scripts/step7_finalize.py --workdir ... --output ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
