# -*- coding: utf-8 -*-
"""压测统计+导出环节：不同维度规模下的耗时/体积/图表柱数。"""
import sys, time, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openpyxl import Workbook
from lib.excel_io import write_analysis_workbook

TYPES = ["消费人群","使用地点","使用时刻","产品用途","使用场景","购买动机","用户满意","未被满足"]


def make_rows(n_dims, total_reviews):
    rows = []
    for i in range(n_dims):
        t = TYPES[i % 8]
        cnt = max(1, int(total_reviews * (0.30 / (1 + i * 0.01))))
        rows.append({
            "item_type": t,
            "dimension": f"维度标签{i:04d}",
            "mention_count": cnt,
            "mention_rate": round(cnt / total_reviews * 100, 2),
            "representative_feedback": "代表反馈节选内容，用于测试导出体积与渲染表现",
        })
    return rows


def run(n_dims, total_reviews):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.xlsx"
        wb = Workbook()
        wb.active.title = "Reviews"
        wb.active.append(["标题", "内容"])
        wb.active.append(["t", "c"])
        wb.save(src)
        wb.close()
        out = Path(td) / "out.xlsx"
        rows = make_rows(n_dims, total_reviews)
        t0 = time.time()
        meta = write_analysis_workbook(
            src, out, summary_rows=rows,
            total_reviews=total_reviews,
            voc_items=n_dims * 2,
            overview_summary="测试总结\n" * 50,
        )
        dt = time.time() - t0
        size = out.stat().st_size if out.exists() else 0
        return dt, size, meta.get("chart_count")


if __name__ == "__main__":
    print(f"{'维度数':>8} {'评论数':>9} {'耗时s':>8} {'文件KB':>9} {'图表':>5}")
    print("-" * 48)
    for n_dims, n_rev in [(120, 100), (300, 500), (600, 2000),
                          (1200, 8000), (2500, 30000), (5000, 100000)]:
        try:
            dt, size, ch = run(n_dims, n_rev)
            print(f"{n_dims:>8} {n_rev:>9} {dt:>8.2f} {size / 1024:>9.1f} {ch:>5}")
        except Exception as e:
            print(f"{n_dims:>8} {n_rev:>9}  ERROR: {type(e).__name__}: {str(e)[:70]}")
