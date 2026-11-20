"""Pure offline point-in-time admissibility checks for financial observations.

Research-only: no network, persistence, dynamic code, or provider integration.
Rejected records are never silently converted into eligible observations.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any

REQUIRED = (
    "source_id", "record_id", "issuer_cik", "legal_importer_id",
    "event_date", "first_publication_time", "retrieved_at",
    "available_as_of", "usage_rights", "units", "value",
    "mapping_proof", "revision_id",
)


# Strictly bounded, display-safe *fixture labels*. These do not authenticate identity.
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
SAFE_UNITS = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,31}$")


def _safe_id(value: Any) -> bool:
    return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None


def _safe_units(value: Any) -> bool:
    return isinstance(value, str) and SAFE_UNITS.fullmatch(value) is not None


def _safe_number(value: Any) -> bool:
    # Preserve finite, signed generic economic measures; later shipment-specific
    # admission is stricter. Short-circuit before math.isfinite for huge integers.
    return (type(value) in (int, float) and abs(value) <= 10**15
            and (type(value) is int or math.isfinite(value)))


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a nonempty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp requires an explicit timezone")
    return parsed.astimezone(timezone.utc)


def assess(record: Any, cutoff: str) -> dict[str, Any]:
    """Return an explicit admission decision without changing the input record.

    Rights must be explicitly approved for this research use, not merely
    present. Source-embedded text is data, never execution authority.
    """
    cutoff_dt = _utc(cutoff)
    if not isinstance(record, dict):
        return {"eligible": False, "reasons": ["INVALID_RECORD"]}
    reasons = []
    for field in REQUIRED:
        if field not in record or record[field] is None or record[field] == "":
            reasons.append("MISSING_" + field.upper())
    if record.get("usage_rights") != "APPROVED_RESEARCH":
        reasons.append("USAGE_RIGHTS_UNVERIFIED")
    proof = record.get("mapping_proof")
    if not isinstance(proof, dict) or proof.get("status") != "VERIFIED" or not _safe_id(proof.get("evidence_id")):
        reasons.append("ISSUER_MAPPING_UNVERIFIED")
    cik = record.get("issuer_cik")
    if not (isinstance(cik, str) and len(cik) == 10 and cik.isascii() and cik.isdigit()):
        reasons.append("ISSUER_CIK_INVALID")
    for field in ("source_id", "record_id", "revision_id", "legal_importer_id"):
        if not _safe_id(record.get(field)):
            reasons.append("INVALID_" + field.upper())
    if not _safe_units(record.get("units")):
        reasons.append("INVALID_UNITS")
    if not _safe_number(record.get("value")):
        reasons.append("VALUE_INVALID")
    for field in ("event_date", "first_publication_time", "retrieved_at", "available_as_of"):
        try:
            when = _utc(record.get(field))
        except ValueError:
            reasons.append("INVALID_" + field.upper())
            continue
        if field in ("event_date", "first_publication_time", "available_as_of") and when > cutoff_dt:
            reasons.append("AFTER_PREDICTION_CUTOFF_" + field.upper())
    try:
        first = _utc(record.get("first_publication_time"))
        available = _utc(record.get("available_as_of"))
        retrieved = _utc(record.get("retrieved_at"))
        if available < first or retrieved < first:
            reasons.append("INCONSISTENT_AVAILABILITY")
    except ValueError:
        pass
    return {"eligible": not reasons, "reasons": sorted(set(reasons)),
            "source_id": record.get("source_id") if _safe_id(record.get("source_id")) else None,
            "record_id": record.get("record_id") if _safe_id(record.get("record_id")) else None,
            "revision_id": record.get("revision_id") if _safe_id(record.get("revision_id")) else None}


def validate_snapshot(records: list[dict[str, Any]], cutoff: str) -> dict[str, Any]:
    """Evaluate rows independently, retaining distinct historical revisions.

    Duplicate exact (source, record, revision) identities are blocked instead
    of double-counted. Eligibility does not establish historical data rights.
    """
    _utc(cutoff)
    seen = set()
    decisions = []
    for record in records:
        decision = assess(record, cutoff)
        # A rejected row cannot reserve an identity and poison a valid row;
        # never hash malformed/untrusted objects as revision identifiers.
        if decision["eligible"]:
            key = (decision["source_id"], decision["record_id"], decision["revision_id"])
            if key in seen:
                decision = {**decision, "eligible": False,
                            "reasons": sorted(set(decision["reasons"] + ["DUPLICATE_REVISION"]))}
            else:
                seen.add(key)
        decisions.append(decision)
    return {"cutoff": cutoff, "total": len(decisions),
            "eligible": sum(bool(x["eligible"]) for x in decisions),
            "blocked": sum(not x["eligible"] for x in decisions),
            "decisions": decisions,
            "scope": "SYNTHETIC_METADATA_SHAPE_REVIEW_ONLY",
            "production_accepted": False,
            "real_data_rights_verified": False,
            "predictive_improvement": "UNKNOWN"}
