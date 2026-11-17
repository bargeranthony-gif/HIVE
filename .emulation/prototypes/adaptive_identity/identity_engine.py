from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


TRAITS = {
    "sociability",
    "humor",
    "competitiveness",
    "formality",
    "patience",
    "playfulness",
}

DEFAULT_PERSONALITY = {
    "sociability": 0.50,
    "humor": 0.50,
    "competitiveness": 0.50,
    "formality": 0.50,
    "patience": 0.50,
    "playfulness": 0.50,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _validate_traits(values: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(values, Mapping):
        raise ValueError("Personality traits must be a mapping.")

    unknown = set(values) - TRAITS
    if unknown:
        raise ValueError(f"Unknown personality traits: {sorted(unknown)}")

    result = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Trait {key!r} must be numeric.")
        number = float(value)
        if not 0.0 <= number <= 1.0:
            raise ValueError(f"Trait {key!r} must be between 0 and 1.")
        result[key] = number
    return result


class IdentityStore:
    """Experimental persistent identity and social-memory store."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS identities (
                    identity_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    baseline_json TEXT NOT NULL,
                    adaptive_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS experiences (
                    experience_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    subject_id TEXT,
                    interaction_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    significance REAL NOT NULL CHECK (
                        significance >= 0 AND significance <= 1
                    ),
                    tags_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_experiences_identity
                    ON experiences(identity_id);

                CREATE INDEX IF NOT EXISTS idx_experiences_subject
                    ON experiences(identity_id, subject_id);

                CREATE TABLE IF NOT EXISTS social_contacts (
                    identity_id TEXT NOT NULL REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    subject_id TEXT NOT NULL,
                    display_name TEXT,
                    notes TEXT,
                    interaction_count INTEGER NOT NULL DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    PRIMARY KEY(identity_id, subject_id)
                );

                CREATE TABLE IF NOT EXISTS personality_revisions (
                    revision_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    changes_json TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'accepted', 'rejected')
                    ),
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT
                );
            """)

    def create_identity(
        self,
        identity_id: str,
        display_name: str,
        baseline: Mapping[str, Any] | None = None,
    ) -> dict:
        if not identity_id.strip() or not display_name.strip():
            raise ValueError("Identity ID and display name are required.")

        traits = dict(DEFAULT_PERSONALITY)
        if baseline is not None:
            traits.update(_validate_traits(baseline))

        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO identities
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    identity_id,
                    display_name,
                    _json(traits),
                    _json({}),
                    now,
                    now,
                ),
            )
        return self.get_identity(identity_id)

    def get_identity(self, identity_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown identity: {identity_id}")

        return {
            "identity_id": row["identity_id"],
            "display_name": row["display_name"],
            "baseline": json.loads(row["baseline_json"]),
            "adaptive": json.loads(row["adaptive_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def record_experience(
        self,
        experience_id: str,
        identity_id: str,
        interaction_type: str,
        summary: str,
        *,
        subject_id: str | None = None,
        significance: float = 0.5,
        tags: tuple[str, ...] | list[str] = (),
        observed_at: str | None = None,
    ) -> dict:
        if not experience_id.strip():
            raise ValueError("Experience ID is required.")
        if not interaction_type.strip() or not summary.strip():
            raise ValueError("Interaction type and summary are required.")
        if len(summary) > 1000:
            raise ValueError("Experience summary cannot exceed 1000 characters.")
        if isinstance(significance, bool) or not isinstance(significance, (int, float)):
            raise ValueError("Significance must be numeric.")
        if not 0.0 <= significance <= 1.0:
            raise ValueError("Significance must be between 0 and 1.")
        if not all(isinstance(tag, str) and tag.strip() for tag in tags):
            raise ValueError("Tags must be non-empty strings.")

        now = _now()
        observed = observed_at or now

        with self._connect() as conn:
            if conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone() is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            conn.execute(
                """
                INSERT INTO experiences
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experience_id,
                    identity_id,
                    subject_id,
                    interaction_type,
                    summary,
                    float(significance),
                    _json(list(tags)),
                    observed,
                    now,
                ),
            )

            if subject_id:
                conn.execute(
                    """
                    INSERT INTO social_contacts (
                        identity_id, subject_id, display_name, notes,
                        interaction_count, first_seen, last_seen
                    )
                    VALUES (?, ?, NULL, NULL, 1, ?, ?)
                    ON CONFLICT(identity_id, subject_id)
                    DO UPDATE SET
                        interaction_count = interaction_count + 1,
                        last_seen = excluded.last_seen
                    """,
                    (identity_id, subject_id, now, now),
                )

        return self.get_experience(experience_id)

    def get_experience(self, experience_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM experiences WHERE experience_id = ?",
                (experience_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown experience: {experience_id}")

        return {
            "experience_id": row["experience_id"],
            "identity_id": row["identity_id"],
            "subject_id": row["subject_id"],
            "interaction_type": row["interaction_type"],
            "summary": row["summary"],
            "significance": row["significance"],
            "tags": json.loads(row["tags_json"]),
            "observed_at": row["observed_at"],
        }

    def list_experiences(self, identity_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT experience_id FROM experiences
                WHERE identity_id = ?
                ORDER BY created_at, experience_id
                """,
                (identity_id,),
            ).fetchall()

        return [self.get_experience(row["experience_id"]) for row in rows]

    def get_social_contact(self, identity_id: str, subject_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM social_contacts
                WHERE identity_id = ? AND subject_id = ?
                """,
                (identity_id, subject_id),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown social contact: {subject_id}")

        return dict(row)

    def update_social_contact(
        self,
        identity_id: str,
        subject_id: str,
        *,
        display_name: str | None = None,
        notes: str | None = None,
    ) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE social_contacts
                SET display_name = COALESCE(?, display_name),
                    notes = COALESCE(?, notes)
                WHERE identity_id = ? AND subject_id = ?
                """,
                (display_name, notes, identity_id, subject_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown social contact: {subject_id}")

        return self.get_social_contact(identity_id, subject_id)

    def forget_subject(self, identity_id: str, subject_id: str) -> None:
        """Remove a contact and its associated stored experiences."""
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM experiences
                WHERE identity_id = ? AND subject_id = ?
                """,
                (identity_id, subject_id),
            )
            conn.execute(
                """
                DELETE FROM social_contacts
                WHERE identity_id = ? AND subject_id = ?
                """,
                (identity_id, subject_id),
            )

    def propose_personality_revision(
        self,
        revision_id: str,
        identity_id: str,
        changes: Mapping[str, Any],
        rationale: str,
        evidence_ids: list[str] | tuple[str, ...],
    ) -> dict:
        validated = _validate_traits(changes)
        if not validated:
            raise ValueError("At least one personality change is required.")
        if not rationale.strip():
            raise ValueError("A rationale is required.")

        evidence = list(dict.fromkeys(evidence_ids))
        if len(evidence) < 3:
            raise ValueError("At least three distinct experiences are required.")

        identity = self.get_identity(identity_id)

        with self._connect() as conn:
            placeholders = ",".join("?" for _ in evidence)
            rows = conn.execute(
                f"""
                SELECT experience_id FROM experiences
                WHERE identity_id = ? AND experience_id IN ({placeholders})
                """,
                [identity_id, *evidence],
            ).fetchall()

            if len(rows) != len(evidence):
                raise ValueError(
                    "Every evidence item must exist and belong to this identity."
                )

        for trait, target in validated.items():
            current = identity["adaptive"].get(
                trait, identity["baseline"].get(trait, 0.5)
            )
            if abs(target - current) > 0.10:
                raise ValueError(
                    f"Change to {trait} exceeds the 0.10 revision limit."
                )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO personality_revisions
                VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL)
                """,
                (
                    revision_id,
                    identity_id,
                    _json(validated),
                    rationale,
                    _json(evidence),
                    _now(),
                ),
            )

        return self.get_revision(revision_id)

    def get_revision(self, revision_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM personality_revisions
                WHERE revision_id = ?
                """,
                (revision_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown revision: {revision_id}")

        return {
            "revision_id": row["revision_id"],
            "identity_id": row["identity_id"],
            "changes": json.loads(row["changes_json"]),
            "rationale": row["rationale"],
            "evidence_ids": json.loads(row["evidence_ids_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "reviewed_at": row["reviewed_at"],
        }

    def accept_revision(self, revision_id: str) -> dict:
        """Apply a pending revision after rechecking evidence and limits."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            revision = conn.execute(
                """
                SELECT * FROM personality_revisions
                WHERE revision_id = ?
                """,
                (revision_id,),
            ).fetchone()

            if revision is None:
                raise KeyError(f"Unknown revision: {revision_id}")
            if revision["status"] != "pending":
                raise ValueError("Only pending revisions can be accepted.")

            identity = conn.execute(
                """
                SELECT * FROM identities WHERE identity_id = ?
                """,
                (revision["identity_id"],),
            ).fetchone()

            changes = json.loads(revision["changes_json"])
            evidence = json.loads(revision["evidence_ids_json"])

            placeholders = ",".join("?" for _ in evidence)
            valid_evidence = conn.execute(
                f"""
                SELECT COUNT(*) AS total FROM experiences
                WHERE identity_id = ? AND experience_id IN ({placeholders})
                """,
                [revision["identity_id"], *evidence],
            ).fetchone()["total"]

            if valid_evidence != len(evidence) or len(evidence) < 3:
                raise ValueError("Revision evidence is no longer valid.")

            adaptive = json.loads(identity["adaptive_json"])
            baseline = json.loads(identity["baseline_json"])
            for trait, target in changes.items():
                current = adaptive.get(trait, baseline.get(trait, 0.5))
                if abs(target - current) > 0.10:
                    raise ValueError(
                        f"Stale revision exceeds the limit for {trait}."
                    )
                adaptive[trait] = target

            now = _now()
            conn.execute(
                """
                UPDATE identities
                SET adaptive_json = ?, updated_at = ?
                WHERE identity_id = ?
                """,
                (_json(adaptive), now, revision["identity_id"]),
            )
            conn.execute(
                """
                UPDATE personality_revisions
                SET status = 'accepted', reviewed_at = ?
                WHERE revision_id = ?
                """,
                (now, revision_id),
            )

        return self.get_identity(revision["identity_id"])

    def reject_revision(self, revision_id: str) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE personality_revisions
                SET status = 'rejected', reviewed_at = ?
                WHERE revision_id = ? AND status = 'pending'
                """,
                (_now(), revision_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Revision does not exist or is not pending.")

        return self.get_revision(revision_id)
