# -*- coding: utf-8 -*-
"""
V6 Step 7: write Excel from AI-normalized summary + overview AI + segment insight.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.excel_io import write_analysis_workbook
from lib.io_util import read_json, write_json
from lib.segment_insight_codec import (
    format_segment_insight_digest,
    parse_segment_insight_output,
)
from lib.segment_stats import analyzed_review_count, build_segment_stats_payload
from lib.statistics import aggregate_statistics
from lib.summary_codec import format_summary_sections, format_summary_text, parse_summary_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="V6 finalize workbook")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--allow-empty-summary",
        action="store_true",
        help="允许在未填写 overview MODEL_OUTPUT 时出表",
    )
    parser.add_argument(
        "--allow-empty-segment-insight",
        action="store_true",
        help="允许在未填写 consumer_segment_insight MODEL_OUTPUT 时出表",
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
    analyzed = analyzed_review_count(meta, fallback_total=total_reviews)
    input_file = Path(meta["input_file"])

    summary_rows = aggregate_statistics(items, total_reviews, consolidate=False)
    write_json(workdir / "summary.json", summary_rows)

    overview_text = ""
    summary_sections: list[dict] = []
    sdir = workdir / "overview_summary"
    raw_path = sdir / "MODEL_OUTPUT.json"
    if raw_path.exists():
        raw = raw_path.read_text(encoding="utf-8")
        payload, err = parse_summary_payload(raw)
        if err:
            if args.allow_empty_summary and ("尚未填写" in err or raw.strip().startswith("/*")):
                overview_text = ""
                summary_sections = []
            else:
                raise SystemExit(f"AI 总结校验失败：{err}")
        else:
            overview_text = format_summary_text(payload or {})
            summary_sections = format_summary_sections(payload or {})
            write_json(
                workdir / "overview_summary.json",
                {"summary_text": overview_text, "sections": summary_sections},
            )
    elif not args.allow_empty_summary:
        raise SystemExit(
            "缺少 overview_summary/MODEL_OUTPUT.json；"
            "请先运行 step6_prepare_summary.py，或加 --allow-empty-summary"
        )

    stats_path = workdir / "segment_stats.json"
    if stats_path.exists():
        segment_stats = read_json(stats_path)
    else:
        segment_stats = build_segment_stats_payload(items, analyzed, top_n=5)
        write_json(stats_path, segment_stats)
    core_segments = list(segment_stats.get("core_segments") or [])
    allowed = [s.get("segment") for s in core_segments if s.get("segment")]

    segment_payload: dict | None = None
    segment_digest = ""
    seg_dir = workdir / "consumer_segment_insight"
    seg_raw_path = seg_dir / "MODEL_OUTPUT.json"
    if seg_raw_path.exists():
        raw = seg_raw_path.read_text(encoding="utf-8")
        payload, err = parse_segment_insight_output(raw, allowed_segments=allowed)
        if err:
            if args.allow_empty_segment_insight and (
                "尚未填写" in err or raw.strip().startswith("/*")
            ):
                segment_payload = {
                    "external_research_status": "skipped",
                    "segments": [],
                    "product_development": {"must_have_features": [], "product_moats": []},
                }
            else:
                raise SystemExit(f"消费人群洞察校验失败：{err}")
        else:
            segment_payload = payload
            write_json(workdir / "consumer_segment_insight.json", segment_payload)
    elif not args.allow_empty_segment_insight:
        raise SystemExit(
            "缺少 consumer_segment_insight/MODEL_OUTPUT.json；"
            "请先运行 step6b_prepare_segment_insight.py，或加 --allow-empty-segment-insight"
        )
    else:
        segment_payload = {
            "external_research_status": "skipped",
            "segments": [],
            "product_development": {"must_have_features": [], "product_moats": []},
        }

    segment_digest = format_segment_insight_digest(segment_payload or {})

    out = Path(args.output).resolve() if args.output else workdir / "评论洞察分析结果.xlsx"
    excel_meta = write_analysis_workbook(
        input_file,
        out,
        summary_rows=summary_rows,
        total_reviews=total_reviews,
        voc_items=len(items),
        overview_summary=overview_text,
        summary_sections=summary_sections,
        core_segments=core_segments,
        segment_insight=segment_payload,
        segment_insight_digest=segment_digest,
    )

    result = {
        "skill_version": "v6",
        "output_file": str(out),
        "total_reviews": total_reviews,
        "analyzed_reviews": analyzed,
        "voc_items": len(items),
        "dimensions": len(summary_rows),
        "core_segments": len(core_segments),
        "has_overview_summary": bool(overview_text.strip()),
        "has_segment_insight": bool((segment_payload or {}).get("segments")),
        "external_research_status": (segment_payload or {}).get("external_research_status"),
        "normalized": True,
        "excel": excel_meta,
    }
    write_json(workdir / "result.json", result)
    print(f"output_file={out}")
    print(
        f"total_reviews={total_reviews} analyzed_reviews={analyzed} "
        f"dimensions={len(summary_rows)} core_segments={len(core_segments)} "
        f"ai_summary={'yes' if overview_text.strip() else 'no'} "
        f"segment_insight={'yes' if result['has_segment_insight'] else 'no'}"
    )
    print(f"charts={excel_meta.get('chart_count')} sheets={excel_meta.get('sheetnames')}")
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
