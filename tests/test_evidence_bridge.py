"""HIVE S3 proof-bridge boundary, temporal and documentary-fragility tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hive.company_intel import load_fixture
from hive.evidence_bridge import (
    BridgeBoundaryError, VERSION, _hash, align_reports,
    minimal_root_cuts, run_bridge,
)

GRAPH = Path(__file__).resolve().parents[1] / "fixtures" / "cedar_arc_temporal.json"
FINANCE = Path(__file__).resolve().parents[1] / "fixtures" / "economic_replay_synthetic.json"


def graph():
    return load_fixture(GRAPH)[0]


def base():
    g = graph()
    finance = {"schema": "hive.synthetic-financial-replay.v1",
               "mode": "OFFLINE_ONLY", "synthetic": True,
               "tenant_id": g["tenant_id"], "entity_id": g["entity"]["registry_id"],
               "evaluation_as_of": "2026-12-01T00:00:00Z",
               "cases": [{"case_id": "FAKE-C1", "cutoff": "2026-03-10T00:00:00Z"},
                         {"case_id": "FAKE-C2", "cutoff": "2026-11-01T00:00:00Z"}]}
    rows = [{"case_id": c["case_id"], "cutoff": c["cutoff"],
             "set": "TRAINING" if i == 0 else "HOLDOUT",
             "support": {"source_record_ids": ["FAKE-INV-01"]}}
            for i, c in enumerate(finance["cases"])]
    replay = {"schema": "hive.financial-replay-output.v1",
              "classification": "FICTIONAL_OFFLINE_RESEARCH",
              "entity_id": finance["entity_id"],
              "forecasts": rows,
              "holdout_metrics": {"falsification_diagnostic": "PLACEBO_COMPETITIVE",
                                  "comparison_gate": "FULL_SYNTHETIC_COVERAGE"},
              "receipt": {"provider_calls": 0, "external_writes": 0,
                          "registry_writes": 0, "trades": 0, "broker_connections": 0,
                          "operating_mode": "LOCAL_SYNTHETIC_ONLY"}}
    return g, finance, replay


def test_version_review_only():
    assert VERSION.startswith("0.3")


def test_cross_tenant_denial_before_any_source_inspection():
    g, f, r = base()
    f["tenant_id"] = "tenant-fixture-other"
    g["records"][0]["value"] = {"sensitive": "PRIVATE_MARKER_NEVER_PRINT"}
    output = align_reports(g, f, r)
    assert output["state"] == "BLOCKED"
    assert output["reason"] == "CROSS_TENANT_DENIED"
    assert "PRIVATE_MARKER" not in json.dumps(output)
    assert "source_id" not in json.dumps(output)
    assert "proof_fingerprint_sha256" not in output


def test_entity_mismatch_denied_without_fuzzy_name():
    g, f, r = base()
    f["entity_id"] = "FAKE-LOOKALIKE"
    output = align_reports(g, f, r)
    assert output["reason"] == "ENTITY_ID_MISMATCH_NO_AUTHORIZED_CROSSWALK"
    assert output["joined_claims"] == []


def test_malformed_fictional_or_offline_mode_rejected():
    for key, value in (("synthetic", False), ("mode", "ONLINE"),
                       ("schema", "hive.unknown.v1"), ("tenant_id", "live")):
        g, f, r = base()
        f[key] = value
        with pytest.raises(BridgeBoundaryError):
            align_reports(g, f, r)


def test_missing_graph_primary_identity_rejected():
    g, f, r = base()
    del g["entity"]
    with pytest.raises(BridgeBoundaryError):
        align_reports(g, f, r)


def test_replay_result_contract_required():
    for key, value in (("schema", "other"), ("classification", "REAL_MARKET_RESEARCH"),
                       ("entity_id", "FAKE-OTHER")):
        g, f, r = base()
        r[key] = value
        with pytest.raises(BridgeBoundaryError):
            align_reports(g, f, r)


def test_replay_receipt_must_be_read_only():
    for name in ("provider_calls", "external_writes", "registry_writes", "trades", "broker_connections"):
        g, f, r = base()
        r["receipt"][name] = 1
        with pytest.raises(BridgeBoundaryError):
            align_reports(g, f, r)


def test_dated_snapshots_are_recomputed_independently_not_backpropagated():
    g, f, r = base()
    output = align_reports(g, f, r)
    assert output["state"] == "ALIGNED_FIXTURE_IDS_ONLY_NOT_VERIFIED_IDENTITY"
    assert output["forecast_count"] == 2
    early, late = output["historical_snapshots"]
    assert "S-02" in early["graph_as_of_source_ids"]
    assert "S-REV-FY2025" not in early["graph_as_of_source_ids"]
    assert "S-REV-FY2025" in late["graph_as_of_source_ids"]
    assert early["graph_source_set_sha256"] != late["graph_source_set_sha256"]
    assert late["graph_unresolved_conflict_count"] > 0
    assert early["graph_path_count"] == 1
    assert late["graph_path_count"] == 3
    assert output["financial_predictive_value"] == "NOT_ESTABLISHED"
    assert output["economic_causality"] == "NOT_ESTABLISHED"
    assert output["replay_recomputed_from_packet"] is False


def test_late_published_source_does_not_retroactively_change_earlier_snapshot():
    g, f, r = base()
    before = align_reports(g, f, r)
    late = copy.deepcopy(g["records"][0])
    late.update(source_id="S-EXTRA-LATE", root_id="R-EXTRA-LATE",
                published_at="2026-11-25T00:00:00Z",
                first_available_at="2026-11-26T00:00:00Z")
    g["records"].append(late)
    after = align_reports(g, f, r)
    assert [x["graph_source_set_sha256"] for x in before["historical_snapshots"]] == [
        x["graph_source_set_sha256"] for x in after["historical_snapshots"]]


def test_hypothesis_status_cannot_promote_placebo_to_alpha():
    g, f, r = base()
    r["holdout_metrics"]["relative_mae_improvement"] = "0.999999"
    r["holdout_metrics"]["falsification_diagnostic"] = "PLACEBO_COMPETITIVE"
    x = align_reports(g, f, r)
    assert x["replay_falsification_diagnostic"] == "PLACEBO_COMPETITIVE"
    assert x["financial_predictive_value"] == "NOT_ESTABLISHED"
    assert not x["receipt"]["forecast_or_causal_claim_established"]
    assert x["source_to_model_feature_mapping"] == "NOT_IMPLEMENTED"


def test_replay_case_count_must_match():
    g, f, r = base()
    r["forecasts"].pop()
    with pytest.raises(BridgeBoundaryError):
        align_reports(g, f, r)


def test_duplicate_report_case_rejected():
    g, f, r = base()
    r["forecasts"][1]["case_id"] = r["forecasts"][0]["case_id"]
    with pytest.raises(BridgeBoundaryError):
        align_reports(g, f, r)


def test_case_timestamp_mismatch_rejected():
    g, f, r = base()
    r["forecasts"][0]["cutoff"] = "2026-03-11T00:00:00Z"
    with pytest.raises(BridgeBoundaryError):
        align_reports(g, f, r)


def test_case_out_of_order_rejected():
    g, f, r = base()
    r["forecasts"].reverse()
    with pytest.raises(BridgeBoundaryError):
        align_reports(g, f, r)


def test_cutoff_after_evaluation_is_rejected():
    g, f, r = base()
    f["evaluation_as_of"] = "2026-02-01T00:00:00Z"
    with pytest.raises(BridgeBoundaryError):
        align_reports(g, f, r)


def test_no_external_actions_and_fingerprint_stable():
    g, f, r = base()
    x = align_reports(g, f, r)
    y = align_reports(g, f, r)
    assert x == y
    assert x["proof_fingerprint_sha256"] == _hash({k: v for k, v in x.items()
                                                    if k != "proof_fingerprint_sha256"})
    assert x["receipt"]["external_writes"] == x["receipt"]["credits_spent"] == 0


def test_documentary_cuts_for_single_chain_not_economic_shocks():
    g, f, r = base()
    x = align_reports(g, f, r)
    cuts = x["historical_snapshots"][1]["graph_documentary_fragility"]
    assert cuts
    assert all(c["meaning"].endswith("NOT_ECONOMIC_CAUSALITY") for c in cuts)
    assert all(c["path_count"] >= 1 for c in cuts)


def test_two_independent_documentary_paths_need_two_cut_roots():
    paths = [
        {"entities": ["FAKE-ORIGIN", "FAKE-TARGET"], "original_roots": ["R-A", "R-B"]},
        {"entities": ["FAKE-ORIGIN", "FAKE-OTHER", "FAKE-TARGET"], "original_roots": ["R-C", "R-D"]},
    ]
    result = minimal_root_cuts(paths)
    assert result[0]["state"] == "BOUNDED_EXACT"
    assert result[0]["minimal_cut_sets"] == [
        ["R-A", "R-C"], ["R-A", "R-D"], ["R-B", "R-C"], ["R-B", "R-D"]]


def test_shared_root_is_single_point_of_documentary_failure():
    paths = [
        {"entities": ["FAKE-O", "FAKE-T"], "original_roots": ["R-SHARED", "R-A"]},
        {"entities": ["FAKE-O", "FAKE-X", "FAKE-T"], "original_roots": ["R-SHARED", "R-B"]},
    ]
    cuts = minimal_root_cuts(paths)[0]["minimal_cut_sets"]
    assert ["R-SHARED"] in cuts
    assert ["R-A", "R-B"] in cuts


def test_cut_source_count_budget_preserves_unknown():
    p = [{"entities": ["FAKE-A", "FAKE-T"],
          "original_roots": ["R-" + str(i) for i in range(13)]}]
    r = minimal_root_cuts(p)[0]
    assert r["state"] == "UNKNOWN_SOURCE_SPACE_TOO_LARGE"
    assert not r["minimal_cut_sets"]


def test_no_paths_is_not_proof_no_relationship_exists():
    assert minimal_root_cuts([]) == []


def test_invalid_path_lineage_or_cap_rejected():
    with pytest.raises(BridgeBoundaryError):
        minimal_root_cuts([{"entities": ["FAKE-X"], "original_roots": []}])
    with pytest.raises(BridgeBoundaryError):
        minimal_root_cuts([{"entities": ["FAKE-X", "FAKE-Y"],
                            "original_roots": ["R-A"]}] * 129)


def test_invalid_forecast_source_references_fail_closed():
    for broken in (None, "FAKE-INV-01", ["FAKE-INV-01", "INJECT!"], [123]):
        g, f, r = base()
        r["forecasts"][0]["support"]["source_record_ids"] = broken
        with pytest.raises(BridgeBoundaryError):
            align_reports(g, f, r)


def test_missing_support_or_partition_fails_closed():
    for key, value in (("support", None), ("set", "PROMOTED")):
        g, f, r = base()
        r["forecasts"][0][key] = value
        with pytest.raises(BridgeBoundaryError):
            align_reports(g, f, r)


def test_equivalent_timezone_cutoffs_produce_identical_snapshots():
    g, f, r = base()
    x = align_reports(g, f, r)
    f["cases"][0]["cutoff"] = "2026-03-09T19:00:00-05:00"
    r["forecasts"][0]["cutoff"] = "2026-03-09T19:00:00-05:00"
    y = align_reports(g, f, r)
    assert x == y


def test_cut_lineage_zero_length_root_refused():
    with pytest.raises(BridgeBoundaryError):
        minimal_root_cuts([{"entities": ["FAKE-A", "FAKE-B"],
                            "original_roots": [""]}])


def test_remote_actual_financial_replay_tenant_mismatch_is_a_no_join():
    pytest.importorskip("hive.financial_replay")
    from hive.financial_replay import load_packet
    finance = load_packet(FINANCE)[0]
    x = run_bridge(graph(), finance)
    assert x["reason"] == "CROSS_TENANT_DENIED"
    assert x["graph_or_replay_inspected"] is False
    assert "S-02" not in json.dumps(x)


def test_remote_full_replay_with_explicitly_aligned_fictional_identifiers():
    pytest.importorskip("hive.financial_replay")
    from hive.financial_replay import load_packet
    fin = load_packet(FINANCE)[0]
    g = graph()
    old_tenant, old_id = g["tenant_id"], g["entity"]["registry_id"]
    g["tenant_id"] = fin["tenant_id"]
    g["entity"]["registry_id"] = fin["entity_id"]
    for rec in g["records"]:
        if rec.get("tenant_id") == old_tenant:
            rec["tenant_id"] = fin["tenant_id"]
        if rec.get("registry_id") == old_id:
            rec["registry_id"] = fin["entity_id"]
    seed = copy.deepcopy(g["records"][0])
    seed.update(source_id="S-EARLY-REGISTRY", root_id="R-EARLY-REGISTRY",
                published_at="2019-01-01T00:00:00Z",
                first_available_at="2019-01-02T00:00:00Z")
    g["records"].append(seed)
    x = run_bridge(g, fin)
    assert x["state"] == "ALIGNED_FIXTURE_IDS_ONLY_NOT_VERIFIED_IDENTITY"
    assert x["replay_recomputed_from_packet"] is True
    assert x["forecast_count"] == len(fin["cases"]) == 23
    assert all("S-EARLY-REGISTRY" in z["graph_as_of_source_ids"]
               for z in x["historical_snapshots"])
    assert all("S-REV-FY2025" not in z["graph_as_of_source_ids"]
               for z in x["historical_snapshots"])
    assert x["replay_falsification_diagnostic"] == "PLACEBO_COMPETITIVE"
    assert x["financial_predictive_value"] == "NOT_ESTABLISHED"
