# -*- coding: utf-8 -*-
"""
Step 1 (Python): read Excel → batch reviews → write AI-ready prompt files.

Usage:
  python step1_prepare_extract.py --input reviews.xlsx --workdir ./run1 \\
      [--product-name NAME] [--product-category CAT] [--sheet SHEET]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import EXTRACT_CHUNK_LIMIT
from lib.excel_io import (
    build_reviews_block,
    count_and_load_reviews,
    resolve_review_columns,
)
from lib.io_util import format_product, read_text, render_template, skill_root, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare extract batches for Agent AI")
    parser.add_argument("--input", required=True, help="Input xlsx path")
    parser.add_argument("--workdir", required=True, help="Working directory for this run")
    parser.add_argument("--product-name", default="")
    parser.add_argument("--product-category", default="")
    parser.add_argument("--sheet", default="")
    parser.add_argument("--title-column", default="")
    parser.add_argument("--content-column", default="")
    parser.add_argument("--chunk-size", type=int, default=EXTRACT_CHUNK_LIMIT)
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    workdir = Path(args.workdir).resolve()
    if not input_path.exists():
        raise SystemExit(f"输入文件不存在：{input_path}")
    if input_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise SystemExit("输入必须是 xlsx")

    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    sheet, title_col, content_col = resolve_review_columns(
        input_path,
        args.sheet or None,
        title_column=args.title_column or None,
        content_column=args.content_column or None,
    )
    reviews = count_and_load_reviews(
        input_path, sheet, content_column=content_col, title_column=title_col
    )
    ai_reviews = [r for r in reviews if not r.get("skip_ai")]
    product_name = format_product(args.product_name)
    product_category = format_product(args.product_category)

    prompts = skill_root() / "prompts"
    system_tpl = read_text(prompts / "extract_system.md")
    user_tpl = read_text(prompts / "extract_user.md")

    batches_dir = workdir / "extract_batches"
    batches_dir.mkdir(parents=True)
    chunk_size = max(1, int(args.chunk_size))
    batch_metas = []

    for i in range(0, len(ai_reviews), chunk_size):
        chunk = ai_reviews[i : i + chunk_size]
        batch_no = i // chunk_size + 1
        batch_id = f"batch_{batch_no:04d}"
        bdir = batches_dir / batch_id
        bdir.mkdir(parents=True)
        block = build_reviews_block(chunk)
        user_msg = render_template(
            user_tpl,
            {
                "product_name": product_name,
                "product_category": product_category,
                "reviews": block,
                "reviews_block": block,
            },
        )
        (bdir / "system.md").write_text(system_tpl, encoding="utf-8")
        (bdir / "user.md").write_text(user_msg, encoding="utf-8")
        write_json(
            bdir / "expected_ids.json",
            {"review_ids": [r["review_id"] for r in chunk], "reviews": chunk},
        )
        # Placeholder for Agent to fill
        (bdir / "MODEL_OUTPUT.json").write_text(
            "/* Agent: call model with system.md + user.md, save STRICT JSON here */\n",
            encoding="utf-8",
        )
        batch_metas.append(
            {
                "batch_id": batch_id,
                "review_count": len(chunk),
                "path": str(bdir.relative_to(workdir)).replace("\\", "/"),
            }
        )

    write_json(
        workdir / "meta.json",
        {
            "input_file": str(input_path),
            "sheet_name": sheet,
            "title_column": title_col,
            "content_column": content_col,
            "product_name": args.product_name or "",
            "product_category": args.product_category or "",
            "total_reviews": len(reviews),
            "ai_reviews": len(ai_reviews),
            "empty_reviews": len(reviews) - len(ai_reviews),
            "chunk_size": chunk_size,
            "extract_batches": batch_metas,
        },
    )
    write_json(workdir / "reviews.json", reviews)

    print(f"workdir={workdir}")
    print(f"total_reviews={len(reviews)} ai_reviews={len(ai_reviews)} batches={len(batch_metas)}")
    for b in batch_metas:
        print(f"  - {b['path']} ({b['review_count']} reviews)")
    print("NEXT: For each batch, Agent fills MODEL_OUTPUT.json using system.md + user.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
