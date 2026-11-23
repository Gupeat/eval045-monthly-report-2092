"""EVAL-042 local stub: attribute failures and review rejections."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stubs.common import load_json, pct, write_json

REASONS = [
    "low_confidence",
    "policy_violation",
    "duplicate",
    "missing_context",
    "out_of_scope",
    "format_error",
    "manual_reject",
]


def _insights(dataset: dict, aggregate: dict, reason_counts, by_tool: dict, rejected: list) -> list[str]:
    threshold = aggregate["reviews"]["low_sample_threshold"]
    low = [
        f"{tool} 仅 {stat['reviewed']} 条"
        for tool, stat in by_tool.items()
        if stat["low_sample"]
    ]
    low_text = "、".join(low) or "无低样本分组"
    counts = list(reason_counts.values())
    uniform = len(set(counts)) == 1
    reason_text = f"{len(REASONS)} 类拒绝原因" + ("各 " + str(counts[0]) + " 条" if uniform else "计数不一")
    incidents = dataset["incidents"]
    degraded = [i for i in incidents if i["type"] == "degraded"]
    p0 = [i for i in incidents if i["type"] == "p0_failure"]
    p0_text = "；".join(f"{i['incident_id']} 为 {i['tool_id']} {i['root_cause']}" for i in p0) or "无 P0"
    return [
        f"low_sample 分组 {low_text}，低于阈值 {threshold}，不能参与默认质量排名。",
        f"{reason_text}，拒绝总数 {len(rejected)}，拒绝率 {aggregate['reviews']['reject_rate_pct']:.4f}%。",
        f"{len(degraded)} 次退化为单工具当日质量下降；{p0_text}。",
    ]


def attribute(dataset: dict, aggregate: dict) -> dict:
    reviews = dataset["review_events"]
    rejected = [e for e in reviews if e["decision"] == "rejected"]
    reason_counts = Counter(e["rejection_reason"] for e in rejected)
    by_tool = {}
    for tool in dataset["tools"]:
        te = [e for e in reviews if e["tool_id"] == tool]
        tr = [e for e in te if e["decision"] == "rejected"]
        by_tool[tool] = {
            "reviewed": len(te),
            "rejected": len(tr),
            "reject_rate_pct": pct(len(tr), len(te)),
            "low_sample": len(te) < aggregate["reviews"]["low_sample_threshold"],
        }
    return {
        "meta": {
            "schema_version": "eval045.attribution.v1",
            "seed": dataset["seed"],
            "month": dataset["month"],
        },
        "incidents": [
            {
                "incident_id": i["incident_id"],
                "type": i["type"],
                "tool_id": i["tool_id"],
                "date": i["date"],
                "root_cause": i["root_cause"],
                "impact": i["impact"],
                "recovery_run_id": i.get("recovery_run_id"),
            }
            for i in dataset["incidents"]
        ],
        "rejection_reasons": [
            {
                "reason": reason,
                "count": reason_counts.get(reason, 0),
                "share_pct": pct(reason_counts.get(reason, 0), len(rejected)),
            }
            for reason in REASONS
        ],
        "by_tool": by_tool,
        "insights": _insights(dataset, aggregate, reason_counts, by_tool, rejected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="EVAL-042 attribution stub")
    parser.add_argument("--dataset", default="out/seed_dataset.json")
    parser.add_argument("--aggregate", default="out/aggregate.json")
    parser.add_argument("--out", default="out/attribution.json")
    args = parser.parse_args()
    result = attribute(load_json(args.dataset), load_json(args.aggregate))
    write_json(args.out, result)
    print(f"wrote {args.out}: incidents={len(result['incidents'])} reasons={len(result['rejection_reasons'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
