"""Local mock eval-pii-scan: flag common PII patterns in a dataset or literal text.

This is a stand-in for the platform's eval-pii-scan; it is deliberately small and
documented as a mock in README.md.  It exits 1 when it finds an error-level match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone_cn": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "id_card_cn": re.compile(r"(?<![0-9A-Za-z])\d{17}[\dXx](?![0-9A-Za-z])"),
    "bank_card": re.compile(r"(?<!\d)\d{16,19}(?!\d)"),
    "token": re.compile(r"(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._-]{20,})"),
}


def walk_strings(value: object, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.append((f"{path}.<key>", key))
            found.extend(walk_strings(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(walk_strings(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append((path, value))
    return found


def scan_strings(pairs: list[tuple[str, str]]) -> list[dict]:
    findings = []
    for path, text in pairs:
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                raw = match.group(0)
                findings.append(
                    {
                        "pattern": name,
                        "path": path,
                        "excerpt": raw[:4] + "***" if len(raw) > 4 else "***",
                        "length": len(raw),
                    }
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock eval-pii-scan")
    parser.add_argument("--path", help="JSON dataset to scan")
    parser.add_argument("--text", help="Literal text to scan")
    parser.add_argument("--json-out", help="Optional path for machine-readable output")
    args = parser.parse_args()
    if not args.path and args.text is None:
        parser.error("provide --path or --text")
    target_sha256 = None
    if args.path:
        raw = Path(args.path).read_bytes()
        target_sha256 = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw.decode("utf-8"))
        pairs = walk_strings(data)
        target = args.path
    else:
        pairs = [("$text", args.text or "")]
        target = "<text>"
    findings = scan_strings(pairs)
    result = {
        "tool": "eval-pii-scan",
        "mode": "mock",
        "target": target,
        "target_sha256": target_sha256,
        "scanned_strings": len(pairs),
        "errors": len(findings),
        "findings": findings,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
