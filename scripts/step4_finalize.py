# -*- coding: utf-8 -*-
"""Deprecated alias: use step5_finalize.py (after step4_prepare_summary.py)."""
from __future__ import annotations

import sys

print(
    "step4_finalize.py 已拆分：\n"
    "  1) python scripts/step4_prepare_summary.py --workdir ...\n"
    "  2) 填写 overview_summary/MODEL_OUTPUT.json\n"
    "  3) python scripts/step5_finalize.py --workdir ... --output ...\n"
    "若仅需先出表、总结可后补：step5_finalize.py --allow-empty-summary",
    file=sys.stderr,
)
raise SystemExit(2)
