"""Render the AC3 evidence screenshot: 2 degraded events + 1 P0 failure."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stubs.common import load_json
from stubs.md import md_to_html


CSS = """
@page { size: 1400px 620px; margin: 0; }
body { font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; color: #1f2328; margin: 0; padding: 26px 40px; width: 1320px; }
h1 { font-size: 34px; margin: 0 0 6px; }
h2 { font-size: 23px; margin: 24px 0 8px; border-bottom: 2px solid #d0d7de; padding-bottom: 6px; }
p { font-size: 16px; margin: 4px 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 15px; }
th, td { border: 1px solid #b8c0c8; padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #f0f3f6; }
.card { display: inline-block; padding: 10px 16px; margin: 6px 10px 6px 0; border-radius: 8px; background: #fff4e5; border-left: 6px solid #d97706; font-size: 17px; }
.card.p0 { background: #ffebe9; border-left-color: #cf222e; }
.footer { color: #57606a; font-size: 13px; margin-top: 18px; }
"""


def find_edge() -> str:
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
    raise RuntimeError("Microsoft Edge/Chromium not found; set EDGE_BIN")


def build_html(dataset: dict, aggregate: dict) -> str:
    incidents = dataset["incidents"]
    lines = [
        "# AC3 运行稳定性证据",
        "",
        f"虚构数据演练 · {dataset['generated_at'][:10]} 生成 · 种子 {dataset['seed']}",
        "",
        f'<div class="card">退化事件：{aggregate["incidents"]["degraded"]} 次</div>',
        f'<div class="card p0">P0 失败：{aggregate["incidents"]["p0_failure"]} 次</div>',
        "",
        "## 退化事件",
        "",
        "| 事件 | 工具 | 日期 | 根因 | 影响 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i in incidents:
        if i["type"] == "degraded":
            lines.append(f"| {i['incident_id']} | {i['tool_id']} | {i['date']} | {i['root_cause']} | {i['impact']} |")
    lines += [
        "",
        "## P0 失败",
        "",
        "| 事件 | 工具 | 日期 | 根因 | 恢复运行 | 恢复运行开始时间 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i in incidents:
        if i["type"] == "p0_failure":
            run = next((r for r in dataset["runs"] if r.get("run_id") == i.get("recovery_run_id")), None)
            started = run["started_at"] if run else "—"
            lines.append(f"| {i['incident_id']} | {i['tool_id']} | {i['date']} | {i['root_cause']} | {i.get('recovery_run_id') or '—'} | {started} |")
    lines += ["", '<div class="footer">本图由 scripts/make_ac3_shot.py 从 out/seed_dataset.json 生成；数据全部虚构。</div>']
    body = md_to_html("\n".join(lines))
    return f"<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>AC3 events</title><style>{CSS}</style></head><body>{body}</body></html>"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AC3 events HTML and screenshot")
    parser.add_argument("--dataset", default="out/seed_dataset.json")
    parser.add_argument("--aggregate", default="out/aggregate.json")
    parser.add_argument("--out-html", default="out/ac3_events.html")
    parser.add_argument("--out-png", default="artifacts/AC3-events.png")
    args = parser.parse_args()
    dataset = load_json(args.dataset)
    aggregate = load_json(args.aggregate)
    html_path = Path(args.out_html)
    png_path = Path(args.out_png)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(build_html(dataset, aggregate), encoding="utf-8")
    edge = find_edge()
    with tempfile.TemporaryDirectory(prefix="eval045-shot-") as profile:
        cmd = [
            edge,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--window-size=1400,620",
            f"--user-data-dir={profile}",
            f"--screenshot={png_path.resolve()}",
            html_path.resolve().as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0 or not png_path.exists() or png_path.stat().st_size < 5000:
        raise RuntimeError(f"screenshot failed rc={proc.returncode}: {proc.stderr[-500:]}")
    from PIL import Image

    with Image.open(png_path) as im:
        print(f"wrote {png_path} ({png_path.stat().st_size} bytes, {im.width}x{im.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
