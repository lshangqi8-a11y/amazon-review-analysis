# -*- coding: utf-8 -*-
"""
V3 Step 4: merge persona + fulfillment → stats → Excel overview/result.
No AI normalize pass: labels come from dual-pass extract + gatekeep.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.excel_io import write_analysis_workbook
from lib.io_util import read_json, write_json
from lib.statistics import aggregate_statistics


def main() -> int:
    parser = argparse.ArgumentParser(description="V3 finalize analysis workbook")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--output", default="")
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
    input_file = Path(meta["input_file"])
    summary_rows = aggregate_statistics(items, total_reviews)
    write_json(workdir / "summary.json", summary_rows)

    out = Path(args.output).resolve() if args.output else workdir / "评论洞察分析结果.xlsx"
    excel_meta = write_analysis_workbook(
        input_file,
        out,
        summary_rows=summary_rows,
        product_name=meta.get("product_name") or "",
        product_category=meta.get("product_category") or "",
        total_reviews=total_reviews,
        voc_items=len(items),
    )

    result = {
        "skill_version": "v3",
        "output_file": str(out),
        "total_reviews": total_reviews,
        "persona_items": len(persona),
        "fulfillment_items": len(fulfillment),
        "voc_items": len(items),
        "dimensions": len(summary_rows),
        "excel": excel_meta,
    }
    write_json(workdir / "result.json", result)
    print(f"output_file={out}")
    print(
        f"total_reviews={total_reviews} persona={len(persona)} "
        f"fulfillment={len(fulfillment)} dimensions={len(summary_rows)}"
    )
    print(f"sheets={excel_meta.get('sheetnames')}")
    print(f"charts={excel_meta.get('chart_count')} titles={excel_meta.get('chart_titles')}")
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
