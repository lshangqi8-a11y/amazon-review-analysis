# -*- coding: utf-8 -*-
"""Deprecated alias pointing at the current V4 finalize chain."""
from __future__ import annotations

import sys

print(
    "step4_finalize.py 已废弃。当前流程：\n"
    "  step4_prepare_normalize.py  → 填 normalize_batches/*/MODEL_OUTPUT.json\n"
    "  step5_ingest_normalize.py\n"
    "  step6_prepare_summary.py    → 填 overview_summary/MODEL_OUTPUT.json\n"
    "  step7_finalize.py [--allow-empty-summary]",
    file=sys.stderr,
)
raise SystemExit(2)
