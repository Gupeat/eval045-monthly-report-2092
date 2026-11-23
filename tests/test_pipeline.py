import hashlib

from seed_month import build_dataset, dumps_dataset
from stubs.eval041_aggregate import aggregate
from stubs.eval042_attribute import attribute
from stubs.eval043_render import draft_markdown
from stubs.eval044_review_publish import published_markdown, review_comments


def _pipeline():
    data = build_dataset()
    raw = dumps_dataset(data).encode("utf-8")
    agg = aggregate(data, hashlib.sha256(raw).hexdigest())
    att = attribute(data, agg)
    return data, agg, att


def test_aggregate_matches_dataset():
    _, agg, att = _pipeline()
    assert agg["runs"]["total"] == 210
    assert agg["runs"]["success"] == 207
    assert agg["runs"]["success_rate_pct"] == 98.5714
    assert agg["incidents"] == {"total": 3, "degraded": 2, "p0_failure": 1}
    assert agg["reviews"]["accepted"] == 2300
    assert agg["reviews"]["rejected"] == 700
    assert agg["reviews"]["reject_rate_pct"] == 23.3333
    assert agg["reviews"]["low_sample_groups"][0]["reviewed"] == 19
    assert att["incidents"][1]["incident_id"] == "INC-P0-01"


def test_review_changes_are_visible():
    data, agg, att = _pipeline()
    draft = draft_markdown(data, agg, att)
    comments = review_comments("draft-sha", agg, att)
    published = published_markdown(data, agg, att, comments)
    assert "- 本月复核事件约 3,000 条" in draft
    assert "- 本月复核事件约 3,000 条" not in published
    assert "- 本月复核事件 3,000 条：accepted 2,300 条，rejected 700 条，拒绝率 23.3333%。" in published
    assert "2,300 条" in published
    assert "700 条" in published
    assert "low_sample" in published
    assert "P0 失败（1 次）" in published
    assert "退化事件（2 次）" in published
    assert "默认排名覆盖其余 6 个工具" in published
    assert len(comments) == 3
    assert all(c["status"] == "resolved" for c in comments)
    assert "| R1 |" in published and "| R3 |" in published


def test_docx_renders(tmp_path):
    from stubs.md import markdown_to_docx

    data, agg, att = _pipeline()
    md = draft_markdown(data, agg, att)
    path = tmp_path / "draft.docx"
    markdown_to_docx(md, path)
    assert path.exists() and path.stat().st_size > 5000
