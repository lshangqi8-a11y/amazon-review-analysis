# -*- coding: utf-8 -*-
"""Backward-compatible facade → intelligence_codec (V5 Review Intelligence)."""
from __future__ import annotations

from .intelligence_codec import (  # noqa: F401
    build_stats_block,
    format_summary_text,
    parse_summary_output,
    validate_summary_payload,
)
