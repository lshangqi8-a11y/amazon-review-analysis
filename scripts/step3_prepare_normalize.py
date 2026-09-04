# -*- coding: utf-8 -*-
"""
Step 3 (Python): build one-shot normalize prompt from extract_items.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.io_util import format_product, read_json, read_text, render_template, skill_root, write_json
from lib.normalize_codec import build_normalize_input_rows, build_normalize_voc_items_block


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare one-shot normalize prompt")
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    items = read_json(workdir / "extract_items.json")
    if not items:
        write_json(workdir / "normalize_input_rows.json", [])
        ndir = workdir / "normalize"
        ndir.mkdir(parents=True, exist_ok=True)
        (ndir / "SKIP.txt").write_text("无提炼结果，跳过归一。直接运行 step4_finalize.py\n", encoding="utf-8")
        print("no items; skip normalize")
        return 0

    rows = build_normalize_input_rows(items)
    block = build_normalize_voc_items_block(rows)
    prompts = skill_root() / "prompts"
    system_tpl = read_text(prompts / "normalize_system.md")
    user_tpl = read_text(prompts / "normalize_user.md")
    user_msg = render_template(
        user_tpl,
        {
            "product_name": format_product(meta.get("product_name")),
            "product_category": format_product(meta.get("product_category")),
            "voc_items": block,
        },
    )

    ndir = workdir / "normalize"
    ndir.mkdir(parents=True, exist_ok=True)
    (ndir / "system.md").write_text(system_tpl, encoding="utf-8")
    (ndir / "user.md").write_text(user_msg, encoding="utf-8")
    write_json(workdir / "normalize_input_rows.json", rows)
    (ndir / "MODEL_OUTPUT.json").write_text(
        "/* Agent: call model ONCE with system.md + user.md, save STRICT JSON here */\n",
        encoding="utf-8",
    )
    print(f"unique_raw_dimensions={len(rows)}")
    print(f"normalize_dir={ndir}")
    print("NEXT: Agent fills normalize/MODEL_OUTPUT.json (one shot), then step4_finalize.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
