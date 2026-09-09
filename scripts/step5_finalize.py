# -*- coding: utf-8 -*-
"""
V4 Step 5: read eight-dim summary + optional AI overview text → Excel.
Left charts/panels, right AI summary column. No product name/category required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.excel_io import write_analysis_workbook
from lib.io_util import read_json, write_json
from lib.statistics import aggregate_statistics
from lib.summary_codec import parse_summary_output


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 finalize workbook with optional AI summary")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--allow-empty-summary",
        action="store_true",
        help="允许在未填写 MODEL_OUTPUT 时出表（右侧显示占位文案）",
    )
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

    summary_path = workdir / "summary.json"
    if summary_path.exists():
        summary_rows = read_json(summary_path)
        if not isinstance(summary_rows, list):
            raise SystemExit("summary.json 必须是数组")
    else:
        summary_rows = aggregate_statistics(items, total_reviews)
        write_json(summary_path, summary_rows)

    overview_text = ""
    sdir = workdir / "overview_summary"
    raw_path = sdir / "MODEL_OUTPUT.json"
    if raw_path.exists():
        raw = raw_path.read_text(encoding="utf-8")
        text, err = parse_summary_output(raw)
        if err:
            if args.allow_empty_summary and ("尚未填写" in err or raw.strip().startswith("/*")):
                overview_text = ""
            else:
                raise SystemExit(f"AI 总结校验失败：{err}")
        else:
            overview_text = text or ""
            write_json(workdir / "overview_summary.json", {"summary_text": overview_text})
    elif not args.allow_empty_summary:
        raise SystemExit(
            "缺少 overview_summary/MODEL_OUTPUT.json；"
            "请先运行 step4_prepare_summary.py，或加 --allow-empty-summary"
        )

    out = Path(args.output).resolve() if args.output else workdir / "评论洞察分析结果.xlsx"
    excel_meta = write_analysis_workbook(
        input_file,
        out,
        summary_rows=summary_rows,
        total_reviews=total_reviews,
        voc_items=len(items),
        overview_summary=overview_text,
    )

    result = {
        "skill_version": "v4",
        "output_file": str(out),
        "total_reviews": total_reviews,
        "persona_items": len(persona),
        "fulfillment_items": len(fulfillment),
        "voc_items": len(items),
        "dimensions": len(summary_rows),
        "has_overview_summary": bool(overview_text.strip()),
        "excel": excel_meta,
    }
    write_json(workdir / "result.json", result)
    print(f"output_file={out}")
    print(
        f"total_reviews={total_reviews} dimensions={len(summary_rows)} "
        f"ai_summary={'yes' if overview_text.strip() else 'no'}"
    )
    print(f"charts={excel_meta.get('chart_count')} summary_area={excel_meta.get('summary_reserve')}")
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
