# -*- coding: utf-8 -*-
"""Optional heuristic long-tail only (AI normalize is primary)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import LABEL_OTHER, OVERVIEW_TOP_N
from lib.excel_io import _overview_limit_for_type
from lib.statistics import aggregate_statistics


def test_long_tail_bucket_only() -> None:
    items = []
    for rid in range(1, 10):
        items.append(
            {
                "item_type": "购买动机",
                "dimension": "复购囤货",
                "extracted_summary": f"a{rid}",
                "review_row": rid,
            }
        )
    for i, rid in enumerate(range(100, 110)):
        items.append(
            {
                "item_type": "购买动机",
                "dimension": f"偶发动机{i}独特性",
                "extracted_summary": f"c{i}",
                "review_row": rid,
            }
        )
    rows = aggregate_statistics(items, analyzed_reviews=200, consolidate=True)
    motive = [r for r in rows if r["item_type"] == "购买动机"]
    names = {r["dimension"] for r in motive}
    assert "复购囤货" in names
    assert LABEL_OTHER in names


def test_overview_top_n_constant() -> None:
    assert isinstance(OVERVIEW_TOP_N, dict)
    assert _overview_limit_for_type("消费人群") == 10


if __name__ == "__main__":
    test_long_tail_bucket_only()
    test_overview_top_n_constant()
    print("LABEL_FALLBACK_OK")
