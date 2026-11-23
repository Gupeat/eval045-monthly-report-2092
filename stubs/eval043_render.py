"""EVAL-043 local stub: render the pre-review draft."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stubs.common import load_json, write_json
from stubs.md import markdown_to_docx, md_to_html

CSS = """
body { font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; color: #1f2328; font-size: 11pt; line-height: 1.55; margin: 28px; }
h1 { font-size: 22pt; margin: 0 0 4px; }
h2 { font-size: 15pt; border-bottom: 1px solid #d0d7de; padding-bottom: 4px; margin-top: 22px; }
h3 { font-size: 12pt; margin-top: 16px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9pt; }
th, td { border: 1px solid #c9d1d9; padding: 5px 6px; text-align: left; vertical-align: top; }
th { background: #f3f4f6; }
.meta { color: #57606a; font-size: 10pt; }
.note { background: #fff8c5; border-left: 4px solid #d4a72c; padding: 8px 10px; }
"""


def _ranked_tools(aggregate: dict) -> list[tuple[str, dict]]:
    return sorted(aggregate["tools"].items(), key=lambda kv: (-kv[1]["avg_quality_score"], kv[0]))


def draft_markdown(dataset: dict, aggregate: dict, attribution: dict) -> str:
    runs = aggregate["runs"]
    reviews = aggregate["reviews"]
    ranked = _ranked_tools(aggregate)
    lines = [
        "# 会员空间平台质量月报（2026-11）",
        "",
        "数据期间：2026-11-01 至 2026-11-30。本报告使用虚构数据演练月报流程，不代表任何真实会员或员工。",
        "",
        "## 管理摘要",
        "",
        f"- 7 个工具夜间运行 {runs['total']} 次，成功 {runs['success']} 次，成功率 {runs['success_rate_pct']:.4f}%。",
        f"- 本月复核事件约 3,000 条，拒绝 {reviews['rejected']} 条，拒绝率 {reviews['reject_rate_pct']:.4f}%。",
        f"- 红队发现 {aggregate['redteam']['total']} 条问题，覆盖 5 种状态。",
        f"- 运行期间发生 {aggregate['incidents']['degraded']} 次退化事件和 {aggregate['incidents']['p0_failure']} 次 P0 失败。",
        "",
        "## 运行稳定性",
        "",
        "| 事件 | 类型 | 工具 | 日期 | 根因 | 恢复 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i in attribution["incidents"]:
        lines.append(
            f"| {i['incident_id']} | 退化（P0 为 {i['type']}） | {i['tool_id']} | {i['date']} | {i['root_cause']} | {i.get('recovery_run_id') or '当日恢复'} |"
        )
    lines += [
        "",
        "## 工具质量排名",
        "",
        "| 排名 | 工具 | 运行次数 | 成功率 | 平均质量分 | p95 延迟(ms) | 复核条数 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rank, (tool, stat) in enumerate(ranked, start=1):
        success_rate = stat["success"] * 100.0 / stat["runs"] if stat["runs"] else 0.0
        lines.append(
            f"| {rank} | {tool} | {stat['runs']} | {success_rate:.2f}% | {stat['avg_quality_score']:.4f} | {stat['p95_latency_ms']} | {stat['reviews']} |"
        )
    lines += [
        "",
        "## 失败模式归因",
        "",
        "| 拒绝原因 | 条数 | 占拒绝总数 |",
        "| --- | --- | --- |",
    ]
    for reason in attribution["rejection_reasons"]:
        lines.append(f"| {reason['reason']} | {reason['count']} | {reason['share_pct']:.4f}% |")
    lines += [
        "",
        "## 审阅与发布",
        "",
        "本稿为待审阅草稿，尚未经过 EVAL-044 审阅。",
        "",
        "## 数据口径",
        "",
        "运行记录来自 runs 表；复核记录来自 review_events 表；事件来自 incidents 表。所有数字由聚合脚本生成。",
        "",
        "## 附录",
        "",
        f"- 种子：{dataset['seed']}",
        f"- 数据集生成时间：{dataset['generated_at']}",
        "- 生成命令：python run_all.py",
        "",
    ]
    return "\n".join(lines)


def html_page(markdown: str, title: str) -> str:
    return (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title><style>{CSS}</style></head><body>"
        f"{md_to_html(markdown)}</body></html>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="EVAL-043 render stub")
    parser.add_argument("--dataset", default="out/seed_dataset.json")
    parser.add_argument("--aggregate", default="out/aggregate.json")
    parser.add_argument("--attribution", default="out/attribution.json")
    parser.add_argument("--out-dir", default="out")
    args = parser.parse_args()
    dataset = load_json(args.dataset)
    aggregate = load_json(args.aggregate)
    attribution = load_json(args.attribution)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = draft_markdown(dataset, aggregate, attribution)
    (out / "draft.md").write_text(md, encoding="utf-8")
    (out / "draft.html").write_text(html_page(md, "质量月报草稿 2026-11"), encoding="utf-8")
    markdown_to_docx(md, out / "draft.docx")
    write_json(out / "draft_meta.json", {"stage": "EVAL-043", "draft_md": "out/draft.md", "draft_docx": "out/draft.docx"})
    print(f"wrote {out / 'draft.md'}, {out / 'draft.html'}, {out / 'draft.docx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
