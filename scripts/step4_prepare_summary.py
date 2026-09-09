# -*- coding: utf-8 -*-
"""Deprecated alias → step6_prepare_summary.py (after AI normalize)."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

print(
    "注意：流程已增加「AI 维度归一」。\n"
    "请使用：python scripts/step6_prepare_summary.py ...\n"
    "完整顺序：step4_prepare_normalize → step5_ingest_normalize → step6_prepare_summary → step7_finalize",
    file=sys.stderr,
)
sys.argv[0] = str(Path(__file__).with_name("step6_prepare_summary.py"))
runpy.run_path(str(Path(__file__).with_name("step6_prepare_summary.py")), run_name="__main__")
