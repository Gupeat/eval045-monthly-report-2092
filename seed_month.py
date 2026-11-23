"""Deterministic synthetic dataset for the EVAL-045 monthly-report drill.

The dataset is entirely fictional.  It is generated from a single fixed seed
and contains no member, employee, or customer records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SEED = 20261001
BASE_DAY = date(2026, 11, 1)
DAYS = 30
TOOLS = [f"tool-{i:02d}" for i in range(1, 8)]
REJECTION_REASONS = [
    "low_confidence",
    "policy_violation",
    "duplicate",
    "missing_context",
    "out_of_scope",
    "format_error",
    "manual_reject",
]
TOOL_REVIEW_COUNTS = {
    "tool-01": 497,
    "tool-02": 497,
    "tool-03": 497,
    "tool-04": 497,
    "tool-05": 497,
    "tool-06": 496,
    "tool-07": 19,
}
LOW_SAMPLE_THRESHOLD = 30


def _iso(day: date, hour: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _incidents() -> list[dict]:
    return [
        {
            "incident_id": "INC-DEG-01",
            "type": "degraded",
            "tool_id": "tool-02",
            "date": "2026-11-08",
            "started_at": "2026-11-08T02:00:00Z",
            "detected_at": "2026-11-08T02:18:00Z",
            "resolved_at": "2026-11-08T05:40:00Z",
            "status": "resolved",
            "root_cause": "上游模型超时率升高，重试后质量分下降",
            "impact": "tool-02 当日质量分低于基线，未影响其他工具",
        },
        {
            "incident_id": "INC-P0-01",
            "type": "p0_failure",
            "tool_id": "tool-03",
            "date": "2026-11-11",
            "started_at": "2026-11-11T02:00:00Z",
            "detected_at": "2026-11-11T02:03:00Z",
            "resolved_at": "2026-11-12T06:00:00Z",
            "status": "resolved",
            "root_cause": "向量库连接池耗尽，夜间批处理无法建立连接",
            "impact": "tool-03 当日运行失败；次日恢复运行成功",
            "recovery_run_id": "run-20261112-tool-03",
        },
        {
            "incident_id": "INC-DEG-02",
            "type": "degraded",
            "tool_id": "tool-05",
            "date": "2026-11-19",
            "started_at": "2026-11-19T02:00:00Z",
            "detected_at": "2026-11-19T02:11:00Z",
            "resolved_at": "2026-11-19T04:55:00Z",
            "status": "resolved",
            "root_cause": "检索索引合并延迟，召回率短时下降",
            "impact": "tool-05 当日质量分低于基线，未影响其他工具",
        },
    ]


def _runs(rng: random.Random) -> list[dict]:
    special = {
        ("2026-11-08", "tool-02"): ("degraded", "INC-DEG-01"),
        ("2026-11-11", "tool-03"): ("failed", "INC-P0-01"),
        ("2026-11-19", "tool-05"): ("degraded", "INC-DEG-02"),
    }
    runs = []
    for day_index in range(DAYS):
        day = BASE_DAY + timedelta(days=day_index)
        day_s = day.isoformat()
        for tool_index, tool in enumerate(TOOLS, start=1):
            status, incident_id = special.get((day_s, tool), ("success", None))
            recovery_of = None
            if day_s == "2026-11-12" and tool == "tool-03":
                recovery_of = "INC-P0-01"
            if status == "failed":
                quality = 0.0
                latency = 30000 + rng.randint(0, 5000)
            elif status == "degraded":
                quality = round(rng.uniform(0.35, 0.55), 4)
                latency = rng.randint(6000, 12000)
            else:
                quality = round(rng.uniform(0.72, 0.99), 4)
                latency = rng.randint(800, 4200)
            runs.append(
                {
                    "run_id": f"run-{day.strftime('%Y%m%d')}-{tool}",
                    "tool_id": tool,
                    "date": day_s,
                    "started_at": _iso(day, 1 + tool_index),
                    "status": status,
                    "quality_score": quality,
                    "latency_ms": latency,
                    "incident_id": incident_id,
                    "recovery_of": recovery_of,
                }
            )
    return runs


def _redteam() -> list[dict]:
    statuses = ["open", "triaged", "in_progress", "fixed", "verified"]
    titles = [
        "低样本分组被错误纳入默认排名",
        "P0 失败与普通退化在同一表格中混写",
        "审阅意见缺少数据口径引用",
        "月报摘要使用约数而非精确值",
        "拒绝原因分组口径未在报告中说明",
        "PDF 页眉页码在部分阅读器中缺失",
        "复核事件去重规则未写入 README",
        "质量分四舍五入规则未披露",
        "退化事件未标注恢复时间",
        "失败模式归因缺少工单号",
        "low_sample 阈值硬编码为 30",
        "报告生成依赖本机 Edge 路径",
    ]
    findings = []
    for i, title in enumerate(titles, start=1):
        findings.append(
            {
                "finding_id": f"RT-{i:02d}",
                "title": title,
                "severity": ["low", "medium", "high"][i % 3],
                "status": statuses[(i - 1) % len(statuses)],
                "owner_ticket": f"EVAL-045-{i:02d}",
            }
        )
    return findings


def _review_events(rng: random.Random) -> list[dict]:
    events = []
    index = 0
    for tool in TOOLS:
        count = TOOL_REVIEW_COUNTS[tool]
        for _ in range(count):
            slot = (index * 7919) % 3000
            rejected = slot < 700
            reason = REJECTION_REASONS[slot % 7] if rejected else None
            decision = "rejected" if rejected else "accepted"
            events.append(
                {
                    "event_id": f"review-{index + 1:04d}",
                    "tool_id": tool,
                    "reviewer_id": f"rev-{rng.randint(1, 20):02d}",
                    "sample_group": "low_sample" if tool == "tool-07" else "standard",
                    "decision": decision,
                    "rejection_reason": reason,
                    "reviewed_at": _iso(BASE_DAY + timedelta(days=slot % 30), 6 + (slot % 12)),
                }
            )
            index += 1
    return events


def build_dataset(seed: int = SEED) -> dict:
    rng = random.Random(seed)
    runs = _runs(rng)
    events = _review_events(rng)
    return {
        "schema_version": "eval045.seed.v1",
        "seed": seed,
        "month": "2026-11",
        "generated_at": "2026-12-01T00:00:00Z",
        "fictional": True,
        "tools": TOOLS,
        "runs": runs,
        "incidents": _incidents(),
        "redteam_findings": _redteam(),
        "review_events": events,
    }


def dumps_dataset(dataset: dict) -> str:
    return json.dumps(dataset, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_dataset(path: Path, seed: int = SEED) -> str:
    data = dumps_dataset(build_dataset(seed))
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the deterministic EVAL-045 synthetic month")
    parser.add_argument("--out", default="out/seed_dataset.json")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    out = Path(args.out)
    digest = write_dataset(out, args.seed)
    print(f"wrote {out} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
