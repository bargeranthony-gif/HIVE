"""Independent synthetic acceptance tests for additive HIVE candidate.

Not a substitute for the missing previously packaged standalone prototype source.
"""
import copy
import json
from pathlib import Path

import pytest

from hive.company_intel import (
    ReviewBoundaryError,
    aware_time,
    evaluate_fixture,
    load_fixture,
    main,
    render_markdown,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cedar_arc.json"


def setup_report():
    fixture, sha = load_fixture(FIXTURE)
    return fixture, evaluate_fixture(fixture, fixture_sha256=sha)


def by_type(report, name):
    return next(c for c in report["claims"] if c["type"] == name)


def test_c01_exact_identity_and_lookalike_rejected():
    _, report = setup_report()
    assert report["entity"]["registry_id"] == "FAKE-US-AR-2048-001"
    assert report["entity"]["match"] == "CONFIRMED_BY_EXACT_FIXTURE_ID"
    assert report["excluded_counts"]["other_identity"] == 1
    assert "S-LOOKALIKE" not in report["source_ids"]


def test_c02_shipments_remain_a_count_not_revenue():
    _, report = setup_report()
    observed = by_type(report, "shipment_activity")
    assert observed["count"] == 120 and observed["revenue_implied"] is False
    assert "revenue" not in observed


def test_c03_customs_value_has_units_and_is_not_margin():
    _, report = setup_report()
    shipment = by_type(report, "shipment_activity")
    assert shipment["customs_value_usd"] == 75_000
    assert "not sales or margin" in render_markdown(report)
    assert shipment["supplier_dependency_verified"] is False


def test_c04_filed_vs_vendor_estimated_are_distinct():
    _, report = setup_report()
    assert by_type(report, "filed_revenue")["amount_usd"] == 40_000_000
    assert by_type(report, "vendor_revenue_estimate")["amount_usd"] == 52_000_000
    assert report["discrepancies"][0]["code"] == "REPORTED_VS_ESTIMATED_DISCREPANCY"


def test_c05_republication_does_not_count_as_independent_source():
    _, report = setup_report()
    assert "S-02-REPEAT" in report["source_ids"]
    assert report["unique_original_roots"] == 6


def test_c06_proposed_legislation_not_effective():
    _, report = setup_report()
    law = by_type(report, "regulatory_proposal")
    assert law["status"] == "PROPOSED"
    assert law["effective"] is False


def test_c07_dismissed_allegation_not_adverse_judgment():
    _, report = setup_report()
    litigation = by_type(report, "litigation")
    assert litigation["allegation_filed"] is True
    assert litigation["dismissed"] is True
    assert litigation["adverse_judgment"] is False


def test_c08_missing_legal_coverage_is_unknown_not_no_litigation():
    _, report = setup_report()
    assert "Complete litigation coverage" in report["unknown"]
    assert "no litigation" not in render_markdown(report).lower()


def test_c09_unknown_rights_and_paid_requests_are_excluded():
    _, report = setup_report()
    assert report["excluded_counts"]["rights_or_cost"] == 1
    assert "S-BLOCKED-COST" not in report["source_ids"]
    assert report["receipt"]["api_credits_spent"] == 0


def test_c10_untrusted_instructions_do_not_become_execution():
    fixture, report = setup_report()
    assert any("IGNORE ALL RULES" in str(r.get("value")) for r in fixture["records"])
    assert "IGNORE ALL RULES" not in render_markdown(report)
    assert report["receipt"]["external_writes"] == 0


def test_c11_source_supplied_maturity_cannot_self_promote():
    _, report = setup_report()
    assert report["receipt"]["maturity"] == "ISOLATED_REVIEW_CANDIDATE_NOT_VERIFIED_IN_PRODUCTION"
    assert "test_verified" not in json.dumps(report)


def test_c12_private_and_cross_tenant_evidence_are_excluded():
    _, report = setup_report()
    assert report["excluded_counts"]["restricted"] == 1
    assert report["excluded_counts"]["other_tenant"] == 1
    assert "PRIVATE-NOT-IN-REPORT" not in json.dumps(report)
    assert "CROSS-TENANT-NOT-IN-REPORT" not in json.dumps(report)


def test_c13_auth_and_failure_cases_preserve_other_sources():
    fixture, original = setup_report()
    for err in ("HTTP_401", "HTTP_402", "HTTP_403", "HTTP_429", "TIMEOUT", "OUTAGE", "PARTIAL_FAILURE"):
        variant = copy.deepcopy(fixture)
        variant["provider_errors"] = {"ImportYeti": err}
        report = evaluate_fixture(variant)
        assert report["provider_states"]["ImportYeti"] == "MOCK_UNAVAILABLE"
        assert report["claims"] == original["claims"]


def test_c14_deterministic_evidence_locators_and_zero_calls():
    fixture, report = setup_report()
    again = evaluate_fixture(fixture, fixture_sha256=report["receipt"]["fixture_sha256"])
    assert again == report
    assert report["source_ids"][0] == "S-01"
    assert report["receipt"]["live_provider_calls"] == 0
    assert report["receipt"]["hive_registry_modified"] is False


def test_reject_nonfictional_and_unapproved_modes():
    fixture, _ = setup_report()
    for change in ({"synthetic": False}, {"mode": "ONLINE"}):
        variant = {**fixture, **change}
        with pytest.raises(ReviewBoundaryError):
            evaluate_fixture(variant)


def test_future_published_filing_does_not_leak():
    _, report = setup_report()
    assert report["excluded_counts"]["future"] == 1
    assert "9999999999" not in json.dumps(report)


def test_naive_and_invalid_timestamps_fail_closed():
    with pytest.raises(ReviewBoundaryError):
        aware_time("2026-11-01T00:00:00")
    with pytest.raises(ReviewBoundaryError):
        aware_time("not-a-date")
    fixture, _ = setup_report()
    fixture["as_of"] = "2026-11-01"
    with pytest.raises(ReviewBoundaryError):
        evaluate_fixture(fixture)


def test_cli_files_and_rejects_online_flag(tmp_path):
    assert main(["--fixture", str(FIXTURE), "--output", str(tmp_path)]) == 0
    assert (tmp_path / "company_brief.md").exists()
    data = json.loads((tmp_path / "company_brief.json").read_text())
    assert data["receipt"]["live_provider_calls"] == 0
    assert data["entity"]["name"] == "Cedar Arc Components LLC"
    with pytest.raises(SystemExit):
        main(["--fixture", str(FIXTURE), "--online"])
