"""EVAL-041 local stub: aggregate the seed month into report metrics."""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stubs.common import load_json, p95, pct, write_json

REASONS = [
    "low_confidence",
    "policy_violation",
    "duplicate",
    "missing_context",
    "out_of_scope",
    "format_error",
    "manual_reject",
]
STATUSES = ["success", "degraded", "failed"]
REDTEAM_STATUSES = ["open", "triaged", "in_progress", "fixed", "verified"]
LOW_SAMPLE_THRESHOLD = 30


def aggregate(dataset: dict, dataset_sha256: str) -> dict:
    runs = dataset["runs"]
    reviews = dataset["review_events"]
    incidents = dataset["incidents"]
    redteam = dataset["redteam_findings"]

    run_status = Counter(r["status"] for r in runs)
    review_decision = Counter(e["decision"] for e in reviews)
    reason_counts = Counter(e["rejection_reason"] for e in reviews if e["decision"] == "rejected")
    redteam_status = Counter(f["status"] for f in redteam)
    incident_type = Counter(i["type"] for i in incidents)

    tools = {}
    for tool in dataset["tools"]:
        tr = [r for r in runs if r["tool_id"] == tool]
        te = [e for e in reviews if e["tool_id"] == tool]
        tr_status = Counter(r["status"] for r in tr)
        tools[tool] = {
            "runs": len(tr),
            "success": tr_status.get("success", 0),
            "degraded": tr_status.get("degraded", 0),
            "failed": tr_status.get("failed", 0),
            "avg_quality_score": round(sum(r["quality_score"] for r in tr) / len(tr), 4) if tr else 0.0,
            "p95_latency_ms": p95([r["latency_ms"] for r in tr]),
            "reviews": len(te),
            "rejected": sum(1 for e in te if e["decision"] == "rejected"),
            "low_sample": len(te) < LOW_SAMPLE_THRESHOLD,
        }

    low_sample_groups = [
        {
            "tool_id": tool,
            "reviewed": len([e for e in reviews if e["tool_id"] == tool]),
            "threshold": LOW_SAMPLE_THRESHOLD,
            "is_low_sample": len([e for e in reviews if e["tool_id"] == tool]) < LOW_SAMPLE_THRESHOLD,
        }
        for tool in dataset["tools"]
        if len([e for e in reviews if e["tool_id"] == tool]) < LOW_SAMPLE_THRESHOLD
    ]

    latencies = [r["latency_ms"] for r in runs]
    qualities = [r["quality_score"] for r in runs]
    return {
        "meta": {
            "schema_version": "eval045.aggregate.v1",
            "seed": dataset["seed"],
            "month": dataset["month"],
            "dataset_sha256": dataset_sha256,
        },
        "runs": {
            "total": len(runs),
            "success": run_status.get("success", 0),
            "degraded": run_status.get("degraded", 0),
            "failed": run_status.get("failed", 0),
            "success_rate_pct": pct(run_status.get("success", 0), len(runs)),
            "avg_quality_score": round(sum(qualities) / len(qualities), 4) if qualities else 0.0,
            "p95_latency_ms": p95(latencies),
        },
        "incidents": {
            "total": len(incidents),
            "degraded": incident_type.get("degraded", 0),
            "p0_failure": incident_type.get("p0_failure", 0),
        },
        "redteam": {
            "total": len(redteam),
            "by_status": {s: redteam_status.get(s, 0) for s in REDTEAM_STATUSES},
        },
        "reviews": {
            "total": len(reviews),
            "accepted": review_decision.get("accepted", 0),
            "rejected": review_decision.get("rejected", 0),
            "reject_rate_pct": pct(review_decision.get("rejected", 0), len(reviews)),
            "by_reason": {r: reason_counts.get(r, 0) for r in REASONS},
            "by_tool": {t: {"reviewed": len([e for e in reviews if e["tool_id"] == t])} for t in dataset["tools"]},
            "low_sample_groups": low_sample_groups,
            "low_sample_threshold": LOW_SAMPLE_THRESHOLD,
        },
        "tools": tools,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="EVAL-041 aggregate stub")
    parser.add_argument("--dataset", default="out/seed_dataset.json")
    parser.add_argument("--out", default="out/aggregate.json")
    args = parser.parse_args()
    dataset_path = Path(args.dataset)
    raw = dataset_path.read_bytes()
    dataset = load_json(dataset_path)
    result = aggregate(dataset, hashlib.sha256(raw).hexdigest())
    write_json(args.out, result)
    print(f"wrote {args.out}: runs={result['runs']['total']} reviews={result['reviews']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
