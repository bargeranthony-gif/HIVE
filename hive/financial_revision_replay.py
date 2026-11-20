"""Deterministic, offline, *synthetic-only* financial history replay.

Never use this module to confer rights, certify provenance, or generate a
production-ready trading signal. It checks fixture assertions, not legal facts.
No database, network, subprocess, dynamic evaluation, or executable inputs.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from .financial_history import _utc, assess

SCHEMA_VERSION = "finance-pit-synthetic-v1"
FUTURE_CODE = "REVISION_AFTER_CUTOFF"
MAX_ROWS = 1000
MAX_SOURCE_CHARS = 64000
REQUIRED_EXTRA = (
    "provider", "source_root_id", "tenant_id", "visibility", "data_class",
    "revision_number", "revision_publication_time", "source_excerpt",
    "source_excerpt_sha256", "availability_evidence", "rights_evidence",
    "measurement_period_start", "measurement_period_end",
)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _when(value: Any, reasons: set[str], name: str) -> datetime | None:
    try:
        return _utc(value)
    except (ValueError, TypeError, OverflowError):
        reasons.add("INVALID_" + name.upper())
        return None


def _row(record: Any, cutoff: datetime, tenant_id: str) -> dict[str, Any]:
    # Scope is checked before any field inspection. Foreign/restricted records
    # have no influence on in-scope groups and no identifiers in the receipt.
    if not isinstance(record, dict):
        return {"provider": None, "source_id": None, "record_id": None,
                "revision_id": None, "selected": False, "eligible": False,
                "reasons": ["INVALID_RECORD"], "future": False}
    boundary = set()
    if record.get("tenant_id") != tenant_id:
        boundary.add("TENANT_SCOPE_DENIED")
    if record.get("visibility") != "PUBLIC_SYNTHETIC" or record.get("data_class") != "SYNTHETIC":
        boundary.add("NON_SYNTHETIC_OR_RESTRICTED_INPUT")
    if boundary:
        return {"provider": None, "source_id": None, "record_id": None,
                "revision_id": None, "selected": False, "eligible": False,
                "reasons": sorted(boundary), "future": False}
    base = assess(record, cutoff.isoformat())
    reasons = set(base["reasons"])
    decision = {
        "provider": record.get("provider"), "source_id": base.get("source_id"),
        "record_id": base.get("record_id"),
        "revision_id": base.get("revision_id"),
        "selected": False, "eligible": False,
    }
    for field in REQUIRED_EXTRA:
        if field not in record or record[field] is None or record[field] == "":
            reasons.add("MISSING_" + field.upper())
    for field in ("provider", "source_id", "record_id", "source_root_id",
                  "revision_id", "legal_importer_id"):
        if not _nonempty(record.get(field)):
            reasons.add("INVALID_" + field.upper())
    if record.get("tenant_id") != tenant_id:
        reasons.add("TENANT_SCOPE_DENIED")
    if record.get("visibility") != "PUBLIC_SYNTHETIC" or record.get("data_class") != "SYNTHETIC":
        reasons.add("NON_SYNTHETIC_OR_RESTRICTED_INPUT")
    cik = record.get("issuer_cik")
    if not isinstance(cik, str) or len(cik) != 10 or not cik.isascii() or not cik.isdigit():
        reasons.add("ISSUER_CIK_FORMAT")
    if record.get("units") != "shipment_count":
        reasons.add("UNIT_NOT_SHIPMENT_COUNT")
    value = record.get("value")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        reasons.add("SHIPMENT_COUNT_INVALID")
    elif value > 1_000_000_000_000:
        reasons.add("SHIPMENT_COUNT_OUT_OF_RANGE")
    number = record.get("revision_number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        reasons.add("REVISION_NUMBER_INVALID")

    proof = record.get("mapping_proof")
    if not (isinstance(proof, dict) and proof.get("status") == "VERIFIED" and
            _nonempty(proof.get("evidence_id")) and
            proof.get("issuer_cik") == cik and
            proof.get("legal_importer_id") == record.get("legal_importer_id")):
        reasons.add("EXACT_MAPPING_PROOF_REQUIRED")

    rights = record.get("rights_evidence")
    if not (isinstance(rights, dict) and rights.get("status") == "FIXTURE_APPROVED" and
            rights.get("scope") == "OFFLINE_RESEARCH" and _nonempty(rights.get("reference"))):
        reasons.add("RIGHTS_RECEIPT_REQUIRED")

    evidence = record.get("availability_evidence")
    if not (isinstance(evidence, dict) and
            evidence.get("kind") in ("OFFICIAL_RELEASE", "ARCHIVED_CAPTURE") and
            evidence.get("status") == "FIXTURE_VERIFIED" and
            _nonempty(evidence.get("reference"))):
        reasons.add("INDEPENDENT_AVAILABILITY_RECEIPT_REQUIRED")

    content = record.get("source_excerpt")
    sha = record.get("source_excerpt_sha256")
    try:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest() if isinstance(content, str) else None
    except UnicodeEncodeError:
        digest = None
    if not (isinstance(content, str) and len(content) <= MAX_SOURCE_CHARS and
            isinstance(sha, str) and len(sha) == 64 and digest == sha):
        reasons.add("SOURCE_HASH_OR_CONTENT_INVALID")

    first = _when(record.get("first_publication_time"), reasons, "first_publication_time")
    revision = _when(record.get("revision_publication_time"), reasons, "revision_publication_time")
    available = _when(record.get("available_as_of"), reasons, "available_as_of")
    event = _when(record.get("event_date"), reasons, "event_date")
    start = _when(record.get("measurement_period_start"), reasons, "measurement_period_start")
    end = _when(record.get("measurement_period_end"), reasons, "measurement_period_end")
    evidence_time = _when(evidence.get("observed_at") if isinstance(evidence, dict) else None,
                          reasons, "availability_evidence_time")
    if first and revision and revision < first:
        reasons.add("REVISION_BEFORE_ORIGINAL_PUBLICATION")
    if revision and available and available < revision:
        reasons.add("AVAILABILITY_BEFORE_REVISION")
    if revision and evidence_time and evidence_time < revision:
        reasons.add("EVIDENCE_BEFORE_REVISION")
    if start and end and start > end:
        reasons.add("INVALID_MEASUREMENT_PERIOD")
    if end and event and end > event:
        reasons.add("MEASUREMENT_PERIOD_AFTER_EVENT")
    for date, code in ((event, "EVENT_AFTER_CUTOFF"),
                       (end, "MEASUREMENT_END_AFTER_CUTOFF"),
                       (evidence_time, "EVIDENCE_AFTER_CUTOFF")):
        if date and date > cutoff:
            reasons.add(code)
    if revision and revision > cutoff:
        reasons.add(FUTURE_CODE)
    # A revision timestamp after cutoff can be ignored for earlier snapshots;
    # its mere presence must not erase the valid, earlier historical revision.
    future = revision is not None and revision > cutoff
    return {**decision, "reasons": sorted(reasons), "future": future,
            "eligible": not reasons, "revision_number": number,
            "source_root_id": record.get("source_root_id")}


def replay_as_of(records: list[Any], cutoff: str, *, tenant_id: str = "SYNTHETIC") -> dict[str, Any]:
    """Return one latest eligible revision per independent synthetic source event.

    Missing, conflicting or unverifiable pre-cutoff revisions quarantine the
    entire event. Later revisions cannot rewrite earlier historical snapshots.
    Source text is never returned. Input order never affects the output digest.
    """
    cutoff_dt = _utc(cutoff)
    if not isinstance(records, list) or len(records) > MAX_ROWS:
        raise ValueError("records must be a list of <= 1000 observations")
    if not _nonempty(tenant_id):
        raise ValueError("tenant_id must be nonempty")
    decisions = [_row(row, cutoff_dt, tenant_id) for row in records]
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for i, row in enumerate(records):
        if (isinstance(row, dict) and row.get("tenant_id") == tenant_id and
                row.get("visibility") == "PUBLIC_SYNTHETIC" and
                row.get("data_class") == "SYNTHETIC"):
            key = (row.get("provider"), row.get("source_id"), row.get("record_id"))
            if all(_nonempty(part) for part in key):
                groups[key].append(i)
    selected_index: dict[tuple[str, str, str], int] = {}
    for key, ids in groups.items():
        historic = [i for i in ids if not decisions[i]["future"]]
        if not historic:
            continue
        if any(not decisions[i]["eligible"] for i in historic):
            for i in historic:
                decisions[i]["reasons"] = sorted(set(decisions[i]["reasons"]) | {"EVENT_QUARANTINED"})
                decisions[i]["eligible"] = False
            continue
        ordered = sorted(historic, key=lambda i: decisions[i]["revision_number"])
        numbers = [decisions[i]["revision_number"] for i in ordered]
        names = [records[i]["revision_id"] for i in ordered]
        broken = bool(numbers != list(range(1, len(ordered) + 1)) or len(set(names)) != len(names))
        # A revision can correct a value, not silently reassign the economic
        # event to another issuer, importer, source root or measured period.
        fixed_fields = (
            "provider", "source_id", "record_id", "source_root_id", "issuer_cik",
            "legal_importer_id", "measurement_period_start", "measurement_period_end", "units",
        )
        original = records[ordered[0]]
        if any(any(records[i].get(field) != original.get(field) for field in fixed_fields)
               for i in ordered[1:]):
            broken = True
        previous_time = None
        for position, i in enumerate(ordered):
            item = records[i]
            expected_parent = names[position - 1] if position else None
            if item.get("revision_parent_id") != expected_parent:
                broken = True
            pub = _utc(item["revision_publication_time"])
            if previous_time is not None and pub < previous_time:
                broken = True
            previous_time = pub
        if broken:
            for i in historic:
                decisions[i]["reasons"] = ["REVISION_LINEAGE_UNVERIFIED"]
                decisions[i]["eligible"] = False
            continue
        selected_index[key] = ordered[-1]

    # Identical underlying evidence in different provider records is not
    # independent support. Quarantine *all* conflicting candidates.
    root_to_group: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for key, i in selected_index.items():
        root_to_group[records[i]["source_root_id"]].append(key)
    for keys in root_to_group.values():
        if len(keys) > 1:
            for key in keys:
                i = selected_index.pop(key)
                decisions[i]["reasons"] = ["CROSS_SOURCE_ROOT_COLLISION"]
                decisions[i]["eligible"] = False

    output_rows = []
    for key, i in selected_index.items():
        row = records[i]
        decisions[i]["selected"] = True
        output_rows.append({
            "provider": key[0], "source_id": key[1], "record_id": key[2],
            "source_root_id": row["source_root_id"],
            "source_excerpt_sha256": row["source_excerpt_sha256"],
            "revision_id": row["revision_id"], "revision_number": row["revision_number"],
            "issuer_cik": row["issuer_cik"], "legal_importer_id": row["legal_importer_id"],
            "units": row["units"], "value": row["value"],
            "revision_publication_time": row["revision_publication_time"],
        })
    sort_key = lambda d: json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)
    output_rows.sort(key=sort_key)
    for d in decisions:
        # A valid superseded revision is admissible at cutoff, but not selected.
        d.pop("source_root_id", None)
        d.pop("revision_number", None)
        d.pop("future", None)
    decisions.sort(key=sort_key)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "cutoff": cutoff_dt.isoformat(),
        "scope": "OFFLINE_SYNTHETIC_ONLY",
        "records_received": len(records),
        "selected_count": len(output_rows),
        "blocked_count": sum(bool(d["reasons"]) for d in decisions),
        "decisions": decisions, "selected_observations": output_rows,
        "predictive_improvement": "UNKNOWN",
        "real_data_rights_verified": False,
        "production_accepted": False,
    }
    payload["receipt_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload
