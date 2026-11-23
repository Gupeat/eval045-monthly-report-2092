"""Run the EVAL-041..044 drill in order and record exit codes/artifact hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
LOG = ROOT / "run.log"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_command(command: list[str]) -> list[str]:
    return ["python" if index == 0 else part for index, part in enumerate(command)]


def record_failure(stage: str, command: list[str], returncode: int, stderr: str) -> None:
    issue = ROOT / "issue_list.md"
    marker = "## 运行失败（自动记录）"
    text = issue.read_text(encoding="utf-8") if issue.exists() else "# 问题清单\n"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n"
    text += "\n" + marker + "\n"
    text += (
        f"\n### {stage}\n\n"
        f"- 命令：`{' '.join(public_command(command))}`\n"
        f"- 退出码：{returncode}\n"
        f"- stderr 摘要：{stderr.strip()[-500:] or '(empty)'}\n"
        f"- 处理建议：修复后重跑 python run_all.py；断点即本阶段。\n"
    )
    issue.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full EVAL-045 monthly-report drill")
    parser.add_argument("--seed", type=int, default=20261001)
    args = parser.parse_args()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    stages = [
        (
            "seed",
            [sys.executable, "seed_month.py", "--out", "out/seed_dataset.json", "--seed", str(args.seed)],
            ["out/seed_dataset.json"],
        ),
        (
            "eval041_aggregate",
            [sys.executable, "stubs/eval041_aggregate.py", "--dataset", "out/seed_dataset.json", "--out", "out/aggregate.json"],
            ["out/aggregate.json"],
        ),
        (
            "eval042_attribute",
            [
                sys.executable,
                "stubs/eval042_attribute.py",
                "--dataset",
                "out/seed_dataset.json",
                "--aggregate",
                "out/aggregate.json",
                "--out",
                "out/attribution.json",
            ],
            ["out/attribution.json"],
        ),
        (
            "eval043_render",
            [
                sys.executable,
                "stubs/eval043_render.py",
                "--dataset",
                "out/seed_dataset.json",
                "--aggregate",
                "out/aggregate.json",
                "--attribution",
                "out/attribution.json",
                "--out-dir",
                "out",
            ],
            ["out/draft.md", "out/draft.html", "out/draft.docx"],
        ),
        (
            "eval044_review_publish",
            [
                sys.executable,
                "stubs/eval044_review_publish.py",
                "--dataset",
                "out/seed_dataset.json",
                "--aggregate",
                "out/aggregate.json",
                "--attribution",
                "out/attribution.json",
                "--draft",
                "out/draft.md",
                "--out-dir",
                "out",
            ],
            ["out/published_v2.md", "out/published_v2.html", "out/published_v2.pdf", "out/review_comments.json", "out/publish_manifest.json"],
        ),
    ]
    log_lines: list[str] = []
    for stage, command, outputs in stages:
        started = time.perf_counter()
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        duration_ms = round((time.perf_counter() - started) * 1000)
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        missing = [p for p in outputs if not (ROOT / p).exists()]
        if proc.returncode != 0 or missing:
            record_failure(stage, command, proc.returncode, proc.stderr + (" missing=" + ",".join(missing) if missing else ""))
            print(f"FAILED stage={stage} rc={proc.returncode} missing={missing}", file=sys.stderr)
            return 1
        log_lines.append(
            json.dumps(
                {
                    "stage": stage,
                    "command": public_command(command),
                    "exit_code": proc.returncode,
                    "duration_ms": duration_ms,
                    "outputs": [
                        {"path": p, "sha256": sha256(ROOT / p), "bytes": (ROOT / p).stat().st_size}
                        for p in outputs
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        print(f"PASS {stage} ({duration_ms} ms)")
    LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"wrote {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
