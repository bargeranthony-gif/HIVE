from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .capabilities import (
    EVIDENCE_RANK,
    CapabilityRecord,
    evaluate_capability_records,
)
from .db import connect
from .planning import PlanningAssessment


IDENTITY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PlanIdentity:
    """Deterministic identity for a repository-scoped executable plan."""

    repository_id: int
    repository_url: str
    digest: str
    canonical_json: str

    @property
    def snapshot(self) -> dict[str, Any]:
        """Return a fresh copy of the canonical identity snapshot."""
        return json.loads(self.canonical_json)


def create_plan_identity(
    assessment: PlanningAssessment,
    repository_id: int,
) -> PlanIdentity:
    """
    Create a deterministic identity for a ready, repository-scoped plan.

    Repository validation, capability evaluation, and snapshot construction
    use one consistent SQLite read transaction.

    This function does not write governance or execution records.
    """
    if not isinstance(assessment, PlanningAssessment):
        raise TypeError("assessment must be a PlanningAssessment")

    if isinstance(repository_id, bool) or not isinstance(repository_id, int):
        raise ValueError("A valid repository_id is required")

    if repository_id <= 0:
        raise ValueError("A valid repository_id is required")

    if not assessment.ready:
        raise ValueError("Planning assessment is not ready for execution")

    minimum_level = assessment.minimum_evidence_level
    if minimum_level not in EVIDENCE_RANK:
        raise ValueError(f"Invalid minimum evidence level: {minimum_level!r}")

    required_names = tuple(
        dict.fromkeys(
            capability
            for step in assessment.plan.ordered_steps
            for capability in step.required_capabilities
        )
    )

    with connect() as conn:
        # Explicitly start a read transaction. The first SELECT establishes
        # the SQLite snapshot used by all subsequent reads.
        conn.execute("BEGIN")

        repository = conn.execute(
            """
            SELECT id, url
            FROM repositories
            WHERE id = ?
            """,
            (repository_id,),
        ).fetchone()

        if repository is None:
            raise ValueError(f"Repository not found: {repository_id}")

        rows = conn.execute(
            """
            SELECT
                id,
                repository_id,
                name,
                description,
                evidence_level,
                evidence
            FROM capabilities
            WHERE repository_id = ?
            ORDER BY id
            """,
            (repository_id,),
        ).fetchall()

        records = tuple(
            CapabilityRecord(
                id=row["id"],
                repository_id=row["repository_id"],
                name=row["name"],
                description=row["description"],
                evidence_level=row["evidence_level"],
                evidence=row["evidence"],
            )
            for row in rows
        )

        # Evaluate the exact records that will be used in the identity.
        evaluation = evaluate_capability_records(
            required_names,
            records,
            minimum_level,
        )

        if not evaluation.ready:
            raise ValueError(
                "Repository capability evidence does not satisfy the plan"
            )

        relevant_names = set(required_names)

        capability_snapshot = [
            {
                "id": record.id,
                "repository_id": record.repository_id,
                "name": record.name,
                "description": record.description,
                "evidence_level": record.evidence_level,
                "evidence": record.evidence,
            }
            for record in sorted(
                (
                    record
                    for record in records
                    if record.name in relevant_names
                ),
                key=lambda item: (item.name, item.id),
            )
        ]

        snapshot = {
            "identity_schema_version": IDENTITY_SCHEMA_VERSION,
            "repository": {
                "id": repository["id"],
                "url": repository["url"],
            },
            "minimum_evidence_level": minimum_level,
            "plan": assessment.plan.to_dict(),
            "capability_records": capability_snapshot,
        }

        canonical_json = json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        digest = hashlib.sha256(
            canonical_json.encode("utf-8")
        ).hexdigest()

        return PlanIdentity(
            repository_id=repository["id"],
            repository_url=repository["url"],
            digest=digest,
            canonical_json=canonical_json,
        )
