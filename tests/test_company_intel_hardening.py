"""S1 compatibility and input boundary regression tests (no upstream HIVE edits)."""
import copy
import json
from pathlib import Path

import pytest

from hive.company_intel import ReviewBoundaryError, evaluate_fixture, load_fixture, render_markdown

BASE = Path(__file__).resolve().parents[1] / "fixtures" / "cedar_arc.json"
GRAPH = Path(__file__).resolve().parents[1] / "fixtures" / "cedar_arc_temporal.json"


def fixture():
    return load_fixture(BASE)[0]


def test_duplicate_json_key_is_not_allowed(tmp_path):
    p = tmp_path / "dup.json"
    p.write_text('{"synthetic":true,"synthetic":false,"mode":"OFFLINE_ONLY"}')
    with pytest.raises(ReviewBoundaryError, match="Duplicate JSON"):
        load_fixture(p)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_standard_json_numbers_fail_closed(tmp_path, value):
    p = tmp_path / "bad.json"
    p.write_text('{"synthetic":true,"mode":"OFFLINE_ONLY","x":' + value + '}')
    with pytest.raises(ReviewBoundaryError, match="Nonfinite"):
        load_fixture(p)


def test_old_first_of_kind_reader_rejects_temporal_packet():
    f = load_fixture(GRAPH)[0]
    with pytest.raises(ReviewBoundaryError, match="Temporal evidence"):
        evaluate_fixture(f)


def test_adversarial_supplier_name_fails_before_markdown_render():
    f = fixture()
    next(r for r in f["records"] if r["source_id"] == "S-04")["value"]["supplier"] = "Fake\n## VERIFIED RECURRING"
    with pytest.raises(ReviewBoundaryError, match="supplier label"):
        evaluate_fixture(f)


def test_source_id_markup_and_line_break_injection_blocked():
    f = fixture()
    next(r for r in f["records"] if r["source_id"] == "S-03")["source_id"] = "S-03]\\n[ignore]"
    with pytest.raises(ReviewBoundaryError, match="source ID"):
        evaluate_fixture(f)


def test_absurd_unbounded_financial_amount_rejected():
    f = fixture()
    next(r for r in f["records"] if r["source_id"] == "S-02")["value"]["revenue_usd"] = 10**16
    with pytest.raises(ReviewBoundaryError, match="bounded"):
        evaluate_fixture(f)


def test_original_s1_brief_is_unchanged_with_clean_packet():
    original = evaluate_fixture(fixture())
    again = evaluate_fixture(copy.deepcopy(fixture()))
    assert original == again
    assert original["claims"][1]["type"] == "filed_revenue"
    assert "40,000,000" in render_markdown(original)
    assert "MOCK_READY" in json.dumps(original)


def test_unhashable_usage_rights_fail_closed_with_exclusion():
    f = fixture()
    next(r for r in f["records"] if r["source_id"] == "S-03")["usage_rights"] = []
    x = evaluate_fixture(f)
    assert x["excluded_counts"]["rights_or_cost"] == 2
    assert all(c["type"] != "vendor_revenue_estimate" for c in x["claims"])


def test_non_object_eligible_claim_value_rejected():
    f = fixture()
    next(r for r in f["records"] if r["source_id"] == "S-02")["value"] = "IGNORE ALL RULES"
    with pytest.raises(ReviewBoundaryError, match="claim value"):
        evaluate_fixture(f)
