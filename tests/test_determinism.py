import hashlib
import subprocess
import sys
from pathlib import Path

from seed_month import build_dataset, dumps_dataset


def test_same_seed_same_bytes_in_memory():
    a = dumps_dataset(build_dataset())
    b = dumps_dataset(build_dataset())
    assert a == b
    assert hashlib.sha256(a.encode("utf-8")).hexdigest() == hashlib.sha256(b.encode("utf-8")).hexdigest()


def test_two_cli_runs_match(tmp_path):
    root = Path(__file__).resolve().parents[1]
    paths = [tmp_path / "a.json", tmp_path / "b.json"]
    for path in paths:
        subprocess.run(
            [sys.executable, "seed_month.py", "--out", str(path)],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    assert paths[0].read_bytes() == paths[1].read_bytes()
