# -*- coding: utf-8 -*-
"""Shared helpers for skill CLI steps."""
from __future__ import annotations

import json
from pathlib import Path


def skill_root() -> Path:
    # .../amazon-review-analysis/scripts/lib/io_util.py → skill root
    return Path(__file__).resolve().parents[2]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def render_template(template: str, variables: dict) -> str:
    out = template
    for key, value in variables.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def format_product(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text else "（未填写）"
