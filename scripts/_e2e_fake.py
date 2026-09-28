# -*- coding: utf-8 -*-
"""
Optional local smoke: fake AI outputs through the V5 7-step pipeline.

Requires explicit paths (no machine-specific defaults):

  python scripts/_e2e_fake.py --input reviews.xlsx --workdir ./tmp_v5_e2e --output ./out.xlsx --force
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
        if any(k in low for k in ["love", "great", "durable", "fun", "耐用", "喜欢", "clean", "easy"]):
            items.append(
                {
                    "类型": "用户满意",
                    "原始维度": "耐用好玩",
                    "单条提炼": "正面体验",
                    "信号类型": "满意点",
                }
            )
        if any(k in low for k in ["break", "broke", "dirty", "cheap", "断裂", "脏", "disappoint"]):
            items.append(
                {
                    "类型": "未被满足",
                    "原始维度": "易损坏",
                    "单条提炼": "负面体验",
                    "信号类型": "明确问题",
                }
            )
        if any(k in low for k in ["wish", "希望", "extra", "adapter", "配件"]):
            items.append(
                {
                    "类型": "未被满足",
                    "原始维度": "缺少备用配件",
                    "单条提炼": "希望增加配件",
                    "信号类型": "明确需求",
                }
            )
        results.append({"review_id": rid, "items": items})
    return {"results": results}


def fake_normalize(expected_pairs: list[dict]) -> dict:
    """Identity mapping (enough to exercise normalize → finalize)."""
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


def fake_intelligence(summary_rows: list[dict]) -> dict:
    """Fake Pass4 Review Intelligence covering all required blocks."""
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
    sat = [r["dimension"] for r in summary_rows if r.get("item_type") == "用户满意"]
    unmet = [r["dimension"] for r in summary_rows if r.get("item_type") == "未被满足"]
    people = [r["dimension"] for r in summary_rows if r.get("item_type") == "消费人群"]
    pos = sat[:1]
    neg = unmet[:1]
    attrs = []
    if pos or neg:
        attrs.append(
            {
                "attribute": "耐用性",
                "positive_dimensions": pos,
                "negative_dimensions": neg,
                "assessment": "优劣势并存" if pos and neg else ("整体优势" if pos else "整体短板"),
            }
        )
    pains = []
    for d in unmet[:3]:
        pains.append(
            {
                "dimension": d,
                "severity": "高",
                "priority": "高",
                "reason": "影响正常使用或耐用体验",
            }
        )
    opps = []
    for d in unmet:
        if "配件" in d or d == "缺少备用配件":
            opps.append(
                {
                    "opportunity": "增加备用配件",
                    "source_dimensions": [d],
                    "reason": "存在明确用户需求",
                }
            )
            break
    if not opps and unmet:
        opps.append(
            {
                "opportunity": "针对头部痛点改进",
                "source_dimensions": [unmet[0]],
                "reason": "基于未被满足证据",
            }
        )
    si_segments = [
        {
            "segment": p,
            "summary": f"【评论数据事实】人群「{p}」在评论中可识别，需结合样本状态解读。",
            "important_attributes": ([attrs[0]["attribute"]] if attrs else []),
            "development_implications": [f"针对「{p}」验证核心体验是否匹配其用途与痛点"],
        }
        for p in people
    ]
    si_comps = []
    if len(people) >= 2:
        si_comps.append(
            {
                "segment_a": people[0],
                "segment_b": people[1],
                "finding": "【评论数据事实】两组在用途/痛点提及结构上存在差异，详见 Python 对比表。",
                "external_research_needed": False,
            }
        )
    seg_opps = []
    if people and unmet:
        seg_opps.append(
            {
                "segment": people[0],
                "opportunity": f"针对「{people[0]}」优先处理「{unmet[0]}」",
                "review_evidence": [unmet[0]],
                "external_evidence": [],
                "recommendation": "【产品开发推论】先用小样验证，再扩量",
            }
        )
    return {
        "sections": [
            {"title": t, "bullets": [f"[{t}] 冒烟测试要点一", f"[{t}] 冒烟测试要点二"]}
            for t in titles
        ],
        "attribute_performance": attrs,
        "pain_priorities": pains,
        "opportunities": opps,
        "recommendations": {
            "priority_improvements": [
                {
                    "action": "强化结构耐用",
                    "evidence": f"{pains[0]['dimension']} 高优先级" if pains else "头部痛点",
                    "source_dimensions": [pains[0]["dimension"]] if pains else [],
                }
            ],
            "keep_strengths": [
                {
                    "action": "保留已获好评卖点",
                    "evidence": f"{pos[0]}" if pos else "正向反馈",
                    "source_dimensions": pos,
                }
            ],
            "explore_opportunities": [
                {
                    "action": opps[0]["opportunity"] if opps else "探索配件方案",
                    "evidence": opps[0]["reason"] if opps else "用户需求",
                    "source_dimensions": opps[0]["source_dimensions"] if opps else [],
                }
            ],
        },
        "segment_intelligence": {
            "segments": si_segments,
            "comparisons": si_comps,
            "external_research_status": "unavailable",
            "external_research": [],
            "segment_product_opportunities": seg_opps,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="V5 fake-AI end-to-end smoke (local only)")
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
    assert meta.get("skill_version") == "v5"
    assert "analyzed_reviews" in meta
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
    summary_rows = json.loads((wd / "summary.json").read_text(encoding="utf-8"))
    sdir = wd / "review_intelligence"
    (sdir / "MODEL_OUTPUT.json").write_text(
        json.dumps(fake_intelligence(summary_rows), ensure_ascii=False, indent=2),
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
