# -*- coding: utf-8 -*-
"""
Step 4 (Python): validate normalize → stats → write 评论分析结果 Excel
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.excel_io import write_analysis_workbook
from lib.io_util import read_json, write_json
from lib.normalize_codec import apply_mappings, parse_and_validate_normalize
from lib.statistics import aggregate_statistics


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize analysis workbook")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--output", default="", help="Output xlsx path (default: workdir/评论分析结果.xlsx)")
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    items = read_json(workdir / "extract_items.json")
    total_reviews = int(meta.get("total_reviews") or 0)
    input_file = Path(meta["input_file"])

    skip = workdir / "normalize" / "SKIP.txt"
    if items and not skip.exists():
        raw_path = workdir / "normalize" / "MODEL_OUTPUT.json"
        if not raw_path.exists():
            raise SystemExit(f"缺少归一输出：{raw_path}")
        raw_text = raw_path.read_text(encoding="utf-8").strip()
        if raw_text.startswith("/*"):
            raise SystemExit(f"归一模型输出尚未填写：{raw_path}")
        rows = read_json(workdir / "normalize_input_rows.json")
        expected = {
            (str(r.get("类型") or "").strip(), str(r.get("原始维度") or "").strip())
            for r in rows
            if str(r.get("类型") or "").strip() and str(r.get("原始维度") or "").strip()
        }
        mappings = parse_and_validate_normalize(raw_text, expected)
        items = apply_mappings(items, mappings)
        write_json(workdir / "mappings.json", mappings)
    else:
        mappings = []

    write_json(workdir / "extract_items.json", items)
    summary_rows = aggregate_statistics(items, total_reviews)
    write_json(workdir / "summary.json", summary_rows)

    out = Path(args.output).resolve() if args.output else workdir / "评论分析结果.xlsx"
    write_analysis_workbook(input_file, out, summary_rows=summary_rows)

    result = {
        "output_file": str(out),
        "total_reviews": total_reviews,
        "voc_items": len(items),
        "dimensions": len(summary_rows),
        "mappings": len(mappings),
    }
    write_json(workdir / "result.json", result)
    print(f"output_file={out}")
    print(f"total_reviews={total_reviews} voc_items={len(items)} dimensions={len(summary_rows)}")
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
