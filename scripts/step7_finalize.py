# -*- coding: utf-8 -*-
"""
V5 Step 7: validate Review Intelligence + write Excel
(overview / decision / 消费人群深度分析 / AI总结 / result).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import INTELLIGENCE_DIR_NAME, SKILL_VERSION
from lib.excel_io import write_analysis_workbook
from lib.intelligence_codec import parse_intelligence_output
from lib.io_util import read_json, write_json
from lib.segment_stats import build_segment_analysis
from lib.statistics import aggregate_statistics


def _analyzed_reviews(meta: dict) -> int:
    for key in ("analyzed_reviews", "ai_reviews"):
        if meta.get(key) is not None:
            return int(meta.get(key) or 0)
    return int(meta.get("total_reviews") or 0)


def _resolve_intelligence_dir(workdir: Path, meta: dict) -> Path:
    ri = workdir / INTELLIGENCE_DIR_NAME
    if (ri / "MODEL_OUTPUT.json").exists() or (ri / "user.md").exists():
        return ri
    legacy = workdir / "overview_summary"
    if (legacy / "MODEL_OUTPUT.json").exists():
        return legacy
    info = meta.get("review_intelligence") or meta.get("overview_summary") or {}
    rel = info.get("path") if isinstance(info, dict) else None
    if rel:
        return workdir / rel
    return ri


def main() -> int:
    parser = argparse.ArgumentParser(description="V5 finalize workbook with Review Intelligence")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--allow-empty-summary",
        action="store_true",
        help="允许在未填写 Intelligence MODEL_OUTPUT 时出表",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    mappings_path = workdir / "normalize_mappings.json"
    extract_path = workdir / "extract_items.json"
    if not mappings_path.exists() or not extract_path.exists():
        raise SystemExit(
            "缺少 AI 归一产物（normalize_mappings.json / extract_items.json）。"
            "请先完成 step4_prepare_normalize → 填 MODEL_OUTPUT → step5_ingest_normalize。"
        )

    items = read_json(extract_path)
    if not isinstance(items, list):
        raise SystemExit("extract_items.json 必须是数组")
    if not any(it.get("merged_dimension") for it in items):
        raise SystemExit("extract_items.json 缺少 merged_dimension；请重新运行 step5_ingest_normalize")

    total_reviews = int(meta.get("total_reviews") or 0)
    analyzed = _analyzed_reviews(meta)
    input_file = Path(meta["input_file"])

    summary_rows = aggregate_statistics(items, analyzed, consolidate=False)
    write_json(workdir / "summary.json", summary_rows)

    # Rebuild segment analysis; attach attribute specs after parse if available
    segment_analysis = build_segment_analysis(items, analyzed)

    overview_text = ""
    intelligence = None
    sdir = _resolve_intelligence_dir(workdir, meta)
    raw_path = sdir / "MODEL_OUTPUT.json"
    if raw_path.exists():
        raw = raw_path.read_text(encoding="utf-8")
        # First parse to get attribute_performance for attribute-level segment assoc
        # Recompute segment_analysis with attribute specs after a lightweight peek
        from lib.extract_codec import parse_json_content

        peek = parse_json_content(raw) if not raw.strip().startswith("/*") else None
        attr_specs = []
        if isinstance(peek, dict):
            attr_specs = [
                a for a in (peek.get("attribute_performance") or []) if isinstance(a, dict)
            ]
        if attr_specs:
            segment_analysis = build_segment_analysis(
                items, analyzed, attribute_specs=attr_specs
            )
        write_json(workdir / "segment_analysis.json", {
            "analyzed_reviews": segment_analysis.get("analyzed_reviews"),
            "known_segments": segment_analysis.get("known_segments"),
            "rules": segment_analysis.get("rules"),
            "segments": [
                {k: v for k, v in s.items() if k != "review_rows"}
                for s in (segment_analysis.get("segments") or [])
            ],
            "comparisons": segment_analysis.get("comparisons") or [],
        })

        enriched, text, err = parse_intelligence_output(
            raw,
            summary_rows=summary_rows,
            items=items,
            analyzed_reviews=analyzed,
            segment_analysis=segment_analysis,
        )
        if err:
            if args.allow_empty_summary and ("尚未填写" in err or raw.strip().startswith("/*")):
                overview_text = ""
            else:
                raise SystemExit(f"Review Intelligence 校验失败：{err}")
        else:
            intelligence = enriched
            overview_text = text or ""
            write_json(
                workdir / "review_intelligence.json",
                {
                    "summary_text": overview_text,
                    "intelligence": intelligence,
                },
            )
            write_json(
                workdir / "overview_summary.json",
                {"summary_text": overview_text},
            )
    elif not args.allow_empty_summary:
        raise SystemExit(
            f"缺少 {INTELLIGENCE_DIR_NAME}/MODEL_OUTPUT.json；"
            "请先运行 step6_prepare_summary.py，或加 --allow-empty-summary"
        )

    out = Path(args.output).resolve() if args.output else workdir / "评论洞察分析结果.xlsx"
    excel_meta = write_analysis_workbook(
        input_file,
        out,
        summary_rows=summary_rows,
        total_reviews=total_reviews,
        analyzed_reviews=analyzed,
        voc_items=len(items),
        overview_summary=overview_text,
        intelligence=intelligence,
        segment_analysis=segment_analysis,
    )

    result = {
        "skill_version": SKILL_VERSION,
        "output_file": str(out),
        "total_reviews": total_reviews,
        "analyzed_reviews": analyzed,
        "voc_items": len(items),
        "dimensions": len(summary_rows),
        "segments": len(segment_analysis.get("known_segments") or []),
        "has_overview_summary": bool(overview_text.strip()),
        "has_intelligence": bool(intelligence),
        "normalized": True,
        "excel": excel_meta,
    }
    write_json(workdir / "result.json", result)
    print(f"output_file={out}")
    print(
        f"total_reviews={total_reviews} analyzed_reviews={analyzed} "
        f"dimensions={len(summary_rows)} segments={result['segments']} "
        f"ai_summary={'yes' if overview_text.strip() else 'no'}"
    )
    print(f"charts={excel_meta.get('chart_count')} sheets={excel_meta.get('sheetnames')}")
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
