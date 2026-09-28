# -*- coding: utf-8 -*-
"""
V5 Step 5: ingest AI normalize mappings → merged_dimension → summary.json
Rates use analyzed_reviews as denominator.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.io_util import read_json, write_json
from lib.normalize_codec import (
    apply_mappings,
    mapping_compression_stats,
    parse_and_validate_normalize,
    type_dir_name,
)
from lib.statistics import aggregate_statistics


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 ingest AI dimension normalize outputs")
    parser.add_argument("--workdir", required=True)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="允许部分类型尚未填写；仅汇入已完成类型（未完成类型维度保持原名）",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")
    batches = meta.get("normalize_batches") or []
    if not batches:
        raise SystemExit("meta.json 缺少 normalize_batches；请先运行 step4_prepare_normalize.py")

    persona = read_json(workdir / "persona_items.json")
    fulfillment = read_json(workdir / "fulfillment_items.json")
    if not isinstance(persona, list) or not isinstance(fulfillment, list):
        raise SystemExit("persona_items.json / fulfillment_items.json 必须是数组")
    items = list(persona) + list(fulfillment)

    all_mappings: list[dict] = []
    pending: list[str] = []
    done: list[str] = []

    for b in batches:
        t = b.get("item_type") or ""
        rel = b.get("path") or f"normalize_batches/{type_dir_name(t)}"
        bdir = workdir / rel
        raw_path = bdir / "MODEL_OUTPUT.json"
        expected_rows = read_json(bdir / "expected_pairs.json")
        expected = {(r["类型"], r["原始维度"]) for r in expected_rows}
        if not raw_path.exists():
            pending.append(t)
            continue
        raw = raw_path.read_text(encoding="utf-8")
        if raw.strip().startswith("/*") or "尚未填写" in raw:
            pending.append(t)
            continue
        try:
            mappings = parse_and_validate_normalize(raw, expected)
        except RuntimeError as exc:
            raise SystemExit(f"归一失败 [{t}]: {exc}") from exc
        all_mappings.extend(mappings)
        done.append(t)
        write_json(bdir / "mappings.json", mappings)

    if pending and not args.allow_partial:
        raise SystemExit(
            "以下类型归一尚未填写 MODEL_OUTPUT.json：\n  "
            + ", ".join(pending)
            + "\n可用 --allow-partial 先汇入已完成类型。"
        )

    # Identity-fill for pending types when allow-partial
    if pending:
        covered = {(m["类型"], m["原始维度"]) for m in all_mappings}
        for it in items:
            t = (it.get("item_type") or "").strip()
            raw = (it.get("dimension") or "").strip()
            if t in pending and t and raw and (t, raw) not in covered:
                all_mappings.append({"类型": t, "原始维度": raw, "标准维度": raw})
                covered.add((t, raw))

    # Ensure every extract pair has a mapping
    needed = {
        ((it.get("item_type") or "").strip(), (it.get("dimension") or "").strip())
        for it in items
        if (it.get("item_type") or "").strip() and (it.get("dimension") or "").strip()
    }
    have = {(m["类型"], m["原始维度"]) for m in all_mappings}
    missing = needed - have
    if missing:
        sample = ", ".join(f"{t}/{r}" for t, r in sorted(missing)[:8])
        raise SystemExit(f"归一映射仍缺：{sample}")

    normalized = apply_mappings(items, all_mappings)
    write_json(workdir / "normalize_mappings.json", all_mappings)
    write_json(workdir / "extract_items.json", normalized)

    analyzed = int(meta.get("analyzed_reviews") or meta.get("ai_reviews") or meta.get("total_reviews") or 0)
    # AI normalize is the merge source of truth — no heuristic synonym pass.
    # Denominator = analyzed_reviews (有效分析评论数), not raw total_reviews.
    summary_rows = aggregate_statistics(normalized, analyzed, consolidate=False)
    write_json(workdir / "summary.json", summary_rows)

    stats = mapping_compression_stats(all_mappings)
    meta["normalize_progress"] = {
        "done": done,
        "pending": pending,
        "compression": stats,
        "summary_dimensions": len(summary_rows),
    }
    write_json(workdir / "meta.json", meta)

    print(f"normalize done={len(done)} pending={len(pending)} mappings={len(all_mappings)}")
    print(f"summary_dimensions={len(summary_rows)} (after AI normalize)")
    for t, c in stats.items():
        print(f"  {t}: raw={c['raw']} → std={c['std']}")
    if pending:
        print("PENDING: " + " ".join(pending))
    else:
        print("NEXT: python scripts/step6_prepare_summary.py --workdir ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
