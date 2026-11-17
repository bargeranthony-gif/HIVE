"""Structured evidence evaluation for HAIE v0.3."""

from collections import defaultdict
import re


def _normalize(value):
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _validate_claim(claim):
    if not isinstance(claim, dict):
        raise ValueError("Every claim must be a dictionary.")

    required = {
        "claim_id", "experience_id", "identity_id", "claim_key",
        "claim_value", "stance", "context_key", "confidence",
    }

    missing = required.difference(claim)
    if missing:
        raise ValueError(
            "Claim is missing fields: " + ", ".join(sorted(missing))
        )

    for field in (
        "claim_id", "experience_id", "identity_id",
        "claim_key", "claim_value", "context_key",
    ):
        value = claim[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be non-empty text.")

    if claim["stance"] not in {"supports", "refutes", "uncertain"}:
        raise ValueError("Invalid claim stance.")

    confidence = claim["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise ValueError("Confidence must be between 0 and 1.")

    for field in ("subject_id", "session_id", "interaction_type"):
        value = claim.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be text or None.")


def evaluate_claims(claims, *, minimum_independent_sessions=2):
    """Evaluate structured claims without changing personality or storage.

    Each session contributes at most one stance to a proposition.
    Sessions containing both supporting and refuting evidence are
    marked internally conflicted and excluded from both counts.
    """

    if (
        isinstance(minimum_independent_sessions, bool)
        or not isinstance(minimum_independent_sessions, int)
        or minimum_independent_sessions < 1
    ):
        raise ValueError("Minimum independent sessions must be positive.")

    if not isinstance(claims, (list, tuple)):
        raise ValueError("Claims must be a list or tuple.")

    seen_ids = set()
    groups = defaultdict(list)

    for claim in claims:
        _validate_claim(claim)

        if claim["claim_id"] in seen_ids:
            raise ValueError(f"Duplicate claim ID: {claim['claim_id']}")
        seen_ids.add(claim["claim_id"])

        key = (
            claim["identity_id"],
            claim.get("subject_id"),
            claim.get("interaction_type"),
            _normalize(claim["claim_key"]),
            _normalize(claim["claim_value"]),
            _normalize(claim["context_key"]),
        )
        groups[key].append(claim)

    assessments = []

    for key, records in sorted(
        groups.items(),
        key=lambda item: tuple(value or "" for value in item[0]),
    ):
        identity_id, subject_id, interaction_type, claim_key, claim_value, context = key

        by_session = defaultdict(list)
        unscoped = []

        for record in records:
            session = record.get("session_id")
            if isinstance(session, str) and session.strip():
                by_session[session].append(record)
            else:
                unscoped.append(record)

        supporting_sessions = []
        refuting_sessions = []
        uncertain_sessions = []
        internally_conflicted = []

        for session, session_records in sorted(by_session.items()):
            stances = {
                record["stance"]
                for record in session_records
                if record["stance"] != "uncertain"
            }

            if stances == {"supports", "refutes"}:
                internally_conflicted.append(session)
            elif stances == {"supports"}:
                supporting_sessions.append(session)
            elif stances == {"refutes"}:
                refuting_sessions.append(session)
            elif not stances:
                uncertain_sessions.append(session)

        support_count = len(supporting_sessions)
        refute_count = len(refuting_sessions)

        if support_count and refute_count:
            contradiction = "contradiction_detected"
            review = "conflict_requires_owner_review"
        elif support_count >= minimum_independent_sessions:
            contradiction = "no_conflict_observed"
            review = "eligible_for_owner_review"
        elif refute_count >= minimum_independent_sessions:
            contradiction = "no_conflict_observed"
            review = "eligible_for_owner_review"
        else:
            contradiction = "no_conflict_observed"
            review = "insufficient_independent_sessions"

        assessments.append({
            "identity_id": identity_id,
            "subject_id": subject_id,
            "interaction_type": interaction_type,
            "claim_key": claim_key,
            "claim_value": claim_value,
            "context_key": context,
            "claim_ids": sorted(record["claim_id"] for record in records),
            "observation_count": len(records),
            "supporting_session_count": support_count,
            "refuting_session_count": refute_count,
            "uncertain_session_count": len(uncertain_sessions),
            "supporting_sessions": supporting_sessions,
            "refuting_sessions": refuting_sessions,
            "internally_conflicted_sessions": internally_conflicted,
            "unscoped_observation_count": len(unscoped),
            "contradiction_status": contradiction,
            "review_status": review,
            "confidence_range": [
                min(record["confidence"] for record in records),
                max(record["confidence"] for record in records),
            ],
        })

    return {
        "assessment_version": "0.3",
        "read_only": True,
        "minimum_independent_sessions": minimum_independent_sessions,
        "group_count": len(assessments),
        "assessments": assessments,
    }
