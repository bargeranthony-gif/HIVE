"""HIVE public-safe financial replay: offline, fictional evidence and frozen backtests.

Independent synthetic-only review utility. Does not import HIVE registry/database,
perform network I/O, execute source text, offer financial advice, or grant rights.
No results produced by this module constitute real-market evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
from typing import Any

VERSION = "0.2.0-synthetic-review"
SCHEMA = "hive.synthetic-financial-replay.v1"
METRICS = {"inventory_growth_pct_points": "percentage_points", "shipment_count": "shipments"}
MAX_BYTES = 1_000_000
MAX_RECORDS = 1000
MAX_CASES = 120


class ReplayBoundaryError(ValueError):
    """A source, timing, or research boundary failed; fail closed."""


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in pairs:
        if key in out:
            raise ReplayBoundaryError("Duplicate JSON key")
        out[key] = val
    return out


def _deny_constant(value: str) -> None:
    raise ReplayBoundaryError("Nonfinite JSON values are prohibited")


def load_packet(path: str | Path) -> tuple[dict[str, Any], str]:
    file = Path(path)
    if file.stat().st_size > MAX_BYTES:
        raise ReplayBoundaryError("Packet exceeds maximum size")
    data = file.read_bytes()
    if len(data) > MAX_BYTES:
        raise ReplayBoundaryError("Packet exceeds maximum size")
    try:
        packet = json.loads(data.decode("utf-8", errors="strict"),
                            object_pairs_hook=_object_pairs,
                            parse_constant=_deny_constant)
    except (ValueError, UnicodeError) as exc:
        raise ReplayBoundaryError("Invalid strict UTF-8 JSON packet") from exc
    _check_mode(packet)
    return packet, hashlib.sha256(data).hexdigest()


def _check_mode(packet: Any) -> None:
    if (not isinstance(packet, dict) or packet.get("schema") != SCHEMA
            or packet.get("synthetic") is not True
            or packet.get("mode") != "OFFLINE_ONLY"):
        raise ReplayBoundaryError("Only schema-matched fictional offline packets accepted")
    if (not isinstance(packet.get("tenant_id"), str)
            or not packet["tenant_id"].startswith("tenant-fixture-")):
        raise ReplayBoundaryError("Fictional tenant required")
    if (not isinstance(packet.get("entity_id"), str)
            or not packet["entity_id"].startswith("FAKE-")):
        raise ReplayBoundaryError("Fictional issuer required")


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ReplayBoundaryError("Timestamp must be string")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReplayBoundaryError("Invalid timestamp") from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ReplayBoundaryError("Offset-aware timestamp required")
    return t.astimezone(timezone.utc)


def _date(value: Any) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ReplayBoundaryError("ISO date YYYY-MM-DD required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReplayBoundaryError("Invalid period date") from exc


def _num(value: Any) -> Decimal:
    if not isinstance(value, str) or not value or len(value) > 48:
        raise ReplayBoundaryError("Values must be bounded decimal strings")
    try:
        n = Decimal(value)
    except InvalidOperation as exc:
        raise ReplayBoundaryError("Invalid decimal observation") from exc
    if not n.is_finite() or abs(n) > Decimal("1e12"):
        raise ReplayBoundaryError("Nonfinite or out-of-bound observation")
    return n


def _nat(value: Any, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ReplayBoundaryError(field + " outside permitted range")
    return value


def _decimal_str(n: Decimal) -> str:
    return format(n.quantize(Decimal("0.000001")), "f")


def _stable_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_records(packet: dict[str, Any]) -> tuple[dict[tuple[str, str], list[dict]], Counter]:
    obs = packet.get("observations")
    if not isinstance(obs, list) or not 1 <= len(obs) <= MAX_RECORDS:
        raise ReplayBoundaryError("Bounded observations list required")
    seen: set[str] = set()
    grouped: dict[tuple[str, str], list[dict]] = {}
    blocked: Counter = Counter()
    for r in obs:
        if not isinstance(r, dict):
            raise ReplayBoundaryError("Observation must be object")
        # Scope before content: untrusted foreign tenant/entity rows must not
        # influence duplicate checks, clocks, hash validation or revision chains.
        # Count exclusions without returning source IDs, text or foreign claims.
        if r.get("tenant_id") != packet["tenant_id"]:
            blocked["tenant"] += 1
            continue
        if r.get("entity_id") != packet["entity_id"]:
            blocked["identity"] += 1
            continue
        rid = r.get("record_id")
        if not isinstance(rid, str) or not rid.startswith("FAKE-") or rid in seen:
            raise ReplayBoundaryError("Duplicate or non-fictional record ID")
        seen.add(rid)
        metric, period = r.get("metric"), r.get("period_end")
        if not isinstance(metric, str) or metric not in METRICS or r.get("unit") != METRICS[metric]:
            raise ReplayBoundaryError("Unknown metric or mixed unit")
        p = _date(period)
        first, rev, retrieved = (_time(r.get(k)) for k in
                                 ("first_published_at", "revision_published_at", "retrieved_at"))
        if not first <= rev <= retrieved:
            raise ReplayBoundaryError("Invalid release/revision/retrieval order")
        # Public fiction identifiers are intentionally unlike live account identifiers.
        for k, prefix in (("source_id", "FAKE-SRC-"), ("root_id", "FAKE-ROOT-")):
            if not isinstance(r.get(k), str) or not r[k].startswith(prefix):
                raise ReplayBoundaryError("Synthetic source ID/root required")
        excerpt = r.get("source_excerpt")
        if not isinstance(excerpt, str) or len(excerpt.encode("utf-8")) > 2048:
            raise ReplayBoundaryError("Bounded source excerpt required")
        digest = r.get("excerpt_sha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or hashlib.sha256(excerpt.encode("utf-8")).hexdigest() != digest):
            raise ReplayBoundaryError("Source excerpt hash mismatch")
        val = _num(r.get("value"))
        if metric == "shipment_count" and (val < 0 or val != val.to_integral_value()):
            raise ReplayBoundaryError("Shipment count must be nonnegative integer")
        guarded = {
            "tenant": r.get("tenant_id") == packet["tenant_id"],
            "identity": r.get("entity_id") == packet["entity_id"],
            "rights": (r.get("rights") == "SYNTHETIC_ONLY"
                       and str(r.get("rights_evidence", "")).startswith("fixture://rights/")),
            "mapping": (r.get("mapping") == "EXACT_FAKE_ID"
                        and str(r.get("mapping_evidence", "")).startswith("fixture://map/")),
            "capture": r.get("capture_status") == "COMPLETE",
            "source": str(r.get("publication_evidence", "")).startswith("fixture://pub/"),
        }
        if not all(guarded.values()):
            for key, ok in guarded.items():
                if not ok:
                    blocked[key] += 1
            continue
        grouped.setdefault((metric, period), []).append({
            "record_id": rid, "metric": metric, "period_end": p,
            "value": val, "first_published_at": first,
            "revision_published_at": rev, "retrieved_at": retrieved,
            "source_id": r["source_id"], "root_id": r["root_id"],
            "replaces_record_id": r.get("replaces_record_id")
        })
    for versions in grouped.values():
        versions.sort(key=lambda r: (r["revision_published_at"], r["record_id"]))
        if len({r["root_id"] for r in versions}) != 1:
            raise ReplayBoundaryError("Unreconciled independent-root series conflict")
        if versions[0]["replaces_record_id"] is not None:
            raise ReplayBoundaryError("Unanchored first revision")
        for earlier, later in zip(versions, versions[1:]):
            if (later["replaces_record_id"] != earlier["record_id"]
                    or later["revision_published_at"] <= earlier["revision_published_at"]
                    or later["first_published_at"] != earlier["first_published_at"]):
                raise ReplayBoundaryError("Invalid vintage revision chain")
    return grouped, blocked


def _pick(grouped: dict, metric: str, period: str, cutoff: datetime,
          counters: Counter) -> dict | None:
    records = grouped.get((metric, period), [])
    eligible = [r for r in records if r["first_published_at"] <= cutoff
                and r["revision_published_at"] <= cutoff]
    counters["pre_cutoff_revisions_excluded"] += len(records) - len(eligible)
    if not eligible:
        return None
    latest = max(r["revision_published_at"] for r in eligible)
    same = [r for r in eligible if r["revision_published_at"] == latest]
    if len({r["value"] for r in same}) > 1:
        raise ReplayBoundaryError("Conflicting same-time vintages")
    # A repeated publication is not independent corroboration.
    return min(same, key=lambda r: r["record_id"])


def _feature(grouped: dict, case: dict, cutoff: datetime,
             stats: Counter) -> tuple[Decimal, Decimal, list[str]] | None:
    baseline = _pick(grouped, "inventory_growth_pct_points", case["baseline_period"], cutoff, stats)
    curr = _pick(grouped, "shipment_count", case["shipment_period"], cutoff, stats)
    prior = _pick(grouped, "shipment_count", case["shipment_compare_period"], cutoff, stats)
    if not (baseline and curr and prior):
        return None
    x = (curr["value"] - prior["value"]) / Decimal(100)
    return (baseline["value"], x,
            [baseline["record_id"], curr["record_id"], prior["record_id"]],
            [baseline["root_id"], curr["root_id"], prior["root_id"]])


def _fit(training: list[tuple[Decimal, Decimal]], penalty: Decimal) -> Decimal:
    """Univariate ridge adjustment trained only on available historical labels."""
    with localcontext() as ctx:
        ctx.prec = 34
        numerator = sum((x * y for x, y in training), Decimal(0))
        denominator = penalty + sum((x * x for x, _ in training), Decimal(0))
        return numerator / denominator if denominator else Decimal(0)


def _mean_absolute(pairs: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    if not pairs:
        return None
    with localcontext() as ctx:
        ctx.prec = 34
        return sum((abs(a-b) for a, b in pairs), Decimal(0)) / len(pairs)


def replay(packet: dict[str, Any], *, input_sha256: str = "UNPINNED") -> dict[str, Any]:
    """Run deterministic synthetic-only chronological replay with frozen final holdout."""
    _check_mode(packet)
    eva = _time(packet.get("evaluation_as_of"))
    hypothesis = packet.get("hypothesis")
    if not isinstance(hypothesis, dict) or hypothesis.get("target") != "inventory_growth_pct_points":
        raise ReplayBoundaryError("Preregistered inventory growth hypothesis required")
    if (not isinstance(hypothesis.get("hypothesis_id"), str)
            or not hypothesis["hypothesis_id"].startswith("FAKE-HYPOTHESIS-")):
        raise ReplayBoundaryError("Fictional hypothesis identifier required")
    if hypothesis.get("candidate") != "seasonal_naive_plus_shipment_yoy":
        raise ReplayBoundaryError("Unsupported candidate; no model searching")
    if hypothesis.get("holdout_fraction") != "0.20":
        raise ReplayBoundaryError("Frozen final 20% holdout required")
    min_train = _nat(hypothesis.get("min_training_cases"), "min_training_cases", 6, 6)
    penalty = _num(hypothesis.get("ridge_penalty"))
    if penalty != Decimal("1.0"):
        raise ReplayBoundaryError("Penalty is fixed and not optimized")
    grouped, blocked = _validate_records(packet)
    cases = packet.get("cases")
    if not isinstance(cases, list) or not 10 <= len(cases) <= MAX_CASES:
        raise ReplayBoundaryError("At least ten chronological forecast cases required")
    seen_ids = set()
    prepared = []
    prev_period = date.min
    prev_cutoff = datetime.min.replace(tzinfo=timezone.utc)

    def quarter_index(d: date) -> int:
        if d.month not in (3, 6, 9, 12):
            raise ReplayBoundaryError("Calendar quarter-end month required")
        import calendar
        if d.day != calendar.monthrange(d.year, d.month)[1]:
            raise ReplayBoundaryError("Calendar quarter end required")
        return d.year * 4 + d.month // 3
    for case in cases:
        if not isinstance(case, dict):
            raise ReplayBoundaryError("Forecast case must be object")
        cid = case.get("case_id")
        if not isinstance(cid, str) or not cid.startswith("FAKE-") or cid in seen_ids:
            raise ReplayBoundaryError("Nonfictional or duplicated forecast case")
        seen_ids.add(cid)
        keys = ("target_period", "baseline_period", "shipment_period", "shipment_compare_period")
        dates = [_date(case.get(k)) for k in keys]
        cutoff = _time(case.get("cutoff"))
        indexes = [quarter_index(d) for d in dates]
        if (indexes[1] != indexes[0] - 4
                or indexes[2] != indexes[0] - 1
                or indexes[3] != indexes[0] - 5
                or not dates[0] > prev_period or not cutoff > prev_cutoff
                or not cutoff.date() < dates[0] or cutoff >= eva):
            raise ReplayBoundaryError("Forecast period or cutoff violates chronology")
        prev_period, prev_cutoff = dates[0], cutoff
        prepared.append((case, cutoff))
    holdout_count = (len(prepared) + 4) // 5
    boundary = len(prepared) - holdout_count
    freeze_at = prepared[boundary][1]
    stats: Counter = Counter()

    def training_before(limit: int, as_of: datetime) -> tuple[list, list]:
        pairs = []
        train_ids = []
        evidence = []
        for old, old_cutoff in prepared[:limit]:
            feature = _feature(grouped, old, old_cutoff, stats)
            label = _pick(grouped, "inventory_growth_pct_points", old["target_period"], as_of, stats)
            if not feature or not label or label["first_published_at"] <= old_cutoff:
                continue
            baseline, signal, ids, roots = feature
            pairs.append((signal, label["value"] - baseline))
            train_ids.append(old["case_id"])
            evidence.append({"case_id": old["case_id"],
                             "feature_record_ids": ids,
                             "feature_root_ids": roots,
                             "training_label_record_id": label["record_id"]})
        return pairs, train_ids, evidence

    frozen_pairs, frozen_train_ids, frozen_training_evidence = training_before(boundary, freeze_at)
    frozen_beta = _fit(frozen_pairs, penalty) if len(frozen_pairs) >= min_train else None
    placebo_beta = None
    if frozen_beta is not None:
        xs = [x for x, _ in frozen_pairs]
        ys = [y for _, y in frozen_pairs]
        placebo_beta = _fit(list(zip(reversed(xs), ys)), penalty)

    rows = []
    baseline_scores: list[tuple[Decimal, Decimal]] = []
    candidate_scores: list[tuple[Decimal, Decimal]] = []
    baseline_only_scored = 0
    placebo_scores: list[tuple[Decimal, Decimal]] = []
    for i, (case, cutoff) in enumerate(prepared):
        feature = _feature(grouped, case, cutoff, stats)
        label_known_at_forecast = _pick(grouped, "inventory_growth_pct_points",
                                        case["target_period"], cutoff, stats)
        if label_known_at_forecast:
            raise ReplayBoundaryError("Target value already available at prediction cutoff")
        row = {"case_id": case["case_id"], "target_period": case["target_period"],
               "cutoff": cutoff.isoformat(), "set": "HOLDOUT" if i >= boundary else "TRAINING",
               "status": "NO_USABLE_FEATURE", "prediction": None,
               "support": {"source_record_ids": [], "source_root_ids": [],
                           "trained_on_case_ids": []}}
        if not feature:
            # A missing shipment signal must not erase a valid seasonal baseline.
            baseline_only = _pick(grouped, "inventory_growth_pct_points",
                                  case["baseline_period"], cutoff, stats)
            if baseline_only:
                row["status"] = "BASELINE_ONLY_SIGNAL_UNAVAILABLE"
                row["prediction"] = {"baseline": _decimal_str(baseline_only["value"]),
                                     "candidate": None, "shipment_yoy_hundreds": None}
                row["support"]["source_record_ids"] = [baseline_only["record_id"]]
                row["support"]["source_root_ids"] = [baseline_only["root_id"]]
                if i >= boundary:
                    outcome = _pick(grouped, "inventory_growth_pct_points",
                                    case["target_period"], eva, stats)
                    if outcome:
                        row["outcome_at_evaluation"] = {"value": _decimal_str(outcome["value"]),
                                                         "source_record_id": outcome["record_id"]}
                        baseline_scores.append((baseline_only["value"], outcome["value"]))
                        baseline_only_scored += 1
            rows.append(row)
            continue
        baseline, x, source_ids, source_roots = feature
        row["support"]["source_record_ids"] = source_ids
        row["support"]["source_root_ids"] = source_roots
        if i >= boundary:
            beta = frozen_beta
            used_training = frozen_train_ids
        else:
            past, used_training, _ = training_before(i, cutoff)
            beta = _fit(past, penalty) if len(past) >= min_train else None
        row["support"]["trained_on_case_ids"] = used_training if beta is not None else []
        row["prediction"] = {"baseline": _decimal_str(baseline),
                              "candidate": _decimal_str(baseline + beta*x) if beta is not None else None,
                              "shipment_yoy_hundreds": _decimal_str(x)}
        row["status"] = "PREDICTED" if beta is not None else "INSUFFICIENT_HISTORICAL_TRAINING"
        if i >= boundary:
            outcome = _pick(grouped, "inventory_growth_pct_points", case["target_period"], eva, stats)
            if outcome:
                row["outcome_at_evaluation"] = {"value": _decimal_str(outcome["value"]),
                                                 "source_record_id": outcome["record_id"]}
                baseline_scores.append((baseline, outcome["value"]))
                if beta is not None:
                    candidate_scores.append((baseline+beta*x, outcome["value"]))
                    placebo_scores.append((baseline+placebo_beta*x, outcome["value"]))
        rows.append(row)
    base_mae = _mean_absolute(baseline_scores)
    candidate_mae = _mean_absolute(candidate_scores)
    placebo_mae = _mean_absolute(placebo_scores)
    paired = bool(base_mae is not None and candidate_mae is not None
                  and len(baseline_scores) == len(candidate_scores))
    full_coverage = paired and len(baseline_scores) == holdout_count
    skill = (Decimal(1) - candidate_mae / base_mae
             if full_coverage and base_mae != 0 else None)
    placebo_status = "UNAVAILABLE"
    if placebo_mae is not None and candidate_mae is not None:
        placebo_status = ("PLACEBO_COMPETITIVE" if placebo_mae <= candidate_mae * Decimal("1.10")
                          else "PLACEBO_WORSE_NOT_CAUSAL_PROOF")
    metrics = {"holdout_case_count": holdout_count,
               "baseline_scored_n": len(baseline_scores),
               "candidate_scored_n": len(candidate_scores),
               "baseline_only_scored_n": baseline_only_scored,
               "paired_sample": paired,
               "full_holdout_coverage": full_coverage,
               "comparison_gate": "FULL_SYNTHETIC_COVERAGE" if full_coverage else "INCOMPLETE_HOLDOUT_UNKNOWN",
               "falsification_diagnostic": placebo_status,
               "baseline_mae": _decimal_str(base_mae) if base_mae is not None else "UNKNOWN",
               "candidate_mae": _decimal_str(candidate_mae) if candidate_mae is not None else "UNKNOWN",
               "placebo_mae": _decimal_str(placebo_mae) if placebo_mae is not None else "UNKNOWN",
               "relative_mae_improvement": _decimal_str(skill) if skill is not None else "UNKNOWN",
               "interpretation": "SYNTHETIC_ONLY_NOT_FINANCIAL_EVIDENCE"}
    report = {"schema": "hive.financial-replay-output.v1", "classification": "FICTIONAL_OFFLINE_RESEARCH",
              "preregistration_claim": hypothesis, "entity_id": packet["entity_id"],
              "training_freeze_cutoff": freeze_at.isoformat(),
              "frozen_train_case_ids": frozen_train_ids if frozen_beta is not None else [],
              "frozen_training_evidence": frozen_training_evidence if frozen_beta is not None else [],
              "frozen_slope": _decimal_str(frozen_beta) if frozen_beta is not None else "UNKNOWN",
              "forecasts": rows, "holdout_metrics": metrics,
              "evidence_boundaries": {"invalid_or_unapproved": dict(sorted(blocked.items())),
                                      "as_of_checks_excluding_later_versions": stats["pre_cutoff_revisions_excluded"],
                                      "source_documents_independently_authenticated": False,
                                      "claimed_rights_independently_verified": False,
                                      "semantic_support_independently_verified": False,
                                      "market_returns_modeled": False,
                                      "preregistration_independently_verified": False},
              "receipt": {"version": VERSION, "input_sha256": input_sha256,
                          "provider_calls": 0, "external_writes": 0, "registry_writes": 0,
                          "trades": 0, "broker_connections": 0, "operating_mode": "LOCAL_SYNTHETIC_ONLY",
                          "maturity": "CANDIDATE_LOCAL_TEST_NOT_APPROVED"}}
    report["receipt"]["output_sha256"] = _stable_hash(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HIVE synthetic historical forecasting replay (no live data)")
    parser.add_argument("--fixture", required=True, help="Fictional offline packet; strictly no real data")
    args = parser.parse_args(argv)
    try:
        packet, sha = load_packet(args.fixture)
        report = replay(packet, input_sha256=sha)
    except (ReplayBoundaryError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
