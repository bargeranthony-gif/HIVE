"""HIVE S2: bounded, synthetic-only, point-in-time evidence graph.

Opt-in research extension of the S1 fixture; no imports from HIVE's database,
network discovery, external providers, or BROXSON governance internals.
No commercial rights or source authority can be granted through fixture data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .company_intel import ReviewBoundaryError, aware_time, load_fixture

VERSION = "0.2.0-review"
MAX_RECORDS = 1000
MAX_ENTITIES = 64
MAX_PATHS = 128
MAX_HOPS = 3
TAG = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,79}$")
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 .,&'()-]{0,95}$")
PERIOD = re.compile(r"^(?:FY[0-9]{4}|20[0-9]{2}-[01][0-9])$")
RELATIONS = {"SUPPLIES_OBSERVED", "SHIPS_THROUGH_OBSERVED", "OPERATES_IN_CLAIMED"}
CERTAINTY = {"OBSERVED_ASSOCIATION", "DOCUMENTED_IN_FIXTURE"}
SUPPORTED = {
    "registry", "filed_financials", "vendor_estimate", "shipments",
    "docket", "legislation", "relationship",
}


def _label(value: object, what: str, pattern=TAG) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ReviewBoundaryError(f"Invalid {what} (untrusted or unbounded text)")
    return value


def _money(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10**15:
        raise ReviewBoundaryError(f"Invalid {what}")
    return value


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("ascii")).hexdigest()


def _utc(value: str) -> datetime:
    return aware_time(value).astimezone(timezone.utc)


def _period(value: object) -> str:
    return _label(value, "financial period", PERIOD)


def _record_claims(rec: dict) -> list[dict]:
    """Interpret only explicitly mapped fields, never free-text instructions."""
    value = rec.get("value")
    if not isinstance(value, dict):
        raise ReviewBoundaryError("Source value must be an object")
    kind = rec["kind"]
    base = {"subject": rec["registry_id"], "source_id": rec["source_id"],
            "root_id": rec["root_id"], "available_at": rec["usable_at"]}

    def claim(predicate, period, datum, truth):
        return {**base, "predicate": predicate, "period": period,
                "value": datum, "truth_class": truth}

    if kind == "filed_financials":
        return [claim("FILED_REVENUE_USD", _period(value.get("period")),
                      _money(value.get("revenue_usd"), "filed revenue"), "RECORDED_IN_FIXTURE")]
    if kind == "vendor_estimate":
        return [claim("VENDOR_REVENUE_ESTIMATE_USD", _period(value.get("period")),
                      _money(value.get("revenue_estimate_usd"), "revenue estimate"),
                      "CONTEXTUAL_IN_FIXTURE")]
    if kind == "shipments":
        period = _period(value.get("period"))
        return [claim("SHIPMENT_COUNT", period,
                      _money(value.get("shipment_count"), "shipment count"), "RECORDED_IN_FIXTURE"),
                claim("DECLARED_CUSTOMS_VALUE_USD", period,
                      _money(value.get("declared_customs_value_usd"), "customs value"),
                      "RECORDED_IN_FIXTURE")]
    if kind == "registry":
        status = _label(value.get("status"), "registry status")
        return [claim("REGISTRY_STATUS", "CURRENT", status, "RECORDED_IN_FIXTURE")]
    if kind == "docket":
        # Every negative is scoped to this named case, never the whole company.
        case_id = _label(value.get("case_id"), "fictional docket ID")
        def legal_fact(field):
            v = value.get(field)
            return v if type(v) is bool else "UNKNOWN"
        return [claim("DOCKET_ADVERSE_JUDGMENT", case_id,
                      legal_fact("adverse_judgment"), "RECORDED_IN_FIXTURE"),
                claim("DOCKET_DISMISSED", case_id,
                      legal_fact("dismissed"), "RECORDED_IN_FIXTURE")]
    if kind == "legislation":
        bill_id = _label(value.get("bill"), "fictional bill ID")
        status = _label(value.get("status"), "regulatory status")
        effective = {"PROPOSED": False, "ENACTED_NOT_EFFECTIVE": False,
                     "ENACTED_EFFECTIVE": True}.get(status, "UNKNOWN")
        return [claim("BILL_EFFECTIVE", bill_id, effective,
                      "RECORDED_IN_FIXTURE")]
    return []


def _entities(fixture: dict) -> dict[str, dict]:
    primary = fixture.get("entity")
    if not isinstance(primary, dict):
        raise ReviewBoundaryError("Missing primary fictional entity")
    extra = fixture.get("graph_entities", [])
    if not isinstance(extra, list) or len(extra) + 1 > MAX_ENTITIES:
        raise ReviewBoundaryError("Entity cap exceeded or invalid")
    found = {}
    for e in [primary, *extra]:
        if not isinstance(e, dict):
            raise ReviewBoundaryError("Invalid graph entity")
        eid = _label(e.get("registry_id"), "fictional entity ID")
        if not eid.startswith("FAKE-"):
            raise ReviewBoundaryError("Only fake registry identifiers allowed")
        name = _label(e.get("name"), "fictional entity name", NAME)
        jurisdiction = _label(e.get("jurisdiction"), "jurisdiction")
        if eid in found:
            raise ReviewBoundaryError("Duplicate graph entity identifier")
        found[eid] = {"registry_id": eid, "name": name, "jurisdiction": jurisdiction}
    return found


def _admit_records(fixture: dict, *, as_of: datetime, entities: dict):
    records = fixture.get("records")
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ReviewBoundaryError("Record cap exceeded or invalid")
    tenant = _label(fixture.get("tenant_id"), "tenant ID")
    if not tenant.startswith("tenant-fixture-"):
        raise ReviewBoundaryError("Only fictional tenants allowed")
    excluded = {reason: 0 for reason in (
        "other_tenant", "restricted", "other_identity", "future_or_unavailable",
        "unknown_availability", "rights_or_cost", "unsupported_kind",
    )}
    accepted = {}
    for rec in records:
        if not isinstance(rec, dict):
            raise ReviewBoundaryError("Record must be an object")
        # Scope first: do not inspect, format, hash, or expose excluded payloads.
        if rec.get("tenant_id") != tenant:
            excluded["other_tenant"] += 1
            continue
        if rec.get("visibility") != "PUBLIC_SYNTHETIC":
            excluded["restricted"] += 1
            continue
        registry_id = rec.get("registry_id")
        entity = entities.get(registry_id) if isinstance(registry_id, str) else None
        if entity is None or rec.get("jurisdiction") != entity["jurisdiction"]:
            excluded["other_identity"] += 1
            continue
        if rec.get("usage_rights") != "SYNTHETIC_ONLY" or type(rec.get("cost_usd")) is not int or rec.get("cost_usd") != 0:
            excluded["rights_or_cost"] += 1
            continue
        if not isinstance(rec.get("kind"), str) or rec["kind"] not in SUPPORTED:
            excluded["unsupported_kind"] += 1
            continue
        if "first_available_at" not in rec:
            excluded["unknown_availability"] += 1
            continue
        published = _utc(rec.get("published_at"))
        first_available = _utc(rec["first_available_at"])
        effective = max(published, first_available)
        if effective > as_of:
            excluded["future_or_unavailable"] += 1
            continue
        source_id = _label(rec.get("source_id"), "source ID")
        root_id = _label(rec.get("root_id"), "source root")
        if source_id in accepted:
            raise ReviewBoundaryError("Duplicate active source ID")
        if not isinstance(rec.get("value"), dict):
            raise ReviewBoundaryError("Accepted source value must be an object")
        accepted[source_id] = {**rec, "source_id": source_id, "root_id": root_id,
                               "usable_at": effective.isoformat(),
                               "published_at": published.isoformat(),
                               "first_available_at": first_available.isoformat()}

    # Explicit same-root, same-kind revision chains are the only way to supersede.
    superseded = set()
    for source_id, rec in accepted.items():
        previous_id = rec.get("revision_of")
        if previous_id is None:
            continue
        _label(previous_id, "revision source ID")
        previous = accepted.get(previous_id)
        if previous is None:
            raise ReviewBoundaryError("Revision predecessor is not admissible at this as-of")
        if previous_id == source_id or previous["usable_at"] >= rec["usable_at"]:
            raise ReviewBoundaryError("Cyclic, out-of-order, or non-increasing revision")
        if any(rec[k] != previous[k] for k in ("root_id", "kind", "registry_id", "jurisdiction")):
            raise ReviewBoundaryError("Revision crosses original root, kind, or entity")
        if rec["kind"] in ("filed_financials", "vendor_estimate", "shipments"):
            if rec["value"].get("period") != previous["value"].get("period"):
                raise ReviewBoundaryError("Revision crosses measurement period")
        superseded.add(previous_id)
    return accepted, superseded, excluded


def _relationships(records: dict, *, entities: dict, superseded: set):
    edges = []
    for source_id in sorted(records):
        rec = records[source_id]
        if rec["kind"] != "relationship" or source_id in superseded:
            continue
        raw = rec.get("value")
        if not isinstance(raw, dict):
            raise ReviewBoundaryError("Relationship value must be an object")
        target = _label(raw.get("object_registry_id"), "relationship target")
        relation = _label(raw.get("predicate"), "relationship predicate")
        certainty = _label(raw.get("certainty"), "association qualifier")
        if target not in entities or relation not in RELATIONS or certainty not in CERTAINTY:
            raise ReviewBoundaryError("Undocumented target, relation or certainty")
        edges.append({"subject": rec["registry_id"], "object": target,
                      "predicate": relation, "qualification": certainty,
                      "source_id": source_id, "root_id": rec["root_id"],
                      "available_at": rec["usable_at"],
                      "causality_established": False, "control_established": False})
    return edges


def _paths(edges: list[dict], origin: str):
    by_origin = defaultdict(list)
    for edge in edges:
        by_origin[edge["subject"]].append(edge)
    for out_edges in by_origin.values():
        out_edges.sort(key=lambda x: (x["object"], x["predicate"], x["source_id"]))
    results = []

    def walk(node: str, visited: tuple[str, ...], steps: tuple[dict, ...]):
        if len(steps) >= MAX_HOPS or len(results) >= MAX_PATHS:
            return
        for edge in by_origin[node]:
            if edge["object"] in visited:
                continue
            updated = (*steps, edge)
            results.append({"entities": [*visited, edge["object"]],
                            "evidence_source_ids": [e["source_id"] for e in updated],
                            "original_roots": sorted({e["root_id"] for e in updated}),
                            "inference": "REACHABILITY_ONLY_NOT_CAUSAL_OR_OWNERSHIP"})
            if len(results) >= MAX_PATHS:
                return
            walk(edge["object"], (*visited, edge["object"]), updated)
            if len(results) >= MAX_PATHS:
                return

    walk(origin, (origin,), ())
    return results


def _claims(records: dict, superseded: set):
    rows = []
    for source_id in sorted(records):
        rec = records[source_id]
        if source_id in superseded:
            continue
        rows.extend(_record_claims(rec))
    by_key = defaultdict(list)
    for row in rows:
        by_key[(row["subject"], row["predicate"], row["period"])].append(row)
    claims = []
    conflicts = []
    for key in sorted(by_key):
        group = by_key[key]
        roots = defaultdict(list)
        for c in group:
            roots[c["root_id"]].append(c)
        root_values = {root: {_canonical(r["value"]) for r in items}
                       for root, items in roots.items()}
        if any(len(v) > 1 for v in root_values.values()):
            conflict_type = "SAME_ORIGINAL_ROOT_CONTRADICTION"
        elif len(set.union(*root_values.values())) > 1:
            conflict_type = "INDEPENDENT_ORIGINAL_ROOT_DISAGREEMENT"
        else:
            conflict_type = None
        if conflict_type:
            conflicts.append({"type": conflict_type, "subject": key[0],
                              "predicate": key[1], "period": key[2],
                              "source_ids": sorted(r["source_id"] for r in group),
                              "root_ids": sorted(roots), "resolved": False,
                              "numeric_aggregation_permitted": False})
        # Repeated republications cannot inflate independent support.
        by_value_root = defaultdict(list)
        for c in group:
            by_value_root[(c["root_id"], _canonical(c["value"]))].append(c)
        for items in by_value_root.values():
            first = sorted(items, key=lambda r: r["source_id"])[0]
            claims.append({**first, "supporting_source_ids": sorted(r["source_id"] for r in items),
                           "independent_root_count": len(roots),
                           "adjudication": "UNRESOLVED_DISAGREEMENT" if conflict_type else "SOURCE_LINKED_NOT_INDEPENDENTLY_VERIFIED"})
    return sorted(claims, key=lambda c: (c["subject"], c["predicate"], c["period"], c["root_id"])), conflicts


def evaluate_temporal_graph(fixture: dict, *, as_of: str | None = None) -> dict:
    if not isinstance(fixture, dict) or fixture.get("synthetic") is not True or fixture.get("mode") != "OFFLINE_ONLY":
        raise ReviewBoundaryError("Only explicitly synthetic OFFLINE_ONLY research is accepted")
    query_as_of = _utc(as_of if as_of is not None else fixture.get("as_of"))
    entities = _entities(fixture)
    primary_id = _label(fixture["entity"]["registry_id"], "primary identity")
    accepted, superseded, excluded = _admit_records(fixture, as_of=query_as_of, entities=entities)
    edges = _relationships(accepted, entities=entities, superseded=superseded)
    claims, conflicts = _claims(accepted, superseded)
    # Differing measurement classes create a discrepancy, not evidence to average.
    by_filed = defaultdict(list)
    for c in claims:
        if c["predicate"] == "FILED_REVENUE_USD":
            by_filed[(c["subject"], c["period"])].append(c)
    for other in claims:
        if other["predicate"] == "VENDOR_REVENUE_ESTIMATE_USD":
            filed_group = by_filed.get((other["subject"], other["period"]), [])
            if filed_group and any(c["value"] != other["value"] for c in filed_group):
                conflicts.append({"type": "FILED_VS_ESTIMATE_NOT_COMPARABLE_AS_SAME_TRUTH",
                                  "subject": other["subject"], "period": other["period"],
                                  "source_ids": sorted([c["source_id"] for c in filed_group] +
                                                       [other["source_id"]]),
                                  "resolved": False, "numeric_aggregation_permitted": False})
    traces = [{"source_id": sid, "root_id": r["root_id"],
               "published_at": r["published_at"], "first_available_at": r["first_available_at"],
               "usable_at": r["usable_at"], "sha256": _digest(r)}
              for sid, r in sorted(accepted.items())]
    return {
        "classification": "SYNTHETIC_OFFLINE_TEMPORAL_GRAPH_REVIEW",
        "version": VERSION, "as_of": query_as_of.isoformat(),
        "tenant_id": fixture["tenant_id"], "origin_registry_id": primary_id,
        "entities": [entities[k] for k in sorted(entities)],
        "claims": claims, "conflicts": sorted(conflicts, key=lambda x: (x["type"], x["subject"], x["period"])),
        "relationships": edges, "paths": _paths(edges, primary_id),
        "excluded_counts": excluded,
        "provenance": {"source_traces": traces,
                       "original_root_count": len({r["root_id"] for r in accepted.values()}),
                       "accepted_record_set_sha256": _digest(traces),
                       "source_independence": "UNIQUE_ROOT_IDS_IN_FIXTURE_NOT_A_REAL_WORLD_AUDIT"},
        "open_questions": ["Identity ownership outside the fixture", "Completeness of source coverage",
                           "Economic materiality and causal impact", "Data licensing and consent",
                           "Predictive performance and forecast calibration"],
        "receipt": {"live_provider_calls": 0, "api_credits_spent": 0, "trades_executed": 0,
                    "external_writes": 0, "hive_database_modified": False,
                    "commercial_derivative_permission": "UNKNOWN_NOT_GRANTED",
                    "maturity": "ISOLATED_SYNTHETIC_LOCAL_REVIEW_ONLY",
                    "forecast_or_causal_edge_established": False},
    }



def compare_temporal_graph(fixture: dict, *, from_as_of: str, to_as_of: str) -> dict:
    """Deterministic evidence delta; no inference of causation or performance."""
    before_time, after_time = _utc(from_as_of), _utc(to_as_of)
    if before_time >= after_time:
        raise ReviewBoundaryError("Historical comparison requires increasing cutoff times")
    before = evaluate_temporal_graph(fixture, as_of=from_as_of)
    after = evaluate_temporal_graph(fixture, as_of=to_as_of)

    def claim_identity(row):
        return (row["subject"], row["predicate"], row["period"],
                row["root_id"], row["source_id"], _canonical(row["value"]))

    left_claims = {claim_identity(x): x for x in before["claims"]}
    right_claims = {claim_identity(x): x for x in after["claims"]}
    key_path = lambda x: (tuple(x["entities"]), tuple(x["evidence_source_ids"]))
    left_paths = {key_path(x): x for x in before["paths"]}
    right_paths = {key_path(x): x for x in after["paths"]}
    key_conflict = lambda x: (x["type"], x["subject"], x["period"],
                              tuple(x["source_ids"]))
    left_conflicts = {key_conflict(x): x for x in before["conflicts"]}
    right_conflicts = {key_conflict(x): x for x in after["conflicts"]}
    source_left = {t["source_id"] for t in before["provenance"]["source_traces"]}
    source_right = {t["source_id"] for t in after["provenance"]["source_traces"]}
    return {
        "classification": "SYNTHETIC_OFFLINE_HISTORICAL_CHANGE_REVIEW",
        "from_as_of": before["as_of"], "to_as_of": after["as_of"],
        "newly_eligible_source_ids": sorted(source_right - source_left),
        "claims_added": [right_claims[k] for k in sorted(right_claims.keys() - left_claims.keys())],
        "claims_removed_or_superseded": [left_claims[k] for k in sorted(left_claims.keys() - right_claims.keys())],
        "new_conflicts": [right_conflicts[k] for k in sorted(right_conflicts.keys() - left_conflicts.keys())],
        "new_paths": [right_paths[k] for k in sorted(right_paths.keys() - left_paths.keys())],
        "source_set_hash_before": before["provenance"]["accepted_record_set_sha256"],
        "source_set_hash_after": after["provenance"]["accepted_record_set_sha256"],
        "receipt": {"live_provider_calls": 0, "api_credits_spent": 0,
                    "trades_executed": 0, "external_writes": 0,
                    "hive_database_modified": False,
                    "maturity": "ISOLATED_SYNTHETIC_LOCAL_REVIEW_ONLY",
                    "causality_or_predictive_impact_established": False},
    }


def render_temporal_delta(delta: dict) -> str:
    lines = ["# HIVE S2 Historical Evidence Change (Synthetic Only)", "",
             "**NOT REAL ECONOMIC ACTIVITY OR FORECASTING EVIDENCE.**", "",
             f"Snapshot comparison: `{delta['from_as_of']}` to `{delta['to_as_of']}`.", "",
             "## Newly admissible source IDs", ""]
    lines.extend("- `" + source + "`" for source in delta["newly_eligible_source_ids"])
    lines += ["", "## Added or revised claims", ""]
    lines.extend("- " + row["predicate"] + " / " + row["period"] +
                 ": " + str(row["value"]) + " (source `" + row["source_id"] + "`)"
                 for row in delta["claims_added"])
    lines += ["", "## Removed or superseded claims", ""]
    lines.extend("- " + row["predicate"] + " / " + row["period"] +
                 ": " + str(row["value"]) + " (source `" + row["source_id"] + "`)"
                 for row in delta["claims_removed_or_superseded"])
    lines += ["", "## Newly observed contradictions and paths", ""]
    lines.extend("- Conflict: " + row["type"] + " (" + ", ".join(row["source_ids"]) + ")"
                 for row in delta["new_conflicts"])
    lines.extend("- Directed path: " + " -> ".join(row["entities"]) + " (not causal)"
                 for row in delta["new_paths"])
    lines += ["", "No live sources, authority grants, forecasts, paid data, or trades.", ""]
    return "\n".join(lines)


def render_graph_markdown(report: dict) -> str:
    """Only prevalidated labels and structural facts. No raw vendor prose."""
    lines = ["# HIVE S2 Point-in-Time Evidence Graph (Synthetic Only)", "",
             "**REVIEW-ONLY. NOT A REAL COMPANY REPORT OR TRADING SIGNAL.**", "",
             f"As-of: `{report['as_of']}`. Entity: `{report['origin_registry_id']}`.", "",
             "## Scoped evidence claims", ""]
    for claim in report["claims"]:
        lines.append(f"- `{claim['subject']}` / `{claim['predicate']}` / `{claim['period']}`: "
                     f"`{claim['value']}`; {claim['adjudication']}. "
                     f"Root `{claim['root_id']}`, source `{claim['source_id']}`.")
    lines += ["", "## Unresolved contradictions and non-comparable measurements", ""]
    for conflict in report["conflicts"]:
        lines.append(f"- {conflict['type']}: {', '.join(conflict['source_ids'])}. "
                     "No automatic winner, weighting, averaging, or maturity promotion.")
    if not report["conflicts"]:
        lines.append("- No conflict found in this bounded fixture; completeness is UNKNOWN.")
    lines += ["", "## Directed evidence paths (NOT causal conclusions)", ""]
    for path in report["paths"]:
        lines.append("- " + " -> ".join(f"`{eid}`" for eid in path["entities"]) +
                     "; sources: " + ", ".join(path["evidence_source_ids"]))
    if not report["paths"]:
        lines.append("- No admissible relationship paths as of this snapshot.")
    lines += ["", "## Audit boundaries", "",
              f"Accepted original roots: {report['provenance']['original_root_count']} (fixture-defined only).",
              f"Accepted-set SHA-256: `{report['provenance']['accepted_record_set_sha256']}`.",
              f"Excluded counts: `{_canonical(report['excluded_counts'])}`.",
              "No network, paid data, external writes, code execution from source text, or governance override.",
              "Commercial derivative permission is UNKNOWN and not granted by this report.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HIVE offline synthetic temporal evidence graph")
    parser.add_argument("--fixture", required=True, help="Explicitly synthetic local JSON fixture")
    parser.add_argument("--as-of", help="Offset-aware ISO 8601 historical snapshot")
    parser.add_argument("--compare-from", help="Earlier offset-aware cutoff for a synthetic historical diff")
    parser.add_argument("--output", help="Optional local output directory")
    args = parser.parse_args(argv)
    try:
        fixture, _ = load_fixture(args.fixture)
        if args.compare_from:
            report = compare_temporal_graph(fixture, from_as_of=args.compare_from,
                                            to_as_of=args.as_of or fixture.get("as_of"))
            markdown = render_temporal_delta(report)
            basename = "temporal_delta"
        else:
            report = evaluate_temporal_graph(fixture, as_of=args.as_of)
            markdown = render_graph_markdown(report)
            basename = "temporal_graph"
    except (ReviewBoundaryError, OSError) as exc:
        parser.error(str(exc))
    if args.output:
        folder = Path(args.output)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (basename + ".json")).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (folder / (basename + ".md")).write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
