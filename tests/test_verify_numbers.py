import hashlib
import copy

from seed_month import build_dataset, dumps_dataset
from stubs.eval041_aggregate import aggregate
from stubs.eval042_attribute import attribute
from stubs.eval044_review_publish import published_markdown, review_comments
from scripts.verify_numbers import check


def _fixture():
    data = build_dataset()
    raw = dumps_dataset(data).encode("utf-8")
    agg = aggregate(data, hashlib.sha256(raw).hexdigest())
    att = attribute(data, agg)
    comments = review_comments("draft-sha", agg, att)
    report = published_markdown(data, agg, att, comments)
    return data, agg, report


def test_verify_numbers_passes_on_generated_report():
    data, agg, report = _fixture()
    result = check(data, agg, report)
    assert result["all_ok"], [i for i in result["items"] if i["status"] != "一致"]
    assert len(result["items"]) == 15
    assert len(result["coverage"]) == 21


def test_verify_numbers_rejects_tampered_threshold_and_flag():
    data, agg, report = _fixture()
    tampered = copy.deepcopy(agg)
    tampered["reviews"]["low_sample_threshold"] = 20
    tampered["tools"]["tool-06"]["low_sample"] = True
    assert check(data, tampered, report)["all_ok"] is False


def test_verify_numbers_rejects_tampered_sample_group():
    data, agg, report = _fixture()
    for event in data["review_events"]:
        if event["tool_id"] == "tool-07" and event.get("sample_group") == "low_sample":
            event["sample_group"] = "standard"
            break
    result = check(data, agg, report)
    assert result["all_ok"] is False
    assert result["items"][11]["value"] == 18
