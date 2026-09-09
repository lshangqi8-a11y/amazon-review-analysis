# -*- coding: utf-8 -*-
"""
V4 Step 4: aggregate eight-dim stats + prepare one-shot overview summary AI batch.
Does not require product name / category.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.io_util import read_json, read_text, render_template, skill_root, write_json
from lib.statistics import aggregate_statistics
from lib.summary_codec import build_stats_block


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 prepare one-shot overview AI summary")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--top-n", type=int, default=8)
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    persona = read_json(workdir / "persona_items.json")
    fulfillment = read_json(workdir / "fulfillment_items.json")
    if not isinstance(persona, list) or not isinstance(fulfillment, list):
        raise SystemExit("persona_items.json / fulfillment_items.json 必须是数组")

    items = list(persona) + list(fulfillment)
    write_json(workdir / "extract_items.json", items)
    total_reviews = int(meta.get("total_reviews") or 0)
    summary_rows = aggregate_statistics(items, total_reviews)
    write_json(workdir / "summary.json", summary_rows)

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
    (sdir / "MODEL_OUTPUT.json").write_text(
        "/* Agent: call model with system.md + user.md, save STRICT JSON here */\n",
        encoding="utf-8",
    )

    meta["overview_summary"] = {"path": "overview_summary"}
    write_json(workdir / "meta.json", meta)

    print(f"workdir={workdir}")
    print(f"summary_dimensions={len(summary_rows)} total_reviews={total_reviews}")
    print(f"overview_summary={sdir}")
    print("NEXT: Fill overview_summary/MODEL_OUTPUT.json (八维全量 AI 总结，无需产品名/类目)")
    print("THEN: python scripts/step5_finalize.py --workdir ... --output ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
