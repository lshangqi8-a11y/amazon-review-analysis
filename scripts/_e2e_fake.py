# -*- coding: utf-8 -*-
"""
Optional local smoke: fake AI outputs through the V6 pipeline.

  python scripts/_e2e_fake.py --input reviews.xlsx --workdir ./tmp_v6_e2e --output ./out.xlsx --force
"""
from __future__ import annotations

import argparse
import json
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
        if any(k in low for k in ["small dog", "小型", "small breed"]):
            items.append({"类型": "消费人群", "原始维度": "小型犬", "单条提炼": "评论提到小型犬"})
        if any(k in low for k in ["multi", "多犬", "two dog", "dogs"]):
            items.append({"类型": "消费人群", "原始维度": "多犬家庭", "单条提炼": "多犬家庭"})
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


def fake_normalize(expected_pairs: list[dict]) -> dict:
    return {
        "mappings": [
            {
                "类型": row["类型"],
                "原始维度": row["原始维度"],
                "标准维度": row["原始维度"],
            }
            for row in expected_pairs
        ]
    }


def fake_summary() -> dict:
    titles = [
        "消费人群",
        "使用地点",
        "使用时刻",
        "产品用途",
        "使用场景",
        "购买动机",
        "用户满意",
        "未被满足",
    ]
    return {
        "sections": [
            {"title": t, "bullets": [f"[{t}] 冒烟测试要点一", f"[{t}] 冒烟测试要点二"]}
            for t in titles
        ]
    }


def fake_segment_insight(allowed: list[str]) -> dict:
    segments = []
    for i, name in enumerate(allowed):
        role = "最终使用者" if i == 0 else "购买决策者"
        segments.append(
            {
                "segment": name,
                "role": role,
                "review_findings": [f"{name}在评论中与用途/场景共现"],
                "ai_profile": [f"{name}倾向高频互动，重视陪伴体验（联网不可用，暂据评论归纳）"],
                "core_needs": [f"{name}需要耐用与安全"],
                "sources": [],
            }
        )
    targets = allowed[:2] if allowed else []
    return {
        "external_research_status": "unavailable",
        "segments": segments,
        "product_development": {
            "requirements": [
                {
                    "requirement": "耐用结构",
                    "target_segments": targets or ["（无）"],
                    "basis": "评论多次提到耐用与损坏风险",
                }
            ]
            if targets
            else [],
            "product_moats": [
                {
                    "moat": "针对核心人群的长续航稳定体验",
                    "reason": "评论高频使用场景需要持续稳定，普通功能堆砌难形成差异",
                }
            ]
            if targets
            else [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="V6 fake-AI end-to-end smoke (local only)")
    parser.add_argument("--input", required=True, help="Source reviews xlsx")
    parser.add_argument("--workdir", required=True, help="Working directory for batches")
    parser.add_argument("--output", required=True, help="Output analysis xlsx")
    parser.add_argument("--force", action="store_true", help="Pass --force to step1_prepare")
    args = parser.parse_args()

    wd = Path(args.workdir).resolve()
    inp = Path(args.input).resolve()
    out = Path(args.output).resolve()
    if not inp.exists():
        raise SystemExit(f"input not found: {inp}")

    cmd1 = [
        sys.executable,
        str(ROOT / "scripts/step1_prepare.py"),
        "--input",
        str(inp),
        "--workdir",
        str(wd),
    ]
    if args.force:
        cmd1.append("--force")
    subprocess.run(cmd1, check=True)

    meta = json.loads((wd / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("skill_version") == "v6"
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
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/step2_ingest_persona.py"), "--workdir", str(wd)],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/step3_ingest_fulfillment.py"), "--workdir", str(wd)],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/step4_prepare_normalize.py"), "--workdir", str(wd)],
        check=True,
    )
    meta = json.loads((wd / "meta.json").read_text(encoding="utf-8"))
    for b in meta.get("normalize_batches") or []:
        bdir = wd / b["path"]
        expected = json.loads((bdir / "expected_pairs.json").read_text(encoding="utf-8"))
        (bdir / "MODEL_OUTPUT.json").write_text(
            json.dumps(fake_normalize(expected), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/step5_ingest_normalize.py"), "--workdir", str(wd)],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/step6_prepare_summary.py"), "--workdir", str(wd)],
        check=True,
    )
    sdir = wd / "overview_summary"
    (sdir / "MODEL_OUTPUT.json").write_text(
        json.dumps(fake_summary(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/step6b_prepare_segment_insight.py"),
            "--workdir",
            str(wd),
            "--network-capability",
            "offline",
        ],
        check=True,
    )
    seg_meta = json.loads(
        (wd / "consumer_segment_insight" / "input_meta.json").read_text(encoding="utf-8")
    )
    allowed = list(seg_meta.get("allowed_segments") or [])
    (wd / "consumer_segment_insight" / "MODEL_OUTPUT.json").write_text(
        json.dumps(fake_segment_insight(allowed), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/step7_finalize.py"),
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
