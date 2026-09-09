# -*- coding: utf-8 -*-
"""V4 Step 3: ingest fulfillment_batches → fulfillment_items.json"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import FULFILLMENT_ALLOWED
from lib.extract_codec import (
    internal_to_voc_items,
    parse_json_content,
    to_internal_voc_payload,
    validate_extract_payload,
)
from lib.gatekeep import gatekeep_fulfillment_items
from lib.io_util import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 ingest fulfillment AI outputs")
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")

    all_items = []
    for batch in meta.get("fulfillment_batches") or []:
        bdir = workdir / batch["path"]
        raw_path = bdir / "MODEL_OUTPUT.json"
        if not raw_path.exists():
            raise SystemExit(f"缺少满足模型输出：{raw_path}")
        raw_text = raw_path.read_text(encoding="utf-8").strip()
        if raw_text.startswith("/*"):
            raise SystemExit(f"满足模型输出尚未填写：{raw_path}")
        expected = read_json(bdir / "expected_ids.json")
        expected_ids = set(expected.get("review_ids") or [])
        chunk = expected.get("reviews") or []
        payload = parse_json_content(raw_text)
        if payload is None:
            raise SystemExit(f"无法解析 JSON：{raw_path}")
        err = validate_extract_payload(
            payload, expected_ids, allowed_types=FULFILLMENT_ALLOWED
        )
        if err:
            raise SystemExit(f"满足提炼校验失败 [{batch['batch_id']}]：{err}")
        internal = to_internal_voc_payload(
            payload, expected_ids=expected_ids, allowed_types=FULFILLMENT_ALLOWED
        )
        all_items.extend(
            internal_to_voc_items(internal, chunk, allowed_types=FULFILLMENT_ALLOWED)
        )

    kept, dropped = gatekeep_fulfillment_items(all_items)
    write_json(workdir / "fulfillment_items.json", kept)
    write_json(workdir / "fulfillment_dropped.json", dropped)
    print(f"fulfillment_items={len(kept)} dropped={len(dropped)}")
    print("NEXT: python scripts/step4_prepare_summary.py --workdir ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
