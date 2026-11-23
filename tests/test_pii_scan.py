from seed_month import build_dataset, dumps_dataset
from scripts.eval_pii_scan import scan_strings, walk_strings


def test_seed_dataset_has_no_pii():
    data = build_dataset()
    findings = scan_strings(walk_strings(data))
    assert findings == []


def test_pii_scanner_flags_negative_example():
    email = "user" + "@" + "example.invalid"
    token = "ghp_" + "x" * 36
    findings = scan_strings([("$text", f"mail {email} token {token}")])
    names = {f["pattern"] for f in findings}
    assert "email" in names
    assert "token" in names


def test_pii_scanner_is_deterministic():
    data = build_dataset()
    a = scan_strings(walk_strings(data))
    b = scan_strings(walk_strings(data))
    assert a == b
    assert dumps_dataset(data) == dumps_dataset(build_dataset())
