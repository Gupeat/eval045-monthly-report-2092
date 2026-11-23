from collections import Counter

from seed_month import build_dataset


def test_seed_run_counts():
    data = build_dataset()
    assert len(data["runs"]) == 210
    assert Counter(r["status"] for r in data["runs"]) == {"success": 207, "degraded": 2, "failed": 1}
    assert len(data["incidents"]) == 3
    assert Counter(i["type"] for i in data["incidents"]) == {"degraded": 2, "p0_failure": 1}


def test_seed_incident_links():
    data = build_dataset()
    by_id = {r["run_id"]: r for r in data["runs"]}
    assert by_id["run-20261108-tool-02"]["incident_id"] == "INC-DEG-01"
    assert by_id["run-20261111-tool-03"]["status"] == "failed"
    assert by_id["run-20261112-tool-03"]["recovery_of"] == "INC-P0-01"
    assert by_id["run-20261119-tool-05"]["incident_id"] == "INC-DEG-02"


def test_review_counts_and_reasons():
    data = build_dataset()
    events = data["review_events"]
    assert len(events) == 3000
    assert Counter(e["decision"] for e in events) == {"accepted": 2300, "rejected": 700}
    rejected = [e for e in events if e["decision"] == "rejected"]
    assert Counter(e["rejection_reason"] for e in rejected) == {
        "low_confidence": 100,
        "policy_violation": 100,
        "duplicate": 100,
        "missing_context": 100,
        "out_of_scope": 100,
        "format_error": 100,
        "manual_reject": 100,
    }
    assert Counter(e["sample_group"] for e in events) == {"standard": 2981, "low_sample": 19}


def test_redteam_covers_all_statuses():
    data = build_dataset()
    assert len(data["redteam_findings"]) == 12
    assert set(f["status"] for f in data["redteam_findings"]) == {
        "open",
        "triaged",
        "in_progress",
        "fixed",
        "verified",
    }
