"""Run all acceptance checks; only write PASS after every check succeeds."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
ACCEPTANCE_JSON = ARTIFACTS / "acceptance.json"
ACCEPTANCE_MD = ARTIFACTS / "ACCEPTANCE.md"
STALE = [
    ACCEPTANCE_JSON,
    ACCEPTANCE_MD,
    ARTIFACTS / "pii-scan.json",
    ARTIFACTS / "AC3-events.png",
    ARTIFACTS / "numbers_check.json",
    ROOT / "trace_checklist.md",
]
STAGES = ["seed", "eval041_aggregate", "eval042_attribute", "eval043_render", "eval044_review_publish"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_acceptance(all_passed: bool, checks: list[dict], tests_passed: int | None = None, detail: str = "") -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": now(),
        "all_passed": all_passed,
        "tests_passed": tests_passed,
        "checks": checks,
    }
    if detail:
        data["detail"] = detail
    ACCEPTANCE_JSON.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# ACCEPTANCE",
        "",
        f"Status: {'PASS' if all_passed else 'FAIL'}",
        "",
        f"Generated: {data['generated_at']}",
        "",
    ]
    if detail:
        lines += [f"Detail: {detail}", ""]
    lines += ["| Check | Status | Evidence |", "| --- | --- | --- |"]
    for check in checks:
        lines.append(f"| {check['name']} | {check['status']} | {check.get('detail', '')} |")
    lines.append("")
    ACCEPTANCE_MD.write_text("\n".join(lines), encoding="utf-8")


def run(command: list[str], name: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def old_evidence_removed() -> bool:
    return not any(path.exists() for path in STALE)


def parse_run_log() -> tuple[bool, str]:
    log = ROOT / "run.log"
    if not log.exists():
        return False, "missing run.log"
    text = log.read_text(encoding="utf-8")
    if "C:" in text or "\\" in text:
        return False, "run.log contains a local path"
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != len(STAGES):
        return False, f"expected {len(STAGES)} lines, got {len(lines)}"
    for line, stage in zip(lines, STAGES):
        entry = json.loads(line)
        if entry.get("stage") != stage:
            return False, f"stage order: expected {stage}, got {entry.get('stage')}"
        if entry.get("exit_code") != 0:
            return False, f"{stage} exit_code={entry.get('exit_code')}"
        if not entry.get("command") or entry["command"][0] != "python":
            return False, f"{stage} command is not public"
        for output in entry.get("outputs", []):
            path = ROOT / output["path"]
            if not path.exists() or sha256(path) != output["sha256"]:
                return False, f"{stage} output hash mismatch: {output['path']}"
    return True, f"stages={len(lines)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EVAL-045 acceptance checks")
    args = parser.parse_args()
    checks: list[dict] = []
    tests_passed = None
    preexisting = [str(p.relative_to(ROOT)) for p in STALE if p.exists()]
    for path in STALE:
        if path.exists():
            path.unlink()
    write_acceptance(False, checks, detail="acceptance started; stale evidence removed: " + (", ".join(preexisting) or "none"))

    def check(name: str, ok: bool, detail: str = "") -> bool:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
        return ok

    try:
        if not check(
            "stale_evidence",
            not any(p.exists() for p in [ARTIFACTS / "pii-scan.json", ARTIFACTS / "AC3-events.png", ARTIFACTS / "numbers_check.json", ROOT / "trace_checklist.md"]),
            "pre-run evidence was removed before pytest/pipeline",
        ):
            write_acceptance(False, checks, tests_passed)
            return 1

        pytest = run([sys.executable, "-m", "pytest", "-q"], "pytest")
        match = re.search(r"(\d+) passed", pytest.stdout)
        tests_passed = int(match.group(1)) if match else None
        if not check("pytest", pytest.returncode == 0 and bool(tests_passed), f"rc={pytest.returncode}; tests={tests_passed}"):
            write_acceptance(False, checks, tests_passed)
            return 1

        pipeline = run([sys.executable, "run_all.py"], "run_all")
        if not check("pipeline", pipeline.returncode == 0, f"rc={pipeline.returncode}"):
            write_acceptance(False, checks, tests_passed)
            return 1

        log_ok, log_detail = parse_run_log()
        if not check("run_log", log_ok, log_detail):
            write_acceptance(False, checks, tests_passed)
            return 1

        det_a = ROOT / "out" / "determinism-a.json"
        det_b = ROOT / "out" / "determinism-b.json"
        rc_a = run([sys.executable, "seed_month.py", "--out", str(det_a)], "seed_a").returncode
        rc_b = run([sys.executable, "seed_month.py", "--out", str(det_b)], "seed_b").returncode
        canonical = ROOT / "out" / "seed_dataset.json"
        det_ok = (
            rc_a == 0
            and rc_b == 0
            and det_a.exists()
            and det_b.exists()
            and det_a.read_bytes() == det_b.read_bytes()
            and det_a.read_bytes() == canonical.read_bytes()
        )
        det_sha = sha256(det_a) if det_a.exists() else "missing"
        if not check("determinism", det_ok, f"sha256={det_sha}"):
            write_acceptance(False, checks, tests_passed)
            return 1

        verify = run([sys.executable, "scripts/verify_numbers.py"], "verify_numbers")
        numbers = json.loads((ARTIFACTS / "numbers_check.json").read_text(encoding="utf-8")) if (ARTIFACTS / "numbers_check.json").exists() else {}
        trace_ok = (
            verify.returncode == 0
            and numbers.get("all_ok") is True
            and len(numbers.get("items", [])) == 15
            and len(numbers.get("coverage", [])) >= 20
        )
        if not check("trace_numbers", trace_ok, f"rc={verify.returncode} items={len(numbers.get('items', []))} coverage={len(numbers.get('coverage', []))}"):
            write_acceptance(False, checks, tests_passed)
            return 1

        pii = run(
            [sys.executable, "scripts/eval_pii_scan.py", "--path", "out/seed_dataset.json", "--json-out", "artifacts/pii-scan.json"],
            "pii_scan",
        )
        pii_data = json.loads((ARTIFACTS / "pii-scan.json").read_text(encoding="utf-8")) if (ARTIFACTS / "pii-scan.json").exists() else {}
        pii_ok = (
            pii.returncode == 0
            and pii_data.get("mode") == "mock"
            and pii_data.get("target_sha256") == sha256(ROOT / "out" / "seed_dataset.json")
            and pii_data.get("errors") == 0
            and not pii_data.get("findings")
            and pii_data.get("scanned_strings", 0) >= 1000
        )
        if not check("pii_scan", pii_ok, f"rc={pii.returncode} strings={pii_data.get('scanned_strings')} errors={pii_data.get('errors')}"):
            write_acceptance(False, checks, tests_passed)
            return 1

        shot = run([sys.executable, "scripts/make_ac3_shot.py"], "ac3_shot")
        png = ARTIFACTS / "AC3-events.png"
        width = height = 0
        colors = 0
        html = (ROOT / "out" / "ac3_events.html").read_text(encoding="utf-8") if (ROOT / "out" / "ac3_events.html").exists() else ""
        if png.exists():
            from PIL import Image

            with Image.open(png) as im:
                width, height = im.width, im.height
                colors = len(im.convert("RGB").getcolors(maxcolors=1_000_000) or [])
        shot_ok = (
            shot.returncode == 0
            and png.exists()
            and png.stat().st_size > 5000
            and (width, height) == (1400, 620)
            and colors > 20
            and "INC-DEG-01" in html
            and "INC-DEG-02" in html
            and "INC-P0-01" in html
        )
        if not check("ac3_screenshot", shot_ok, f"rc={shot.returncode} {width}x{height} colors={colors}"):
            write_acceptance(False, checks, tests_passed)
            return 1

        aggregate = json.loads((ROOT / "out" / "aggregate.json").read_text(encoding="utf-8"))
        attribution = json.loads((ROOT / "out" / "attribution.json").read_text(encoding="utf-8"))
        pdf = ROOT / "out" / "published_v2.pdf"
        docx = ROOT / "out" / "draft.docx"
        md = (ROOT / "out" / "published_v2.md").read_text(encoding="utf-8") if (ROOT / "out" / "published_v2.md").exists() else ""
        manifest = json.loads((ROOT / "out" / "publish_manifest.json").read_text(encoding="utf-8")) if (ROOT / "out" / "publish_manifest.json").exists() else {}
        comments = json.loads((ROOT / "out" / "review_comments.json").read_text(encoding="utf-8")) if (ROOT / "out" / "review_comments.json").exists() else {}
        expected = {
            "运行": f"{aggregate['runs']['total']} 次",
            "成功": f"{aggregate['runs']['success']} 次",
            "退化": f"退化事件（{aggregate['incidents']['degraded']} 次）",
            "P0": f"P0 失败（{aggregate['incidents']['p0_failure']} 次）",
            "复核": f"复核事件 {aggregate['reviews']['total']:,} 条",
            "排名": f"默认排名覆盖其余 {len([t for t, s in aggregate['tools'].items() if not s['low_sample']])} 个工具",
            "阈值": f"low_sample 阈值 {aggregate['reviews']['low_sample_threshold']}",
        }
        manifest_ok = (
            pdf.exists()
            and pdf.read_bytes().startswith(b"%PDF")
            and pdf.stat().st_size > 1000
            and docx.exists()
            and docx.stat().st_size > 5000
            and manifest.get("published_pdf_sha256") == sha256(pdf)
            and manifest.get("published_md_sha256") == sha256(ROOT / "out" / "published_v2.md")
            and manifest.get("published_html_sha256") == sha256(ROOT / "out" / "published_v2.html")
            and not str(manifest.get("edge_bin", "")).startswith(("C:", "/"))
            and len(comments.get("comments", [])) == 3
            and all(c.get("status") == "resolved" for c in comments.get("comments", []))
            and "约 3,000" not in md
            and all(token in md for token in expected.values())
            and all(reason["reason"] in md for reason in attribution["rejection_reasons"])
        )
        if not check("samples", manifest_ok, f"pdf={pdf.stat().st_size if pdf.exists() else 0}B docx={docx.stat().st_size if docx.exists() else 0}B"):
            write_acceptance(False, checks, tests_passed)
            return 1

        write_acceptance(True, checks, tests_passed)
        print("ACCEPTANCE PASS")
        return 0
    except subprocess.TimeoutExpired as exc:
        check("timeout", False, repr(exc)[:300])
        write_acceptance(False, checks, tests_passed, detail=repr(exc)[:500])
        print(f"ACCEPTANCE FAIL: timeout {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        check("exception", False, repr(exc)[:300])
        write_acceptance(False, checks, tests_passed, detail=repr(exc)[:500])
        print(f"ACCEPTANCE FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
