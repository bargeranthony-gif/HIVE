"""Read-only evidence assessment for HAIE v0.2.

This module does not modify identity records, personality traits,
personality revisions, or governance state.
"""

from collections import defaultdict
import re


_ALLOWED_SENTIMENTS = {
    "positive", "negative", "neutral", "mixed", "unknown"
}


def _normalize_observation(value):
    """Normalize whitespace and case for exact-text comparison."""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _validate_experience(record):
    if not isinstance(record, dict):
        raise ValueError("Every experience must be a dictionary.")

    required = {
        "experience_id",
        "identity_id",
        "interaction_type",
        "observation",
        "sentiment",
        "confidence",
        "source_type",
    }

    missing = required.difference(record)
    if missing:
        raise ValueError(
            "Experience is missing required fields: "
            + ", ".join(sorted(missing))
        )

    for field in (
        "experience_id",
        "identity_id",
        "interaction_type",
        "observation",
        "source_type",
    ):
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be non-empty text.")

    if record["sentiment"] not in _ALLOWED_SENTIMENTS:
        raise ValueError("Invalid sentiment classification.")

    confidence = record["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0.0 <= confidence <= 1.0
    ):
        raise ValueError("Confidence must be numeric and between 0 and 1.")

    for field in ("subject_id", "session_id"):
        value = record.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be text or None.")


def evaluate_evidence(
    experiences,
    *,
    minimum_independent_sessions=2,
):
    """Assess repeated observations and session independence.

    Exact normalized observations are grouped by identity, subject,
    and interaction type.

    Records without session IDs are not counted as independent sessions.
    No semantic contradiction detection or personality adaptation occurs.
    """

    if (
        isinstance(minimum_independent_sessions, bool)
        or not isinstance(minimum_independent_sessions, int)
        or minimum_independent_sessions < 1
    ):
        raise ValueError(
            "Minimum independent sessions must be a positive integer."
        )

    if not isinstance(experiences, (list, tuple)):
        raise ValueError("Experiences must be a list or tuple.")

    groups = defaultdict(list)
    seen_ids = set()

    for record in experiences:
        _validate_experience(record)

        experience_id = record["experience_id"]
        if experience_id in seen_ids:
            raise ValueError(
                f"Duplicate experience ID: {experience_id}"
            )
        seen_ids.add(experience_id)

        key = (
            record["identity_id"],
            record.get("subject_id"),
            record["interaction_type"],
            _normalize_observation(record["observation"]),
        )
        groups[key].append(record)

    assessments = []

    for key, records in sorted(
        groups.items(),
        key=lambda item: (
            item[0][0],
            item[0][1] or "",
            item[0][2],
            item[0][3],
        ),
    ):
        identity_id, subject_id, interaction_type, normalized = key

        sessions = sorted({
            record["session_id"]
            for record in records
            if record.get("session_id")
        })

        unscoped_count = sum(
            1 for record in records
            if not record.get("session_id")
        )

        sentiments = sorted({
            record["sentiment"]
            for record in records
            if record["sentiment"] != "unknown"
        })

        source_types = sorted({
            record["source_type"]
            for record in records
        })

        independent_count = len(sessions)

        assessments.append({
            "identity_id": identity_id,
            "subject_id": subject_id,
            "interaction_type": interaction_type,
            "normalized_observation": normalized,
            "experience_ids": sorted(
                record["experience_id"] for record in records
            ),
            "observation_count": len(records),
            "repeated": len(records) > 1,
            "independent_session_count": independent_count,
            "session_ids": sessions,
            "unscoped_observation_count": unscoped_count,
            "sentiments": sentiments,
            "sentiment_disagreement": len(sentiments) > 1,
            "source_types": source_types,
            "confidence_range": [
                min(record["confidence"] for record in records),
                max(record["confidence"] for record in records),
            ],
            "contradiction_status": "not_assessed",
            "review_status": (
                "eligible_for_owner_review"
                if independent_count >= minimum_independent_sessions
                else "insufficient_independent_sessions"
            ),
        })

    return {
        "assessment_version": "0.1",
        "read_only": True,
        "minimum_independent_sessions": minimum_independent_sessions,
        "group_count": len(assessments),
        "assessments": assessments,
    }
