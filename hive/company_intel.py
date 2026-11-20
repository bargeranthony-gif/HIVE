"""Synthetic, offline-only company-intelligence review candidate for HIVE.

This additive module does not contact providers, HIVE's database, BROXSON,
ARKHIVE, or AI Network OS. It does not grant authority or commercial rights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

VERSION = "0.1.1-review"
PROVIDERS = (
    "ImportYeti", "ZoomInfo", "DataForB2B", "Global Database",
    "Company Dossier", "Legal Data Hunter", "CourtListener",
)
ACCEPTED_RIGHTS = {"SYNTHETIC_ONLY"}
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.,:/()'-]{0,95}$")


def _safe_label(value: object, label: str) -> str:
    if not isinstance(value, str) or not SAFE_LABEL.fullmatch(value):
        raise ReviewBoundaryError(f"Invalid {label}; unsafe or unbounded text")
    return value


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReviewBoundaryError("Duplicate JSON key prohibited")
        result[key] = value
    return result


def _reject_nonfinite(value):
    raise ReviewBoundaryError("Nonfinite JSON values prohibited")


class ReviewBoundaryError(ValueError):
    """Invalid, unavailable, or unauthorized test input."""


def aware_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ReviewBoundaryError("A timestamp must be a string")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewBoundaryError("Invalid ISO 8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ReviewBoundaryError("Offset-aware timestamps required")
    return result


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10**15:
        raise ReviewBoundaryError(f"{name} must be a bounded nonnegative integer")
    return value


def load_fixture(path: str | Path) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    if len(raw) > 1_000_000:
        raise ReviewBoundaryError("Fixture is too large")
    try:
        fixture = json.loads(raw, object_pairs_hook=_no_duplicate_keys,
                             parse_constant=_reject_nonfinite)
    except ReviewBoundaryError:
        raise
    except (ValueError, UnicodeError) as exc:
        raise ReviewBoundaryError("Invalid UTF-8 JSON fixture") from exc
    if not isinstance(fixture, dict) or fixture.get("synthetic") is not True:
        raise ReviewBoundaryError("Only explicitly synthetic fixtures are accepted")
    if fixture.get("mode") != "OFFLINE_ONLY":
        raise ReviewBoundaryError("Live or unspecified input mode is prohibited")
    return fixture, hashlib.sha256(raw).hexdigest()


def evaluate_fixture(fixture: dict, *, fixture_sha256: str = "UNPINNED") -> dict:
    if fixture.get("synthetic") is not True or fixture.get("mode") != "OFFLINE_ONLY":
        raise ReviewBoundaryError("Synthetic offline mode is mandatory")
    as_of_raw = fixture.get("as_of")
    as_of = aware_time(as_of_raw)
    tenant = fixture.get("tenant_id")
    entity = fixture.get("entity")
    if not isinstance(tenant, str) or not tenant.startswith("tenant-fixture-"):
        raise ReviewBoundaryError("Only fictional tenant IDs are accepted")
    _safe_label(tenant, "fixture tenant")
    if not isinstance(entity, dict):
        raise ReviewBoundaryError("No target entity")
    registry_id = entity.get("registry_id")
    jurisdiction = entity.get("jurisdiction")
    if not isinstance(registry_id, str) or not registry_id.startswith("FAKE-"):
        raise ReviewBoundaryError("Nonfictional registered identifiers are prohibited")
    _safe_label(registry_id, "registry ID")
    _safe_label(jurisdiction, "jurisdiction")
    _safe_label(entity.get("name"), "fictional entity name")
    records = fixture.get("records")
    if not isinstance(records, list):
        raise ReviewBoundaryError("Records must be a list")
    # The S1 first-of-kind reader cannot safely adjudicate revisions or
    # first-availability timestamps: use the S2 temporal engine instead.
    if "graph_entities" in fixture or any(
        isinstance(r, dict) and ("first_available_at" in r or "revision_of" in r)
        for r in records
    ):
        raise ReviewBoundaryError("Temporal evidence requires hive.temporal_graph")

    evidence = []
    excluded = {"other_identity": 0, "other_tenant": 0, "restricted": 0,
                "future": 0, "rights_or_cost": 0}
    accepted_ids = set()
    roots = set()
    for rec in records:
        if not isinstance(rec, dict):
            raise ReviewBoundaryError("Evidence must be an object")
        # Check tenant/visibility before any content is read or surfaced.
        if rec.get("tenant_id") != tenant:
            excluded["other_tenant"] += 1
            continue
        if rec.get("visibility") != "PUBLIC_SYNTHETIC":
            excluded["restricted"] += 1
            continue
        if rec.get("registry_id") != registry_id or rec.get("jurisdiction") != jurisdiction:
            excluded["other_identity"] += 1
            continue
        available = aware_time(rec.get("published_at"))
        if available > as_of:
            excluded["future"] += 1
            continue
        price = rec.get("cost_usd")
        usage_rights = rec.get("usage_rights")
        if (not isinstance(usage_rights, str) or usage_rights not in ACCEPTED_RIGHTS
                or isinstance(price, bool) or price != 0):
            excluded["rights_or_cost"] += 1
            continue
        source_id = rec.get("source_id")
        root_id = rec.get("root_id")
        _safe_label(source_id, "source ID")
        _safe_label(root_id, "original root")
        if source_id in accepted_ids:
            raise ReviewBoundaryError("Duplicate source ID")
        accepted_ids.add(source_id)
        if isinstance(rec.get("kind"), str) and rec["kind"] in {
                "registry", "filed_financials", "vendor_estimate", "shipments",
                "docket", "legislation"}:
            if not isinstance(rec.get("value"), dict):
                raise ReviewBoundaryError("Accepted claim value must be an object")
            roots.add(root_id)
        evidence.append(rec)

    def first(kind: str):
        return next((r for r in evidence if r.get("kind") == kind), None)

    reg = first("registry")
    filing = first("filed_financials")
    estimate = first("vendor_estimate")
    shipments = first("shipments")
    docket = first("docket")
    law = first("legislation")

    def link(rec):
        return (f"[{rec['source_id']}; {rec['root_id']}]" if rec else "UNKNOWN")

    # Never transform vendor estimates or shipments into filed revenue.
    claims = []
    if reg:
        claims.append({"type": "registered_status", "source": link(reg),
                       "value": _safe_label(reg.get("value", {}).get("status", "UNKNOWN"), "registry status"),
                       "truth_class": "RECORDED_IN_FIXTURE"})
    if filing:
        raw = filing.get("value", {})
        amount = _integer(raw.get("revenue_usd"), "filed revenue")
        claims.append({"type": "filed_revenue", "source": link(filing),
                       "amount_usd": amount, "period": _safe_label(raw.get("period", "UNKNOWN"), "financial period"),
                       "truth_class": "RECORDED_IN_FIXTURE"})
    if estimate:
        raw = estimate.get("value", {})
        amount = _integer(raw.get("revenue_estimate_usd"), "revenue estimate")
        claims.append({"type": "vendor_revenue_estimate", "source": link(estimate),
                       "amount_usd": amount, "period": _safe_label(raw.get("period", "UNKNOWN"), "financial period"),
                       "truth_class": "CONTEXTUAL_IN_FIXTURE"})
    if shipments:
        raw = shipments.get("value", {})
        count = _integer(raw.get("shipment_count"), "shipment count")
        customs_value = _integer(raw.get("declared_customs_value_usd"), "customs value")
        claims.append({"type": "shipment_activity", "source": link(shipments),
                       "count": count, "customs_value_usd": customs_value,
                       "period": _safe_label(raw.get("period", "UNKNOWN"), "shipment period"),
                       "supplier": _safe_label(raw.get("supplier", "UNKNOWN"), "supplier label"),
                       "supplier_dependency_verified": False,
                       "revenue_implied": False, "truth_class": "RECORDED_IN_FIXTURE"})
    if docket:
        raw = docket.get("value", {})
        claims.append({"type": "litigation", "source": link(docket),
                       "allegation_filed": raw.get("allegation_filed") is True,
                       "dismissed": raw.get("dismissed") is True,
                       "adverse_judgment": raw.get("adverse_judgment") is True,
                       "case_id": _safe_label(raw.get("case_id", "UNKNOWN"), "case ID"),
                       "truth_class": "RECORDED_IN_FIXTURE"})
    if law:
        raw = law.get("value", {})
        claims.append({"type": "regulatory_proposal", "source": link(law),
                       "status": _safe_label(raw.get("status", "UNKNOWN"), "regulation status"),
                       "effective": raw.get("status") == "ENACTED_EFFECTIVE",
                       "truth_class": "RECORDED_IN_FIXTURE"})

    discrepancies = []
    if filing and estimate:
        filed_amount = next(c["amount_usd"] for c in claims if c["type"] == "filed_revenue")
        estimated_amount = next(c["amount_usd"] for c in claims if c["type"] == "vendor_revenue_estimate")
        if filed_amount != estimated_amount:
            discrepancies.append({"code": "REPORTED_VS_ESTIMATED_DISCREPANCY",
                                  "filed_usd": filed_amount,
                                  "estimated_usd": estimated_amount,
                                  "sources": [filing["source_id"], estimate["source_id"]],
                                  "resolved": False})

    statuses = fixture.get("provider_states", {})
    if not isinstance(statuses, dict):
        raise ReviewBoundaryError("Provider states must be an object")
    provider_states = {name: ("NOT_CONFIGURED" if name == "DataForB2B" else "MOCK_READY")
                       for name in PROVIDERS}
    for name, state in statuses.items():
        if name in provider_states and state in {"MOCK_READY", "NOT_CONFIGURED", "MOCK_UNAVAILABLE"}:
            provider_states[name] = state
    errors = fixture.get("provider_errors", {})
    if not isinstance(errors, dict):
        raise ReviewBoundaryError("Provider errors must be an object")
    known_errors = {"HTTP_401", "HTTP_402", "HTTP_403", "HTTP_429", "TIMEOUT",
                    "OUTAGE", "PARTIAL_FAILURE"}
    for name, code in errors.items():
        if name in provider_states and code in known_errors:
            provider_states[name] = "MOCK_UNAVAILABLE"

    return {
        "classification": "SYNTHETIC_OFFLINE_CANDIDATE",
        "version": VERSION,
        "as_of": as_of.isoformat(),
        "tenant_id": tenant,
        "entity": {"name": entity["name"], "registry_id": registry_id,
                   "jurisdiction": jurisdiction, "match": "CONFIRMED_BY_EXACT_FIXTURE_ID"},
        "claims": claims,
        "discrepancies": discrepancies,
        "unique_original_roots": len(roots),
        "source_ids": [r["source_id"] for r in evidence],
        "excluded_counts": excluded,
        "provider_states": provider_states,
        "hypothesis": {
            "truth_class": "ANALYTICAL_UNVERIFIED",
            "condition": "If the proposal becomes effective and this supplier remains material, sourcing exposure could change",
            "alternatives": ["Supplier mix may change", "Contracts may absorb costs",
                             "Proposal may never take effect"],
            "falsifiers": ["Verify enacted and effective policy",
                           "Verify actual supplier materiality", "Review applicable contracts"],
            "predictive_impact_established": False,
        },
        "unknown": ["Net profit, margin and debt", "Beneficial ownership",
                    "Complete litigation coverage", "Supplier exclusivity",
                    "Future shipments", "Predictive financial performance"],
        "receipt": {"fixture_sha256": fixture_sha256, "live_provider_calls": 0,
                    "api_credits_spent": 0, "external_writes": 0,
                    "hive_registry_modified": False,
                    "maturity": "ISOLATED_REVIEW_CANDIDATE_NOT_VERIFIED_IN_PRODUCTION"},
    }


def render_markdown(report: dict) -> str:
    e = report["entity"]
    lines = ["# HIVE Company Intelligence Brief — Synthetic Review Candidate", "",
             "**SYNTHETIC OFFLINE DEMONSTRATION. NO LIVE PROVIDERS OR TRADING.**", "",
             f"As-of: {report['as_of']} | Tenant: {report['tenant_id']}",
             f"Entity: {e['name']} | {e['jurisdiction']} | {e['registry_id']} | {e['match']}",
             "", "## Source-linked observations", ""]
    for claim in report["claims"]:
        kind = claim["type"]
        if kind == "filed_revenue":
            lines.append(f"- Filed revenue: {claim['amount_usd']:,} USD ({claim['period']}); not profit. {claim['source']}")
        elif kind == "vendor_revenue_estimate":
            lines.append(f"- Vendor-estimated revenue: {claim['amount_usd']:,} USD ({claim['period']}); NOT filed. {claim['source']}")
        elif kind == "shipment_activity":
            lines.append(f"- Shipments: {claim['count']} ({claim['period']}); declared customs value {claim['customs_value_usd']:,} USD; not sales or margin. Observed supplier association: {claim['supplier']}; dependency not verified. {claim['source']}")
        elif kind == "litigation":
            lines.append(f"- Case {claim['case_id']}: allegation filed={claim['allegation_filed']}, dismissed={claim['dismissed']}, adverse judgment={claim['adverse_judgment']}. {claim['source']}")
        elif kind == "regulatory_proposal":
            lines.append(f"- Regulatory status={claim['status']}; effective={claim['effective']}. {claim['source']}")
        else:
            lines.append(f"- Registered status={claim['value']}. {claim['source']}")
    lines.extend(["", "## Contradictions and uncertainty", ""])
    for discrepancy in report["discrepancies"]:
        lines.append(f"- {discrepancy['code']}: filed {discrepancy['filed_usd']:,} USD vs vendor estimate {discrepancy['estimated_usd']:,} USD. Do not average.")
    if not report["discrepancies"]:
        lines.append("- No comparable discrepancy established from available fixture; not a clean bill of health.")
    lines.extend(["", "## Conditional hypothesis", "",
                  f"**UNVERIFIED:** {report['hypothesis']['condition']}.", "",
                  "Alternatives: " + "; ".join(report["hypothesis"]["alternatives"]) + ".",
                  "Falsifiers: " + "; ".join(report["hypothesis"]["falsifiers"]) + ".",
                  "", "## UNKNOWN", ""])
    lines.extend("- " + item for item in report["unknown"])
    lines.extend(["", "## Provider state — fixtures only", ""])
    lines.extend("- " + name + ": " + state for name, state in report["provider_states"].items())
    receipt = report["receipt"]
    lines.extend(["", "## Provenance and execution boundary", "",
                  f"Independent synthetic source roots: {report['unique_original_roots']}.",
                  f"Fixture SHA-256: `{receipt['fixture_sha256']}`.",
                  f"Live calls: {receipt['live_provider_calls']}; credits: {receipt['api_credits_spent']}; external writes: {receipt['external_writes']}.",
                  f"Maturity: {receipt['maturity']}.",
                  "This is not a legal determination, credit recommendation, investment advice, or trading signal."])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HIVE offline fictional company intelligence review")
    parser.add_argument("--fixture", required=True, help="Fictional offline JSON fixture")
    parser.add_argument("--output", help="Directory for an evidence report; omitted means stdout only")
    args = parser.parse_args(argv)
    try:
        fixture, sha = load_fixture(args.fixture)
        report = evaluate_fixture(fixture, fixture_sha256=sha)
    except (ReviewBoundaryError, OSError) as exc:
        parser.error(str(exc))
    markdown = render_markdown(report)
    if args.output:
        target = Path(args.output)
        target.mkdir(parents=True, exist_ok=True)
        (target / "company_brief.md").write_text(markdown, encoding="utf-8")
        (target / "company_brief.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
