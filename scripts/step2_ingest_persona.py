# -*- coding: utf-8 -*-
"""V4 Step 2: ingest persona_batches → persona_items.json"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.constants import PERSONA_ALLOWED
from lib.extract_codec import (
    internal_to_voc_items,
    parse_json_content,
    to_internal_voc_payload,
    validate_extract_payload,
)
from lib.gatekeep import gatekeep_persona_items
from lib.io_util import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 ingest persona AI outputs")
    parser.add_argument("--workdir", required=True)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="跳过尚未填写的批次（断点续跑）；默认要求全部批次填写完整",
    )
    args = parser.parse_args()
    workdir = Path(args.workdir).resolve()
    meta = read_json(workdir / "meta.json")

    batches = meta.get("persona_batches") or []
    all_items = []
    done: list[str] = []
    pending: list[str] = []
    for batch in batches:
        bdir = workdir / batch["path"]
        raw_path = bdir / "MODEL_OUTPUT.json"
        if not raw_path.exists():
            raise SystemExit(f"缺少画像模型输出：{raw_path}")
        raw_text = raw_path.read_text(encoding="utf-8").strip()
        if raw_text.startswith("/*"):
            if not args.allow_partial:
                raise SystemExit(
                    f"画像模型输出尚未填写：{raw_path}\n"
                    "提示：若需断点续跑，请加 --allow-partial 跳过未完成批次。"
                )
            pending.append(batch["batch_id"])
            continue
        expected = read_json(bdir / "expected_ids.json")
        expected_ids = set(expected.get("review_ids") or [])
        chunk = expected.get("reviews") or []
        payload = parse_json_content(raw_text)
        if payload is None:
            raise SystemExit(f"无法解析 JSON：{raw_path}")
        err = validate_extract_payload(payload, expected_ids, allowed_types=PERSONA_ALLOWED)
        if err:
            raise SystemExit(f"画像提炼校验失败 [{batch['batch_id']}]：{err}")
        internal = to_internal_voc_payload(
            payload, expected_ids=expected_ids, allowed_types=PERSONA_ALLOWED
        )
        all_items.extend(
            internal_to_voc_items(internal, chunk, allowed_types=PERSONA_ALLOWED)
        )
        done.append(batch["batch_id"])

    kept, dropped = gatekeep_persona_items(all_items)
    write_json(workdir / "persona_items.json", kept)
    write_json(workdir / "persona_dropped.json", dropped)
    meta["persona_progress"] = {
        "done": done,
        "pending": pending,
        "total": len(batches),
        "partial": bool(pending),
    }
    write_json(workdir / "meta.json", meta)
    print(f"persona_items={len(kept)} dropped={len(dropped)}")
    print(f"persona_batches done={len(done)}/{len(batches)} pending={len(pending)}")
    if pending:
        print(f"PENDING: {' '.join(pending)}")
        print("NEXT: 继续填写上列批次的 MODEL_OUTPUT.json，完成后重跑本命令")
    else:
        print("NEXT: Fill fulfillment_batches/*/MODEL_OUTPUT.json then step3_ingest_fulfillment.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
