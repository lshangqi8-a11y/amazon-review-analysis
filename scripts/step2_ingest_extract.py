# -*- coding: utf-8 -*-
"""
Step 2 (Python): validate all extract MODEL_OUTPUT.json → extract_items.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.extract_codec import (
    internal_to_voc_items,
    parse_json_content,
    to_internal_voc_payload,
    validate_extract_payload,
)
from lib.io_util import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest & validate extract AI outputs")
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")

    all_items = []
    for batch in meta.get("extract_batches") or []:
        bdir = workdir / batch["path"]
        raw_path = bdir / "MODEL_OUTPUT.json"
        if not raw_path.exists():
            raise SystemExit(f"缺少模型输出：{raw_path}")
        raw_text = raw_path.read_text(encoding="utf-8").strip()
        if raw_text.startswith("/*"):
            raise SystemExit(f"模型输出尚未填写：{raw_path}")
        expected = read_json(bdir / "expected_ids.json")
        expected_ids = set(expected.get("review_ids") or [])
        chunk = expected.get("reviews") or []
        payload = parse_json_content(raw_text)
        if payload is None:
            raise SystemExit(f"无法解析 JSON：{raw_path}")
        err = validate_extract_payload(payload, expected_ids)
        if err:
            raise SystemExit(f"提炼校验失败 [{batch['batch_id']}]：{err}")
        internal = to_internal_voc_payload(payload, expected_ids=expected_ids)
        all_items.extend(internal_to_voc_items(internal, chunk))

    write_json(workdir / "extract_items.json", all_items)
    print(f"voc_items={len(all_items)}")
    print("NEXT: run step3_prepare_normalize.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
