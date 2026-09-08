# -*- coding: utf-8 -*-
"""One-shot fake-AI e2e for V4."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fake_persona(reviews):
    results = []
    for r in reviews:
        rid = r["review_id"]
        text = (r.get("title") or "") + " " + (r.get("content") or "")
        low = text.lower()
        items = []
        if any(k in low for k in ["puppy", "pup", "幼"]):
            items.append({"类型": "消费人群", "原始维度": "幼犬", "单条提炼": "评论提到幼犬"})
        if any(k in low for k in ["yard", "outdoor", "庭院", "户外", "outside", "kitchen"]):
            items.append({"类型": "使用地点", "原始维度": "户外-庭院", "单条提炼": "在户外使用"})
        if any(k in low for k in ["everyday", "daily", "每天", "night", "nightly"]):
            items.append({"类型": "使用时刻", "原始维度": "每天", "单条提炼": "日常频繁使用"})
        if any(k in low for k in ["tire", "energy", "精力", "exercise", "train"]):
            items.append({"类型": "产品用途", "原始维度": "消耗精力", "单条提炼": "用来消耗精力"})
        if any(k in low for k in ["gift", "礼物", "travel", "旅行"]):
            items.append({"类型": "使用场景", "原始维度": "礼赠场合", "单条提炼": "送礼或出行相关"})
        if "because" in low or "recommend" in low or "推荐" in text:
            items.append({"类型": "购买动机", "原始维度": "口碑/推荐", "单条提炼": "因推荐而买"})
        results.append({"review_id": rid, "items": items})
    return {"results": results}


def fake_fulfill(reviews):
    results = []
    for r in reviews:
        rid = r["review_id"]
        low = ((r.get("title") or "") + (r.get("content") or "")).lower()
        items = []
        if any(k in low for k in ["love", "great", "durable", "fun", "耐用", "喜欢"]):
            items.append({"类型": "用户满意", "原始维度": "耐用好玩", "单条提炼": "正面体验"})
        if any(k in low for k in ["break", "broke", "dirty", "cheap", "断裂", "脏", "disappoint"]):
            items.append({"类型": "未被满足", "原始维度": "易损坏", "单条提炼": "负面体验"})
        results.append({"review_id": rid, "items": items})
    return {"results": results}


def main() -> int:
    wd = Path(r"d:\skills测试\v4_e2e")
    if wd.exists():
        shutil.rmtree(wd)
    inp = Path(r"C:\Users\Administrator\Downloads\B0DKFHWTZM.xlsx")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/step1_prepare.py"), "--input", str(inp), "--workdir", str(wd)],
        check=True,
    )
    meta = json.loads((wd / "meta.json").read_text(encoding="utf-8"))
    assert meta["skill_version"] == "v4"
    for b in meta["persona_batches"]:
        bdir = wd / b["path"]
        exp = json.loads((bdir / "expected_ids.json").read_text(encoding="utf-8"))
        (bdir / "MODEL_OUTPUT.json").write_text(
            json.dumps(fake_persona(exp["reviews"]), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    for b in meta["fulfillment_batches"]:
        bdir = wd / b["path"]
        exp = json.loads((bdir / "expected_ids.json").read_text(encoding="utf-8"))
        (bdir / "MODEL_OUTPUT.json").write_text(
            json.dumps(fake_fulfill(exp["reviews"]), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    subprocess.run([sys.executable, str(ROOT / "scripts/step2_ingest_persona.py"), "--workdir", str(wd)], check=True)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/step3_ingest_fulfillment.py"), "--workdir", str(wd)], check=True
    )
    out = Path(r"d:\skills测试\B0DKFHWTZM-评论洞察分析-v4-e2e.xlsx")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/step4_finalize.py"),
            "--workdir",
            str(wd),
            "--output",
            str(out),
        ],
        check=True,
    )
    print("E2E_OK", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
