# -*- coding: utf-8 -*-
"""
V4 Step 1: read Excel → write persona_batches + fulfillment_batches for dual-pass AI.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import EXTRACT_CHUNK_LIMIT
from lib.excel_io import (
    build_reviews_block,
    count_and_load_reviews,
    guess_product_fields,
    resolve_review_columns,
)
from lib.io_util import format_product, read_text, render_template, skill_root, write_json


def _looks_like_pipeline_workdir(workdir: Path) -> bool:
    meta_path = workdir / "meta.json"
    if not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(meta, dict):
        return False
    ver = str(meta.get("skill_version") or "")
    if not ver.startswith("v"):
        return False
    return bool(meta.get("persona_batches") or meta.get("pipeline"))


def _prepare_workdir(workdir: Path, *, force: bool) -> None:
    """
    Create workdir. Refuse to wipe unknown non-empty dirs unless --force.
    Previous pipeline workdirs (meta.json skill_version) may be replaced when force
    or when clearly ours; unknown content requires --force.
    """
    if not workdir.exists():
        workdir.mkdir(parents=True)
        return
    try:
        non_empty = any(workdir.iterdir())
    except OSError as exc:
        raise SystemExit(f"无法读取 workdir：{workdir} ({exc})") from exc
    if not non_empty:
        return
    ours = _looks_like_pipeline_workdir(workdir)
    if force or ours:
        shutil.rmtree(workdir)
        workdir.mkdir(parents=True)
        return
    raise SystemExit(
        f"workdir 已存在且非空，且不像本技能流水线目录：{workdir}\n"
        "请改用空目录，或对确认可覆盖的目录加上 --force。"
    )


def _write_pass_batches(
    *,
    workdir: Path,
    pass_name: str,
    system_name: str,
    user_name: str,
    ai_reviews: list[dict],
    chunk_size: int,
    product_name: str,
    product_category: str,
) -> list[dict]:
    prompts = skill_root() / "prompts"
    system_tpl = read_text(prompts / system_name)
    user_tpl = read_text(prompts / user_name)
    batches_dir = workdir / pass_name
    batches_dir.mkdir(parents=True)
    batch_metas: list[dict] = []
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
    return batch_metas


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 prepare dual-pass 8-dim extract batches")
    parser.add_argument("--input", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--product-name", default="")
    parser.add_argument("--product-category", default="")
    parser.add_argument("--sheet", default="")
    parser.add_argument("--title-column", default="")
    parser.add_argument("--content-column", default="")
    parser.add_argument("--chunk-size", type=int, default=EXTRACT_CHUNK_LIMIT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的非空 workdir（默认仅允许覆盖本流水线旧目录）",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    workdir = Path(args.workdir).resolve()
    if not input_path.exists():
        raise SystemExit(f"输入文件不存在：{input_path}")
    if input_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise SystemExit("输入必须是 xlsx")

    _prepare_workdir(workdir, force=bool(args.force))

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

    cli_name = (args.product_name or "").strip()
    cli_cat = (args.product_category or "").strip()
    auto_name, auto_cat = guess_product_fields(input_path, sheet)
    product_name_raw = cli_name or auto_name or ""
    product_category_raw = cli_cat or auto_cat or ""
    product_name = format_product(product_name_raw)
    product_category = format_product(product_category_raw)
    chunk_size = max(1, int(args.chunk_size))

    persona_batches = _write_pass_batches(
        workdir=workdir,
        pass_name="persona_batches",
        system_name="persona_system.md",
        user_name="persona_user.md",
        ai_reviews=ai_reviews,
        chunk_size=chunk_size,
        product_name=product_name,
        product_category=product_category,
    )
    fulfillment_batches = _write_pass_batches(
        workdir=workdir,
        pass_name="fulfillment_batches",
        system_name="fulfillment_system.md",
        user_name="fulfillment_user.md",
        ai_reviews=ai_reviews,
        chunk_size=chunk_size,
        product_name=product_name,
        product_category=product_category,
    )

    write_json(
        workdir / "meta.json",
        {
            "skill_version": "v4",
            "pipeline": "dual_pass_8dim",
            "input_file": str(input_path),
            "sheet_name": sheet,
            "title_column": title_col,
            "content_column": content_col,
            "product_name": product_name_raw,
            "product_category": product_category_raw,
            "product_name_source": ("cli" if cli_name else ("excel" if auto_name else "empty")),
            "product_category_source": ("cli" if cli_cat else ("excel" if auto_cat else "empty")),
            "total_reviews": len(reviews),
            "ai_reviews": len(ai_reviews),
            "empty_reviews": len(reviews) - len(ai_reviews),
            "chunk_size": chunk_size,
            "persona_batches": persona_batches,
            "fulfillment_batches": fulfillment_batches,
        },
    )
    write_json(workdir / "reviews.json", reviews)

    print(f"workdir={workdir}")
    print(f"skill_version=v4 total_reviews={len(reviews)} ai_reviews={len(ai_reviews)}")
    print(f"persona_batches={len(persona_batches)} fulfillment_batches={len(fulfillment_batches)}")
    print("NEXT: Fill persona_batches/*/MODEL_OUTPUT.json (Pass1 画像六维)")
    print("THEN: python scripts/step2_ingest_persona.py --workdir ...")
    print("THEN: Fill fulfillment_batches/*/MODEL_OUTPUT.json (Pass2 满意/未被满足)")
    print("THEN: python scripts/step3_ingest_fulfillment.py --workdir ...")
    print("THEN: python scripts/step4_finalize.py --workdir ... --output ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
