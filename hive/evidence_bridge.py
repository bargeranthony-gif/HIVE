"""HIVE S3 synthetic-only proof bridge across temporal graph and replay.

This read-only adapter refuses cross-tenant, fuzzy-entity or retroactive joins.
Even an admitted synthetic alignment NEVER proves causality or forecasting skill.
Neither a fixture hash nor a claim of rights authenticates external evidence.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from .company_intel import ReviewBoundaryError, aware_time, load_fixture
from .temporal_graph import evaluate_temporal_graph

VERSION = "0.3.0-synthetic-review"
FINANCE_SCHEMA = "hive.synthetic-financial-replay.v1"
REPORT_SCHEMA = "hive.financial-replay-output.v1"
MAX_CASES = 120
MAX_ROOTS_PER_TARGET = 12
MAX_CUT_ORDER = 2


class BridgeBoundaryError(ValueError):
    """Unsafe, unsupported, malformed or inconsistent bridge input."""


def _utc(value: object) -> datetime:
    try:
        return aware_time(value).astimezone(timezone.utc)
    except ReviewBoundaryError as exc:
        raise BridgeBoundaryError("Offset-aware, valid cutoff is required") from exc


def _canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True)


def _hash(obj: object) -> str:
    return hashlib.sha256(_canonical(obj).encode("ascii")).hexdigest()


def _id(value: object, prefix: str, field: str) -> str:
    if (not isinstance(value, str) or not value.startswith(prefix) or len(value) <= len(prefix)
            or len(value) > 100 or not all(c.isalnum() or c in "-_" for c in value)):
        raise BridgeBoundaryError("Invalid synthetic " + field)
    return value


def _preflight(graph: object, finance: object) -> dict | None:
    """Reject before inspecting records, hashing, or constructing any graph output."""
    if not isinstance(graph, dict) or not isinstance(finance, dict):
        raise BridgeBoundaryError("Input packets must be JSON objects")
    if (graph.get("synthetic") is not True or finance.get("synthetic") is not True
            or graph.get("mode") != "OFFLINE_ONLY" or finance.get("mode") != "OFFLINE_ONLY"
            or finance.get("schema") != FINANCE_SCHEMA):
        raise BridgeBoundaryError("Only exact synthetic offline schemas are admissible")
    g_tenant = _id(graph.get("tenant_id"), "tenant-fixture-", "graph tenant")
    f_tenant = _id(finance.get("tenant_id"), "tenant-fixture-", "replay tenant")
    primary = graph.get("entity")
    if not isinstance(primary, dict):
        raise BridgeBoundaryError("Graph primary identity missing")
    g_id = _id(primary.get("registry_id"), "FAKE-", "graph entity")
    f_id = _id(finance.get("entity_id"), "FAKE-", "replay entity")
    if g_tenant != f_tenant:
        reason = "CROSS_TENANT_DENIED"
    elif g_id != f_id:
        reason = "ENTITY_ID_MISMATCH_NO_AUTHORIZED_CROSSWALK"
    else:
        return None
    # No source IDs, names, data, hashes or packet-derived payloads leak on denial.
    return {
        "classification": "SYNTHETIC_EVIDENCE_ALIGNMENT_BLOCKED",
        "version": VERSION, "state": "BLOCKED", "reason": reason,
        "graph_or_replay_inspected": False, "joined_claims": [],
        "receipt": {"external_calls": 0, "external_writes": 0, "credits_spent": 0,
                    "trades": 0, "commercial_authority": "NOT_GRANTED",
                    "forecast_or_causal_claim_established": False},
    }


def minimal_root_cuts(paths: list[dict]) -> list[dict]:
    """Bounded smallest hitting sets of fixture-claimed roots for each endpoint.

    A cut describes loss of documentary reachability, NOT a supply shock.
    When combinatorics exceed bounds, report UNKNOWN instead of approximating.
    """
    if not isinstance(paths, list) or len(paths) > 128:
        raise BridgeBoundaryError("Graph path cap exceeded")
    grouped: dict[str, list[frozenset[str]]] = defaultdict(list)
    for path in paths:
        if not isinstance(path, dict):
            raise BridgeBoundaryError("Invalid graph path")
        entities, roots = path.get("entities"), path.get("original_roots")
        if (not isinstance(entities, list) or len(entities) < 2
                or not isinstance(roots, list) or not roots):
            raise BridgeBoundaryError("Invalid graph path lineage")
        target = _id(entities[-1], "FAKE-", "target")
        lineage = frozenset(_id(r, "", "original root") for r in roots)
        grouped[target].append(lineage)
    results = []
    for target in sorted(grouped):
        families = grouped[target]
        pool = sorted(set().union(*families))
        if len(pool) > MAX_ROOTS_PER_TARGET:
            results.append({"target": target, "state": "UNKNOWN_SOURCE_SPACE_TOO_LARGE",
                            "minimal_cut_sets": [], "path_count": len(families)})
            continue
        minimal = []
        for order in range(1, min(len(pool), MAX_CUT_ORDER) + 1):
            for comb in itertools.combinations(pool, order):
                c = frozenset(comb)
                if any(prior.issubset(c) for prior in minimal):
                    continue
                if all(c.intersection(fam) for fam in families):
                    minimal.append(c)
        results.append({"target": target,
                        "state": "BOUNDED_EXACT" if minimal else "UNKNOWN_NO_CUT_WITHIN_BOUND",
                        "minimal_cut_sets": [sorted(s) for s in minimal],
                        "path_count": len(families),
                        "meaning": "FIXTURE_SOURCE_ROOT_REMOVAL_ONLY_NOT_ECONOMIC_CAUSALITY"})
    return results


def align_reports(graph_fixture: dict, finance_packet: dict,
                  replay_report: dict, *, replay_recomputed: bool = False) -> dict:
    """Construct a point-in-time proof summary; caller-supplied reports are unverified."""
    denial = _preflight(graph_fixture, finance_packet)
    if denial is not None:
        return denial
    if (not isinstance(replay_report, dict) or replay_report.get("schema") != REPORT_SCHEMA
            or replay_report.get("classification") != "FICTIONAL_OFFLINE_RESEARCH"
            or replay_report.get("entity_id") != finance_packet.get("entity_id")):
        raise BridgeBoundaryError("Replay result schema, class or entity mismatch")
    receipt = replay_report.get("receipt")
    if (not isinstance(receipt, dict) or any(receipt.get(k) != 0 for k in
                                           ("provider_calls", "external_writes", "registry_writes", "trades", "broker_connections"))
            or receipt.get("operating_mode") != "LOCAL_SYNTHETIC_ONLY"):
        raise BridgeBoundaryError("Replay evidence is not read-only synthetic output")
    horizon = _utc(finance_packet.get("evaluation_as_of"))
    rows = replay_report.get("forecasts")
    cases = finance_packet.get("cases")
    if (not isinstance(rows, list) or not isinstance(cases, list)
            or len(rows) != len(cases) or not 1 <= len(rows) <= MAX_CASES):
        raise BridgeBoundaryError("Replay/case count or bound mismatch")
    indexed = {}
    for c in cases:
        if not isinstance(c, dict):
            raise BridgeBoundaryError("Case must be an object")
        cid = _id(c.get("case_id"), "FAKE-", "case")
        if cid in indexed:
            raise BridgeBoundaryError("Duplicate case identifier")
        indexed[cid] = c
    seen = set()
    snapshots = []
    last_cutoff = datetime.min.replace(tzinfo=timezone.utc)
    for row in rows:
        if not isinstance(row, dict):
            raise BridgeBoundaryError("Forecast must be an object")
        cid = _id(row.get("case_id"), "FAKE-", "reported case")
        if cid in seen or cid not in indexed:
            raise BridgeBoundaryError("Unmatched, repeated or extra forecast")
        seen.add(cid)
        cutoff = _utc(row.get("cutoff"))
        if (cutoff != _utc(indexed[cid].get("cutoff")) or cutoff <= last_cutoff
                or cutoff >= horizon):
            raise BridgeBoundaryError("Case cutoff mismatch or temporal order violation")
        last_cutoff = cutoff
        try:
            # This is the crucial anti-leakage operation: never reuse a late snapshot.
            graph = evaluate_temporal_graph(graph_fixture, as_of=cutoff.isoformat())
        except ReviewBoundaryError as exc:
            raise BridgeBoundaryError("Temporal graph rejected forecast cutoff") from exc
        traces = graph["provenance"]["source_traces"]
        if any(_utc(t["usable_at"]) > cutoff for t in traces):
            raise BridgeBoundaryError("Graph source available after forecast cutoff")
        cuts = minimal_root_cuts(graph["paths"])
        support = row.get("support")
        if not isinstance(support, dict) or row.get("set") not in ("TRAINING", "HOLDOUT"):
            raise BridgeBoundaryError("Invalid forecast evidence or partition")
        support_ids = support.get("source_record_ids")
        if not isinstance(support_ids, list) or len(support_ids) > 1000:
            raise BridgeBoundaryError("Invalid forecast evidence references")
        for sid in support_ids:
            _id(sid, "FAKE-", "forecast source")
        snapshots.append({
            "case_id": cid, "forecast_cutoff": cutoff.isoformat(),
            "forecast_partition": row.get("set"),
            "forecast_source_record_ids": sorted(set(support_ids)),
            "graph_as_of_source_ids": [t["source_id"] for t in traces],
            "graph_source_set_sha256": graph["provenance"]["accepted_record_set_sha256"],
            "graph_path_count": len(graph["paths"]),
            "graph_unresolved_conflict_count": sum(not c.get("resolved") for c in graph["conflicts"]),
            "graph_documentary_fragility": cuts,
            "state": "AS_OF_ASSOCIATION_ONLY" if traces else "UNKNOWN_NO_ADMISSIBLE_GRAPH_SOURCES",
            "cross_module_model_feature_created": False,
        })
    if len(seen) != len(indexed):
        raise BridgeBoundaryError("Forecast coverage missing")
    metrics = replay_report.get("holdout_metrics")
    if not isinstance(metrics, dict):
        raise BridgeBoundaryError("Missing holdout metrics")
    result = {
        "schema": "hive.synthetic-evidence-bridge-output.v1",
        "classification": "SYNTHETIC_OFFLINE_EVIDENCE_ALIGNMENT",
        "state": "ALIGNED_FIXTURE_IDS_ONLY_NOT_VERIFIED_IDENTITY",
        "version": VERSION,
        "entity_id": finance_packet["entity_id"],
        "as_of_evaluation": horizon.isoformat(),
        "forecast_count": len(snapshots),
        "historical_snapshots": snapshots,
        "replay_falsification_diagnostic": metrics.get("falsification_diagnostic", "UNKNOWN"),
        "replay_comparison_gate": metrics.get("comparison_gate", "UNKNOWN"),
        "source_authentication": "UNKNOWN_NOT_INDEPENDENTLY_VERIFIED",
        "rights_authentication": "UNKNOWN_NOT_INDEPENDENTLY_VERIFIED",
        "economic_causality": "NOT_ESTABLISHED",
        "financial_predictive_value": "NOT_ESTABLISHED",
        "source_to_model_feature_mapping": "NOT_IMPLEMENTED",
        "replay_recomputed_from_packet": replay_recomputed,
        "receipt": {"external_calls": 0, "external_writes": 0, "credits_spent": 0,
                    "trades": 0, "commercial_authority": "NOT_GRANTED",
                    "forecast_or_causal_claim_established": False,
                    "hive_registry_modified": False},
    }
    result["proof_fingerprint_sha256"] = _hash(result)
    return result


def run_bridge(graph_fixture: dict, finance_packet: dict) -> dict:
    """Recalculate financial replay rather than trusting supplied summary text."""
    denial = _preflight(graph_fixture, finance_packet)
    if denial is not None:
        return denial
    from .financial_replay import replay  # optional S2 feature; no imports on denial
    replay_report = replay(finance_packet, input_sha256=_hash(finance_packet))
    return align_reports(graph_fixture, finance_packet, replay_report,
                         replay_recomputed=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HIVE fictional, offline cross-engine evidence alignment")
    parser.add_argument("--graph", required=True, help="Local synthetic graph JSON")
    parser.add_argument("--replay", required=True, help="Local synthetic financial replay packet JSON")
    args = parser.parse_args(argv)
    try:
        graph, _ = load_fixture(args.graph)
        # Both inputs have strict JSON loaders: reject duplicate keys, oversize and NaN.
        from .financial_replay import load_packet, ReplayBoundaryError
        finance, _ = load_packet(args.replay)
        output = run_bridge(graph, finance)
    except (ReviewBoundaryError, BridgeBoundaryError, ReplayBoundaryError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(output, sort_keys=True, indent=2, allow_nan=False))
    return 3 if output["state"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
