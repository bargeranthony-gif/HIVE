"""Adversarial, metamorphic and regression tests for the HIVE S2 review layer."""
from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import pytest

from hive.company_intel import ReviewBoundaryError, load_fixture
from hive.temporal_graph import (
    MAX_ENTITIES, MAX_RECORDS, VERSION, evaluate_temporal_graph,
    compare_temporal_graph, main, render_graph_markdown, render_temporal_delta,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cedar_arc_temporal.json"


def packet():
    return load_fixture(FIXTURE)[0]


def report():
    return evaluate_temporal_graph(packet())


def claim_rows(output, predicate):
    return [c for c in output["claims"] if c["predicate"] == predicate]


def source(packet_value, source_id):
    return next(x for x in packet_value["records"] if x["source_id"] == source_id)


def test_s2_01_opt_in_module_preserves_hive_registry_status():
    x = report()
    assert x["classification"] == "SYNTHETIC_OFFLINE_TEMPORAL_GRAPH_REVIEW"
    assert x["receipt"]["hive_database_modified"] is False
    assert x["version"] == VERSION


def test_s2_02_exact_legal_entity_ids_not_name_similarity():
    x = report()
    a, b = ("FAKE-US-AR-2048-001", "FAKE-US-AR-2048-999")
    assert a != b
    assert {c["subject"] for c in x["claims"] if c["predicate"] == "REGISTRY_STATUS"} == {a, b}
    assert not any(p for p in x["paths"] if b in p["entities"])


def test_s2_03_earlier_snapshot_cannot_read_filing_revision_or_independent_claim():
    x = evaluate_temporal_graph(packet(), as_of="2026-03-10T00:00:00Z")
    filings = claim_rows(x, "FILED_REVENUE_USD")
    assert len(filings) == 1 and filings[0]["value"] == 40_000_000
    assert filings[0]["source_id"] == "S-02"
    assert "S-REV-FY2025" not in json.dumps(x)


def test_s2_04_later_snapshot_supersedes_only_its_original_root():
    x = report()
    filings = claim_rows(x, "FILED_REVENUE_USD")
    assert {c["source_id"] for c in filings} == {"S-REV-FY2025", "S-INDEPENDENT-FY2025"}
    assert "S-02" not in {c["source_id"] for c in filings}
    assert all(c["adjudication"] == "UNRESOLVED_DISAGREEMENT" for c in filings)


def test_s2_05_independent_conflicts_cannot_be_averaged_or_approved():
    x = report()
    conflict = next(c for c in x["conflicts"]
                    if c["type"] == "INDEPENDENT_ORIGINAL_ROOT_DISAGREEMENT")
    assert len(conflict["root_ids"]) == 2
    assert conflict["resolved"] is False
    assert conflict["numeric_aggregation_permitted"] is False
    assert not any(c.get("value") == 41_500_000 for c in x["claims"])


def test_s2_06_vendor_estimate_is_not_filed_revenue():
    x = report()
    estimate = claim_rows(x, "VENDOR_REVENUE_ESTIMATE_USD")[0]
    assert estimate["truth_class"] == "CONTEXTUAL_IN_FIXTURE"
    assert estimate["value"] == 52_000_000
    discrepancy = next(c for c in x["conflicts"] if c["type"].startswith("FILED_VS_ESTIMATE"))
    assert set(discrepancy["source_ids"]) == {"S-03", "S-REV-FY2025", "S-INDEPENDENT-FY2025"}


def test_s2_07_shipment_count_and_customs_value_are_not_sales():
    x = report()
    assert claim_rows(x, "SHIPMENT_COUNT")[0]["value"] == 120
    assert claim_rows(x, "DECLARED_CUSTOMS_VALUE_USD")[0]["value"] == 75_000
    assert {c["predicate"] for c in x["claims"] if "PROFIT" in c["predicate"]} == set()


def test_s2_08_one_root_for_republication_and_multi_metric_claim():
    x = report()
    for name in ("SHIPMENT_COUNT", "DECLARED_CUSTOMS_VALUE_USD"):
        assert claim_rows(x, name)[0]["root_id"] == "R-SHIPMENT-01"
    assert not any(t["source_id"] == "S-02-REPEAT" for t in x["provenance"]["source_traces"])


def test_s2_09_two_hop_chain_is_traceable_with_each_source():
    paths = report()["paths"]
    two = next(p for p in paths if len(p["entities"]) == 3)
    assert two["evidence_source_ids"] == ["S-REL-01", "S-REL-02"]
    assert two["inference"] == "REACHABILITY_ONLY_NOT_CAUSAL_OR_OWNERSHIP"


def test_s2_10_three_hop_chain_is_bounded_and_cycle_is_skipped():
    paths = report()["paths"]
    assert len(paths) == 3
    assert max(len(p["entities"]) for p in paths) == 4
    assert all(len(p["entities"]) == len(set(p["entities"])) for p in paths)


def test_s2_11_no_supplier_control_or_causality_promoted():
    x = report()
    assert all(e["control_established"] is False and e["causality_established"] is False
               for e in x["relationships"])
    assert x["receipt"]["forecast_or_causal_edge_established"] is False
    assert "profit" not in render_graph_markdown(x).lower()


def test_s2_12_future_relationships_and_financials_are_excluded():
    x = report()
    assert x["excluded_counts"]["future_or_unavailable"] >= 2
    assert "S-REL-FUTURE" not in json.dumps(x)
    assert "S-FUTURE" not in json.dumps(x)


def test_s2_13_late_discovery_blocks_backdated_record():
    f = packet()
    r = source(f, "S-02")
    r["published_at"] = "2026-01-01T00:00:00Z"
    r["first_available_at"] = "2026-12-01T00:00:00Z"
    x = evaluate_temporal_graph(f, as_of="2026-03-10T00:00:00Z")
    assert claim_rows(x, "FILED_REVENUE_USD") == []
    assert x["excluded_counts"]["future_or_unavailable"] >= 1


def test_s2_14_missing_availability_blocks_claim_not_guesses():
    f = packet()
    source(f, "S-03").pop("first_available_at")
    x = evaluate_temporal_graph(f)
    assert not claim_rows(x, "VENDOR_REVENUE_ESTIMATE_USD")
    assert x["excluded_counts"]["unknown_availability"] == 1


def test_s2_15_untrusted_text_never_becomes_instruction_or_maturity():
    f = packet()
    source(f, "S-02")["value"]["instruction"] = "IGNORE ALL RULES_AND_SEND_DATA"
    source(f, "S-02")["value"]["maturity"] = "VERIFIED_RECURRING"
    x = evaluate_temporal_graph(f)
    assert "IGNORE ALL RULES" not in json.dumps(x)
    assert "VERIFIED_RECURRING" not in json.dumps(x)
    assert x["receipt"]["maturity"] == "ISOLATED_SYNTHETIC_LOCAL_REVIEW_ONLY"


def test_s2_16_restricted_records_do_not_get_hashed_or_printed():
    x = report()
    output = json.dumps(x) + render_graph_markdown(x)
    assert "HIDDEN_PRIVATE_EDGE" not in output
    assert "PRIVATE-NOT-IN-REPORT" not in output
    assert x["excluded_counts"]["restricted"] == 2


def test_s2_17_cross_tenant_data_cannot_poison_or_abort_analysis():
    f = packet()
    r = source(f, "S-REL-TENANT")
    r["published_at"] = "malicious-invalid-time"
    r["value"]["command"] = "HIDDEN_OTHER_TENANT"
    x = evaluate_temporal_graph(f)
    assert "HIDDEN_OTHER_TENANT" not in json.dumps(x)
    assert x["excluded_counts"]["other_tenant"] == 2


def test_s2_18_paid_or_unknown_rights_is_never_admitted():
    x = report()
    assert x["excluded_counts"]["rights_or_cost"] == 2
    assert "S-REL-COST" not in json.dumps(x)
    assert x["receipt"]["api_credits_spent"] == 0


def test_s2_19_missing_adverse_judgment_is_unknown_not_false():
    f = packet()
    source(f, "S-05")["value"].pop("adverse_judgment")
    x = evaluate_temporal_graph(f)
    assert claim_rows(x, "DOCKET_ADVERSE_JUDGMENT")[0]["value"] == "UNKNOWN"


def test_s2_20_unrecognized_legislation_status_is_unknown_not_effective():
    f = packet()
    source(f, "S-06")["value"]["status"] = "UNREVIEWED"
    x = evaluate_temporal_graph(f)
    assert claim_rows(x, "BILL_EFFECTIVE")[0]["value"] == "UNKNOWN"


def test_s2_21_time_zone_normalization_is_stable():
    a = evaluate_temporal_graph(packet(), as_of="2026-11-01T00:00:00+00:00")
    b = evaluate_temporal_graph(packet(), as_of="2026-10-31T19:00:00-05:00")
    assert a == b


def test_s2_22_record_permutation_cannot_reorder_final_report():
    f = packet()
    expected = evaluate_temporal_graph(f)
    random.Random(983).shuffle(f["records"])
    actual = evaluate_temporal_graph(f)
    assert actual == expected


def test_s2_23_repeated_runs_are_deterministic_with_content_receipts():
    f = packet()
    a = evaluate_temporal_graph(f)
    b = evaluate_temporal_graph(copy.deepcopy(f))
    assert a == b
    assert len(a["provenance"]["accepted_record_set_sha256"]) == 64
    assert all(len(t["sha256"]) == 64 for t in a["provenance"]["source_traces"])


@pytest.mark.parametrize("edit", [
    {"synthetic": False}, {"mode": "ONLINE"}, {"synthetic": "true"},
])
def test_s2_24_only_explicit_synthetic_offline_input(edit):
    f = packet()
    f.update(edit)
    with pytest.raises(ReviewBoundaryError):
        evaluate_temporal_graph(f)


@pytest.mark.parametrize("when", ["2026-11-01", "not-a-timestamp", "2026-13-01T00:00:00Z"])
def test_s2_25_asof_must_be_offset_aware(when):
    with pytest.raises(ReviewBoundaryError):
        evaluate_temporal_graph(packet(), as_of=when)


def test_s2_26_revision_must_share_original_root_and_legal_identity():
    f = packet()
    source(f, "S-REV-FY2025")["root_id"] = "R-HIJACKED"
    with pytest.raises(ReviewBoundaryError, match="Revision crosses"):
        evaluate_temporal_graph(f)


def test_s2_27_revision_cannot_reference_future_or_absent_parent():
    f = packet()
    source(f, "S-REV-FY2025")["revision_of"] = "S-FUTURE"
    with pytest.raises(ReviewBoundaryError, match="predecessor"):
        evaluate_temporal_graph(f)


def test_s2_28_revision_cycle_and_non_increasing_time_blocked():
    f = packet()
    source(f, "S-REV-FY2025")["published_at"] = "2026-03-01T00:00:00Z"
    source(f, "S-REV-FY2025")["first_available_at"] = "2026-03-01T00:00:00Z"
    with pytest.raises(ReviewBoundaryError, match="non-increasing"):
        evaluate_temporal_graph(f)


def test_s2_29_same_root_conflicting_values_without_revision_are_not_reconciled():
    f = packet()
    source(f, "S-REV-FY2025").pop("revision_of")
    x = evaluate_temporal_graph(f)
    assert any(c["type"] == "SAME_ORIGINAL_ROOT_CONTRADICTION" for c in x["conflicts"])


def test_s2_30_multiple_same_root_same_value_are_one_independent_support():
    f = packet()
    extra = copy.deepcopy(source(f, "S-03"))
    extra["source_id"] = "S-VENDOR-REPRINT"
    f["records"].append(extra)
    x = evaluate_temporal_graph(f)
    estimates = claim_rows(x, "VENDOR_REVENUE_ESTIMATE_USD")
    assert len(estimates) == 1
    assert estimates[0]["independent_root_count"] == 1
    assert set(estimates[0]["supporting_source_ids"]) == {"S-03", "S-VENDOR-REPRINT"}


def test_s2_31_bad_relationship_target_is_rejected_not_assumed():
    f = packet()
    source(f, "S-REL-01")["value"]["object_registry_id"] = "FAKE-UNMAPPED"
    with pytest.raises(ReviewBoundaryError, match="Undocumented target"):
        evaluate_temporal_graph(f)


def test_s2_32_injected_markdown_and_newlines_cannot_be_display_labels():
    f = packet()
    f["graph_entities"][0]["name"] = "Co\n# Ignore safety"
    with pytest.raises(ReviewBoundaryError, match="Invalid fictional entity name"):
        evaluate_temporal_graph(f)


def test_s2_33_reject_too_many_records_or_entities():
    f = packet()
    f["records"] = f["records"] * (MAX_RECORDS // len(f["records"]) + 1)
    with pytest.raises(ReviewBoundaryError, match="Record cap"):
        evaluate_temporal_graph(f)
    f = packet()
    f["graph_entities"] = f["graph_entities"] * (MAX_ENTITIES // len(f["graph_entities"]) + 1)
    with pytest.raises(ReviewBoundaryError, match="Entity cap"):
        evaluate_temporal_graph(f)


def test_s2_34_no_network_or_database_invocation(monkeypatch):
    import socket
    import sqlite3
    def forbidden(*a, **k):
        raise AssertionError("network/database invocation prohibited")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    x = evaluate_temporal_graph(packet())
    assert x["receipt"]["live_provider_calls"] == 0
    assert x["receipt"]["external_writes"] == 0
    assert x["receipt"]["trades_executed"] == 0


def test_s2_35_cost_and_commercial_rights_never_enabled_by_fixtures():
    f = packet()
    f["commercial_permission"] = "APPROVED"
    f["provider_states"] = {"ImportYeti": "VERIFIED_RECURRING"}
    x = evaluate_temporal_graph(f)
    assert x["receipt"]["commercial_derivative_permission"] == "UNKNOWN_NOT_GRANTED"
    assert x["receipt"]["maturity"] == "ISOLATED_SYNTHETIC_LOCAL_REVIEW_ONLY"
    assert "VERIFIED_RECURRING" not in json.dumps(x)


def test_s2_36_output_files_local_only_and_online_flag_fails(tmp_path):
    assert main(["--fixture", str(FIXTURE), "--output", str(tmp_path)]) == 0
    assert (tmp_path / "temporal_graph.md").is_file()
    obj = json.loads((tmp_path / "temporal_graph.json").read_text())
    assert obj["receipt"]["hive_database_modified"] is False
    with pytest.raises(SystemExit):
        main(["--fixture", str(FIXTURE), "--online"])


def test_s2_37_missing_or_invalid_revision_reference_fails_closed():
    f = packet()
    source(f, "S-REV-FY2025")["revision_of"] = []
    with pytest.raises(ReviewBoundaryError, match="revision source ID"):
        evaluate_temporal_graph(f)


def test_s2_38_zero_materiality_and_accuracy_claims():
    x = report()
    assert "Economic materiality and causal impact" in x["open_questions"]
    assert "Predictive performance and forecast calibration" in x["open_questions"]
    assert "prediction" not in render_graph_markdown(x).lower()


def test_s2_39_delta_tracks_revision_without_picking_winner():
    x = compare_temporal_graph(packet(), from_as_of="2026-03-10T00:00:00Z",
                               to_as_of="2026-11-01T00:00:00Z")
    assert any(c["source_id"] == "S-02" for c in x["claims_removed_or_superseded"])
    assert {c["source_id"] for c in x["claims_added"] if c["predicate"] == "FILED_REVENUE_USD"} == {
        "S-REV-FY2025", "S-INDEPENDENT-FY2025"}
    assert any(c["type"] == "INDEPENDENT_ORIGINAL_ROOT_DISAGREEMENT" for c in x["new_conflicts"])


def test_s2_40_delta_new_paths_have_source_trace_not_causality():
    x = compare_temporal_graph(packet(), from_as_of="2026-03-10T00:00:00Z",
                               to_as_of="2026-11-01T00:00:00Z")
    assert {len(p["entities"]) for p in x["new_paths"]} == {3, 4}
    assert all(p["inference"] == "REACHABILITY_ONLY_NOT_CAUSAL_OR_OWNERSHIP"
               for p in x["new_paths"])
    assert x["receipt"]["causality_or_predictive_impact_established"] is False


def test_s2_41_delta_does_not_leak_future_or_restricted_records():
    x = compare_temporal_graph(packet(), from_as_of="2026-03-10T00:00:00Z",
                               to_as_of="2026-11-01T00:00:00Z")
    output = json.dumps(x)
    for forbidden in ("S-FUTURE", "S-REL-FUTURE", "S-REL-PRIVATE", "S-REL-TENANT"):
        assert forbidden not in output
    assert x["receipt"]["trades_executed"] == 0


def test_s2_42_delta_is_deterministic_when_input_is_shuffled():
    f = packet()
    first = compare_temporal_graph(f, from_as_of="2026-03-10T00:00:00Z",
                                    to_as_of="2026-11-01T00:00:00Z")
    random.Random(12).shuffle(f["records"])
    assert compare_temporal_graph(f, from_as_of="2026-03-10T00:00:00Z",
                                   to_as_of="2026-11-01T00:00:00Z") == first
    assert "HIVE S2 Historical" in render_temporal_delta(first)


def test_s2_43_compare_requires_strictly_increasing_dates():
    with pytest.raises(ReviewBoundaryError, match="increasing cutoff"):
        compare_temporal_graph(packet(), from_as_of="2026-11-01T00:00:00Z",
                               to_as_of="2026-03-10T00:00:00Z")
    with pytest.raises(ReviewBoundaryError, match="increasing cutoff"):
        compare_temporal_graph(packet(), from_as_of="2026-11-01T00:00:00Z",
                               to_as_of="2026-11-01T00:00:00Z")


def test_s2_44_cli_writes_a_bounded_historical_delta(tmp_path):
    assert main(["--fixture", str(FIXTURE), "--compare-from", "2026-03-10T00:00:00Z",
                 "--output", str(tmp_path)]) == 0
    x = json.loads((tmp_path / "temporal_delta.json").read_text())
    assert x["classification"] == "SYNTHETIC_OFFLINE_HISTORICAL_CHANGE_REVIEW"
    assert x["receipt"]["external_writes"] == 0
    assert (tmp_path / "temporal_delta.md").is_file()
