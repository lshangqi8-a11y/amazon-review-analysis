# -*- coding: utf-8 -*-
"""Deprecated alias → step7_finalize.py."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

print(
    "注意：请改用 python scripts/step7_finalize.py ...",
    file=sys.stderr,
)
sys.argv[0] = str(Path(__file__).with_name("step7_finalize.py"))
runpy.run_path(str(Path(__file__).with_name("step7_finalize.py")), run_name="__main__")
