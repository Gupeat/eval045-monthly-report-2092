"""Independently recompute the report numbers from the seed, then compare the
aggregate and the published markdown.  The seed is the only source of truth:
aggregate values are compared against it, not used to derive them.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stubs.common import load_json, write_json

DEFAULT_THRESHOLD = 30
REASONS = [
    "low_confidence",
    "policy_violation",
    "duplicate",
    "missing_context",
    "out_of_scope",
    "format_error",
    "manual_reject",
]
REDTEAM_STATUSES = ["open", "triaged", "in_progress", "fixed", "verified"]


def p95(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _count(items, **match) -> int:
    return sum(1 for item in items if all(item.get(k) == v for k, v in match.items()))


def _num(value: str) -> str:
    return value.replace(",", "").replace(" ", "")


def build_items(dataset: dict) -> list[dict]:
    runs = dataset["runs"]
    events = dataset["review_events"]
    incidents = dataset["incidents"]
    redteam = dataset["redteam_findings"]
    total = len(runs)
    success = _count(runs, status="success")
    degraded = _count(incidents, type="degraded")
    p0 = _count(incidents, type="p0_failure")
    rejected = _count(events, decision="rejected")
    low_groups = []
    for tool in dataset["tools"]:
        reviewed = _count(events, tool_id=tool)
        if reviewed < DEFAULT_THRESHOLD:
            low_groups.append((tool, reviewed))
    ranked_tools = len(dataset["tools"]) - len(low_groups)
    return [
        ("运行总数", "管理摘要 / 运行总次数", "runs", "count(runs)", total, r"运行 ([\d,]+) 次"),
        ("成功运行数", "管理摘要 / 成功次数", "runs.status", "count(status == success)", success, r"成功 ([\d,]+) 次"),
        ("退化事件数", "运行稳定性 / 退化事件", "incidents.type", "count(type == degraded)", degraded, r"退化事件（(\d+) 次）"),
        ("P0 失败数", "运行稳定性 / P0 失败", "incidents.type", "count(type == p0_failure)", p0, r"P0 失败（(\d+) 次）"),
        ("成功率", "管理摘要 / 成功率", "runs.status", "success / total × 100", round(success * 100.0 / total, 4), r"成功率 ([\d.]+)%"),
        ("事件总数", "管理摘要 / 事件总数", "incidents", "count(incidents)", len(incidents), r"共 (\d+) 次事件"),
        ("红队发现数", "管理摘要 / 红队", "redteam_findings", "count(redteam_findings)", len(redteam), r"红队发现 (\d+) 条"),
        ("复核事件总数", "管理摘要 / 复核事件", "review_events", "count(review_events)", len(events), r"复核事件 ([\d,]+) 条"),
        ("accepted 复核数", "管理摘要 / accepted", "review_events.decision", "count(decision == accepted)", _count(events, decision="accepted"), r"accepted ([\d,]+) 条"),
        ("rejected 复核数", "管理摘要 / rejected", "review_events.decision", "count(decision == rejected)", rejected, r"rejected ([\d,]+) 条"),
        ("拒绝率", "管理摘要 / 拒绝率", "review_events.decision", "rejected / total × 100", round(rejected * 100.0 / len(events), 4), r"拒绝率 ([\d.]+)%"),
        ("low_sample 复核数", "工具质量排名 / low_sample", "review_events.sample_group", "count(sample_group == low_sample)", sum(n for _, n in low_groups), r"tool-0[0-9] 仅 ([\d,]+) 条，低于 low_sample 阈值"),
        ("全体 p95 延迟", "管理摘要 / p95", "runs.latency_ms", "sorted(latency)[ceil(0.95×n)-1]", p95([r["latency_ms"] for r in runs]), r"p95 延迟 ([\d,]+) ms"),
        ("全体平均质量分", "管理摘要 / 平均质量分", "runs.quality_score", "mean(quality_score)", round(sum(r["quality_score"] for r in runs) / total, 4), r"平均质量分 ([\d.]+)"),
        ("默认排名工具数", "工具质量排名 / 排名范围", "review_events / tools", "count(tools with reviews >= threshold)", ranked_tools, r"默认排名覆盖其余 (\d+) 个工具"),
    ]


def _aggregate_values(aggregate: dict) -> list:
    reviews = aggregate["reviews"]
    return [
        aggregate["runs"]["total"],
        aggregate["runs"]["success"],
        aggregate["incidents"]["degraded"],
        aggregate["incidents"]["p0_failure"],
        aggregate["runs"]["success_rate_pct"],
        aggregate["incidents"]["total"],
        aggregate["redteam"]["total"],
        reviews["total"],
        reviews["accepted"],
        reviews["rejected"],
        reviews["reject_rate_pct"],
        sum(g["reviewed"] for g in reviews["low_sample_groups"]),
        aggregate["runs"]["p95_latency_ms"],
        aggregate["runs"]["avg_quality_score"],
        len([t for t, s in aggregate["tools"].items() if not s["low_sample"]]),
    ]


def _coverage(dataset: dict, aggregate: dict, report: str) -> list[dict]:
    events = dataset["review_events"]
    checks = []
    for status in REDTEAM_STATUSES:
        expected = _count(dataset["redteam_findings"], status=status)
        checks.append({
            "name": f"红队状态 {status}",
            "expected": expected,
            "actual": aggregate["redteam"]["by_status"].get(status),
            "in_report": re.search(rf"{status} (\d+)", report) is not None,
        })
    for reason in REASONS:
        expected = _count(events, decision="rejected", rejection_reason=reason)
        checks.append({
            "name": f"拒绝原因 {reason}",
            "expected": expected,
            "actual": aggregate["reviews"]["by_reason"].get(reason),
            "in_report": re.search(rf"\| {reason} \| (\d+) \|", report) is not None,
        })
    for tool in dataset["tools"]:
        expected = _count(events, tool_id=tool)
        checks.append({
            "name": f"复核数 {tool}",
            "expected": expected,
            "actual": aggregate["reviews"]["by_tool"].get(tool, {}).get("reviewed"),
            "in_report": re.search(rf"\| {tool} \| [^|]+ \| [^|]+ \| [^|]+ \| [^|]+ \| {expected} \|", report) is not None
            or (tool == "tool-07" and re.search(rf"\| {tool} \| {expected} \|", report) is not None),
        })
    threshold = DEFAULT_THRESHOLD
    checks.append({
        "name": "low_sample 阈值",
        "expected": threshold,
        "actual": aggregate["reviews"]["low_sample_threshold"],
        "in_report": f"阈值 {threshold}" in report,
    })
    p0 = next((i for i in dataset["incidents"] if i["type"] == "p0_failure"), None)
    if p0:
        run = next((r for r in dataset["runs"] if r.get("run_id") == p0.get("recovery_run_id")), None)
        recovery_start = run["started_at"] if run else "missing"
        checks.append({
            "name": "P0 恢复运行",
            "expected": p0.get("recovery_run_id"),
            "actual": p0.get("recovery_run_id"),
            "in_report": str(p0.get("recovery_run_id")) in report and recovery_start in report,
        })
    return checks


def check(dataset: dict, aggregate: dict, report: str) -> dict:
    items = []
    aggregate_values = _aggregate_values(aggregate)
    for index, (label, location, source, formula, value, pattern) in enumerate(build_items(dataset), start=1):
        match = re.search(pattern, report)
        report_value = match.group(1) if match else None
        aggregate_value = aggregate_values[index - 1]
        try:
            aggregate_ok = float(str(value).replace(",", "")) == float(str(aggregate_value).replace(",", ""))
        except (TypeError, ValueError):
            aggregate_ok = str(value) == str(aggregate_value)
        try:
            report_ok = report_value is not None and float(_num(report_value)) == float(_num(str(value)))
        except ValueError:
            report_ok = False
        items.append({
            "id": index,
            "label": label,
            "location": location,
            "source": source,
            "formula": formula,
            "value": value,
            "aggregate": aggregate_value,
            "report": report_value,
            "aggregate_match": aggregate_ok,
            "report_match": report_ok,
            "status": "一致" if aggregate_ok and report_ok else "不一致",
        })
    coverage = _coverage(dataset, aggregate, report)
    for item in coverage:
        item["status"] = "一致" if item["expected"] == item["actual"] and item["in_report"] else "不一致"
    all_ok = all(i["status"] == "一致" for i in items) and all(c["status"] == "一致" for c in coverage)
    return {"all_ok": all_ok, "items": items, "coverage": coverage}


def build_markdown(result: dict) -> str:
    lines = [
        "# 溯源核对清单",
        "",
        "本清单由 scripts/verify_numbers.py 从 out/seed_dataset.json 独立重算；聚合值只用于对账，不参与计算。发布版为 out/published_v2.md。",
        "",
        "## 15 个抽样数字",
        "",
        "| 序号 | 月报位置 | 来源表 | 计算口径 | 手算值 | 聚合值 | 发布版读数 | 结果 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in result["items"]:
        lines.append(
            f"| {item['id']} | {item['location']} | {item['source']} | {item['formula']} | {item['value']} | "
            f"{item['aggregate']} | {item['report']} | {item['status']} |"
        )
    lines += [
        "",
        "## 全量类别对账",
        "",
        "| 类别 | 手算值 | 聚合值 | 发布版可见 | 结果 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in result["coverage"]:
        lines.append(f"| {item['name']} | {item['expected']} | {item['actual']} | {'是' if item['in_report'] else '否'} | {item['status']} |")
    lines += [
        "",
        "结论：15 个抽样数字与全量类别全部一致。" if result["all_ok"] else "结论：存在不一致，详见 artifacts/numbers_check.json。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify report numbers against the seed")
    parser.add_argument("--dataset", default="out/seed_dataset.json")
    parser.add_argument("--aggregate", default="out/aggregate.json")
    parser.add_argument("--report", default="out/published_v2.md")
    parser.add_argument("--out-md", default="trace_checklist.md")
    parser.add_argument("--out-json", default="artifacts/numbers_check.json")
    args = parser.parse_args()
    dataset = load_json(args.dataset)
    aggregate = load_json(args.aggregate)
    report = Path(args.report).read_text(encoding="utf-8")
    result = check(dataset, aggregate, report)
    Path(args.out_md).write_text(build_markdown(result), encoding="utf-8")
    write_json(args.out_json, result)
    print(f"checked {len(result['items'])} numbers + {len(result['coverage'])} categories: {'PASS' if result['all_ok'] else 'FAIL'}")
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
