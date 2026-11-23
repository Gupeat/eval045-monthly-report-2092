"""EVAL-044 local stub: review the draft, publish v2, and render PDF."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stubs.common import load_json, write_json
from stubs.md import md_to_html

PUBLISH_CSS = """
@page { size: A4; margin: 17mm 15mm; }
body { font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; color: #1f2328; font-size: 10.5pt; line-height: 1.55; }
h1 { font-size: 21pt; margin: 0 0 4px; }
h2 { font-size: 14pt; border-bottom: 1px solid #d0d7de; padding-bottom: 4px; margin-top: 20px; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin-top: 14px; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.8pt; page-break-inside: avoid; }
th, td { border: 1px solid #c9d1d9; padding: 4px 5px; text-align: left; vertical-align: top; }
th { background: #f3f4f6; }
.note { background: #ddf4ff; border-left: 4px solid #0969da; padding: 8px 10px; }
"""


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _find_edge() -> str:
    candidates = [
        os.environ.get("EDGE_BIN", ""),
        r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
        shutil.which("msedge") or "",
        shutil.which("microsoft-edge") or "",
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Microsoft Edge/Chromium not found; set EDGE_BIN to render the PDF")


def render_pdf(html_path: Path, pdf_path: Path) -> str:
    edge = _find_edge()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="eval045-edge-") as profile:
        cmd = [
            edge,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            "--virtual-time-budget=2000",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf_path.resolve()}",
            html_path.resolve().as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        raise RuntimeError(f"Edge print-to-pdf failed rc={proc.returncode}: {proc.stderr[-500:]}")
    if not pdf_path.exists() or pdf_path.stat().st_size < 1000 or not pdf_path.read_bytes().startswith(b"%PDF"):
        raise RuntimeError(f"PDF was not rendered correctly: {pdf_path}")
    return edge


def review_comments(draft_sha256: str, aggregate: dict, attribution: dict) -> list[dict]:
    low = aggregate["reviews"]["low_sample_groups"]
    low_text = "、".join(f"{g['tool_id']} 仅 {g['reviewed']} 条" for g in low) or "无低样本分组"
    reviews = aggregate["reviews"]
    return [
        {
            "comment_id": "R1",
            "problem": "管理摘要用约数，审计要求精确值。",
            "change": f"改为 {_fmt_int(reviews['total'])} 条，并同时列出 accepted {_fmt_int(reviews['accepted'])} / rejected {_fmt_int(reviews['rejected'])}。",
            "status": "resolved",
        },
        {
            "comment_id": "R2",
            "problem": f"{low_text}，低于 low_sample 阈值 {reviews['low_sample_threshold']}，却被纳入默认质量排名。",
            "change": "标注 low_sample，并从默认排名排除；单独列出样本量。",
            "status": "resolved",
        },
        {
            "comment_id": "R3",
            "problem": "P0 失败与普通退化事件混在同一张表，且缺少数据口径引用。",
            "change": "拆为退化事件表与 P0 失败表；新增数据口径与限制章节。",
            "status": "resolved",
        },
    ]


def _recovery_start(dataset: dict, incident: dict) -> str:
    run_id = incident.get("recovery_run_id")
    run = next((r for r in dataset["runs"] if r.get("run_id") == run_id), None)
    return run["started_at"] if run else "—"


def published_markdown(dataset: dict, aggregate: dict, attribution: dict, comments: list[dict]) -> str:
    runs = aggregate["runs"]
    reviews = aggregate["reviews"]
    redteam = aggregate["redteam"]
    incidents = attribution["incidents"]
    threshold = reviews["low_sample_threshold"]
    low = reviews["low_sample_groups"]
    ranked = sorted(
        [(t, s) for t, s in aggregate["tools"].items() if not s["low_sample"]],
        key=lambda kv: (-kv[1]["avg_quality_score"], kv[0]),
    )
    by_tool_reviews = reviews["by_tool"]
    reason_counts = [r["count"] for r in attribution["rejection_reasons"]]
    reason_total = sum(reason_counts)
    uniform_reasons = len(set(reason_counts)) == 1
    tools_count = len(dataset["tools"])
    runs_per_tool = runs["total"] // tools_count if tools_count else 0
    low_text = "、".join(f"{g['tool_id']} 仅 {g['reviewed']} 条" for g in low) or "无"
    lines = [
        "# 会员空间平台质量月报（2026-11）",
        "",
        "发布版 v2 · 审阅后 · 数据全部虚构",
        "",
        "数据期间：2026-11-01 至 2026-11-30。本报告用于演练月报生成、审阅与发布流程，不代表任何真实会员、员工或客户。",
        "",
        "## 管理摘要",
        "",
        f"- {tools_count} 个工具夜间运行 {runs['total']} 次，成功 {runs['success']} 次，成功率 {runs['success_rate_pct']:.4f}%。",
        f"- 共 {aggregate['incidents']['total']} 次事件：退化事件（{aggregate['incidents']['degraded']} 次）与 P0 失败（{aggregate['incidents']['p0_failure']} 次）。",
        f"- 本月复核事件 {_fmt_int(reviews['total'])} 条：accepted {_fmt_int(reviews['accepted'])} 条，rejected {_fmt_int(reviews['rejected'])} 条，拒绝率 {reviews['reject_rate_pct']:.4f}%。",
        f"- 红队发现 {redteam['total']} 条问题，覆盖 open、triaged、in_progress、fixed、verified 五种状态。",
        "- 红队状态分布：" + "、".join(f"{status} {redteam['by_status'][status]}" for status in ["open", "triaged", "in_progress", "fixed", "verified"]) + "。",
        f"- 全体运行平均质量分 {runs['avg_quality_score']:.4f}，全体运行 p95 延迟 {runs['p95_latency_ms']} ms。",
        "",
        "## 运行稳定性",
        "",
        f"### 退化事件（{aggregate['incidents']['degraded']} 次）",
        "",
        "| 事件 | 工具 | 日期 | 根因 | 影响 | 恢复 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i in incidents:
        if i["type"] != "degraded":
            continue
        lines.append(f"| {i['incident_id']} | {i['tool_id']} | {i['date']} | {i['root_cause']} | {i['impact']} | 当日恢复 |")
    lines += [
        "",
        f"### P0 失败（{aggregate['incidents']['p0_failure']} 次）",
        "",
        "| 事件 | 工具 | 日期 | 根因 | 恢复运行 | 恢复运行开始时间 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i in incidents:
        if i["type"] != "p0_failure":
            continue
        lines.append(
            f"| {i['incident_id']} | {i['tool_id']} | {i['date']} | {i['root_cause']} | {i.get('recovery_run_id') or '—'} | {_recovery_start(dataset, i)} |"
        )
    lines += [
        "",
        "AC3 截图：artifacts/AC3-events.png（由 scripts/make_ac3_shot.py 从种子数据生成；截图包含退化与 P0 记录）。",
        "",
        "## 工具质量排名",
        "",
        f"低样本分组 {low_text}，低于 low_sample 阈值 {threshold}，标注为 low_sample，不参与默认排名。默认排名覆盖其余 {len(ranked)} 个工具。",
        "",
        "| 排名 | 工具 | 运行次数 | 成功率 | 平均质量分 | p95 延迟(ms) | 复核条数 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rank, (tool, stat) in enumerate(ranked, start=1):
        success_rate = stat["success"] * 100.0 / stat["runs"] if stat["runs"] else 0.0
        lines.append(
            f"| {rank} | {tool} | {stat['runs']} | {success_rate:.2f}% | {stat['avg_quality_score']:.4f} | {stat['p95_latency_ms']} | {stat['reviews']} |"
        )
    if low:
        lines += [
            "",
            "### low_sample 分组",
            "",
            "| 工具 | 复核条数 | 阈值 | 处置 |",
            "| --- | --- | --- | --- |",
        ]
        for group in low:
            lines.append(f"| {group['tool_id']} | {group['reviewed']} | {threshold} | 标注 low_sample，不参与默认排名 |")
    lines += [
        "",
        "## 失败模式归因",
        "",
        "| 拒绝原因 | 条数 | 占拒绝总数 |",
        "| --- | --- | --- |",
    ]
    for reason in attribution["rejection_reasons"]:
        lines.append(f"| {reason['reason']} | {reason['count']} | {reason['share_pct']:.4f}% |")
    reason_note = f"{len(reason_counts)} 类拒绝原因" + ("各 " + str(reason_counts[0]) + " 条" if uniform_reasons else "计数不一") + f"，合计 {_fmt_int(reason_total)} 条"
    lines += [
        "",
        f"归因要点：{reason_note}；low_sample 分组仅影响排名资格，不改变拒绝率口径。",
        "",
        "## 审阅与发布",
        "",
        "| 意见 | 问题 | 处理 | 状态 |",
        "| --- | --- | --- | --- |",
    ]
    for c in comments:
        lines.append(f"| {c['comment_id']} | {c['problem']} | {c['change']} | {c['status']} |")
    lines += [
        "",
        f"本发布版由 EVAL-044 在草稿基础上应用上述 {len(comments)} 条审阅意见后生成。",
        "",
        "## 数据口径与限制",
        "",
        "| 指标 | 来源表 | 计算口径 |",
        "| --- | --- | --- |",
        f"| 运行总数 / 成功 / 退化 / 失败 | runs | 按 status 计数；每工具每日 1 条，共 {tools_count}×{runs_per_tool}={runs['total']} 条 |",
        "| 成功率 | runs | success / total × 100，保留 4 位小数 |",
        "| 退化 / P0 事件数 | incidents | 按 type 计数；P0 为 p0_failure |",
        f"| 复核总数 / accepted / rejected | review_events | 按 decision 计数；共 {_fmt_int(reviews['total'])} 条 |",
        "| 拒绝率 | review_events | rejected / total × 100，保留 4 位小数 |",
        "| 拒绝原因分布 | review_events | 仅 rejected 记录按 rejection_reason 分组 |",
        f"| low_sample 分组 | review_events | 每组 reviewed < {threshold} 时标注，不参与默认排名 |",
        "| p95 延迟 | runs | 最近秩法，排序后第 ceil(0.95×n) 个值 |",
        "| 平均质量分 | runs | quality_score 算术平均，保留 4 位小数 |",
        "",
        "限制：所有数据由固定种子 20261001 合成；EVAL-041..044 在仓库中以 stubs/ 最小实现替代，真实平台接入时需替换为上游模块。PDF 由本机 Microsoft Edge headless 渲染，未安装 Edge/Chromium 的环境需设置 EDGE_BIN 或改用其他渲染器。",
        "",
        "## 附录",
        "",
        f"- 种子：{dataset['seed']}",
        f"- 数据集生成时间：{dataset['generated_at']}",
        f"- 复核事件：{_fmt_int(reviews['total'])} 条；low_sample：{low_text}",
        "- 复现：python run_all.py",
        "- 数字核对：python scripts/verify_numbers.py",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="EVAL-044 review and publish stub")
    parser.add_argument("--dataset", default="out/seed_dataset.json")
    parser.add_argument("--aggregate", default="out/aggregate.json")
    parser.add_argument("--attribution", default="out/attribution.json")
    parser.add_argument("--draft", default="out/draft.md")
    parser.add_argument("--out-dir", default="out")
    args = parser.parse_args()
    dataset = load_json(args.dataset)
    aggregate = load_json(args.aggregate)
    attribution = load_json(args.attribution)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    draft_bytes = Path(args.draft).read_bytes()
    draft_sha = hashlib.sha256(draft_bytes).hexdigest()
    comments = review_comments(draft_sha, aggregate, attribution)
    md = published_markdown(dataset, aggregate, attribution, comments)
    md_path = out / "published_v2.md"
    html_path = out / "published_v2.html"
    pdf_path = out / "published_v2.pdf"
    md_path.write_text(md, encoding="utf-8")
    html = (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<title>会员空间平台质量月报 2026-11 · 发布版 v2</title>"
        f"<style>{PUBLISH_CSS}</style></head><body>{md_to_html(md)}</body></html>"
    )
    html_path.write_text(html, encoding="utf-8")
    edge = render_pdf(html_path, pdf_path)
    write_json(
        out / "review_comments.json",
        {"stage": "EVAL-044", "draft_sha256": draft_sha, "comments": comments, "published_version": "v2"},
    )
    write_json(
        out / "publish_manifest.json",
        {
            "stage": "EVAL-044",
            "published_version": "v2",
            "draft_sha256": draft_sha,
            "published_md_sha256": hashlib.sha256(md_path.read_bytes()).hexdigest(),
            "published_html_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
            "published_pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "published_pdf_bytes": pdf_path.stat().st_size,
            "edge_bin": Path(edge).name,
            "review_comments": len(comments),
        },
    )
    print(f"wrote {md_path}, {html_path}, {pdf_path} ({pdf_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
