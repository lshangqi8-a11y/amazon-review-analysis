# -*- coding: utf-8 -*-
"""
V5 Step 4: prepare AI dimension-normalize batches (one folder per VOC type).
Semantic refs: up to 3 per raw dimension from different reviews.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import VOC_TYPES
from lib.io_util import (
    is_model_output_placeholder,
    read_json,
    read_text,
    render_template,
    skill_root,
    write_json,
    write_model_output_placeholder,
)
from lib.normalize_codec import (
    build_normalize_input_rows,
    build_normalize_voc_items_block,
    type_dir_name,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 prepare AI dimension normalize batches")
    parser.add_argument("--workdir", required=True)
    parser.add_argument(
        "--force-reset",
        action="store_true",
        help="丢弃已填写的 normalize MODEL_OUTPUT，全部重置为占位符",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    persona = read_json(workdir / "persona_items.json")
    fulfillment = read_json(workdir / "fulfillment_items.json")
    if not isinstance(persona, list) or not isinstance(fulfillment, list):
        raise SystemExit("persona_items.json / fulfillment_items.json 必须是数组")

    items = list(persona) + list(fulfillment)
    write_json(workdir / "extract_items_raw.json", items)

    all_rows = build_normalize_input_rows(items)
    if not all_rows:
        raise SystemExit("没有可归一的维度（extract 为空？）")

    prompts = skill_root() / "prompts"
    system_tpl = read_text(prompts / "normalize_system.md")
    user_tpl = read_text(prompts / "normalize_user.md")

    root = workdir / "normalize_batches"
    preserved: dict[str, str] = {}
    if root.exists():
        if not args.force_reset:
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                mop = child / "MODEL_OUTPUT.json"
                if mop.is_file() and not is_model_output_placeholder(mop):
                    preserved[child.name] = mop.read_text(encoding="utf-8")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    batch_meta = []
    kept = 0
    for t in VOC_TYPES:
        rows = [r for r in all_rows if r.get("类型") == t]
        if not rows:
            continue
        dirname = type_dir_name(t)
        bdir = root / dirname
        bdir.mkdir(parents=True, exist_ok=True)
        expected = [{"类型": r["类型"], "原始维度": r["原始维度"]} for r in rows]
        write_json(bdir / "expected_pairs.json", expected)
        write_json(bdir / "input_rows.json", rows)
        user_msg = render_template(
            user_tpl,
            {"voc_items": build_normalize_voc_items_block(rows)},
        )
        (bdir / "system.md").write_text(system_tpl, encoding="utf-8")
        (bdir / "user.md").write_text(user_msg, encoding="utf-8")
        if dirname in preserved and not args.force_reset:
            (bdir / "MODEL_OUTPUT.json").write_text(preserved[dirname], encoding="utf-8")
            kept += 1
        else:
            write_model_output_placeholder(bdir / "MODEL_OUTPUT.json", force_reset=True)
        batch_meta.append(
            {
                "item_type": t,
                "path": f"normalize_batches/{dirname}",
                "raw_dimensions": len(rows),
            }
        )
        print(f"normalize_batch type={t} raw_dims={len(rows)} path={bdir}")

    meta["normalize_batches"] = batch_meta
    meta["normalize_raw_dimensions"] = len(all_rows)
    write_json(workdir / "meta.json", meta)

    print(f"workdir={workdir}")
    print(f"normalize_batches={len(batch_meta)} raw_dimensions={len(all_rows)}")
    if kept:
        print(f"preserved_model_outputs={kept} (use --force-reset to discard)")
    print("NEXT: 串行填写各 normalize_batches/*/MODEL_OUTPUT.json（禁止子代理并行）")
    print("THEN: python scripts/step5_ingest_normalize.py --workdir ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
