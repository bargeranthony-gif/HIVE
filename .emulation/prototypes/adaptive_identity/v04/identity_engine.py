from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = 5

DEFAULT_TRAITS = {
    "sociability": 0.50,
    "humor": 0.50,
    "competitiveness": 0.50,
    "formality": 0.50,
    "patience": 0.50,
    "playfulness": 0.50,
}

TRAITS = frozenset(DEFAULT_TRAITS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _validate_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    if len(value) > 200:
        raise ValueError(f"{field} cannot exceed 200 characters.")
    return value.strip()


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


def _validate_descriptors(values: Mapping[str, Any]) -> dict:
    if not isinstance(values, Mapping):
        raise ValueError("Personality descriptors must be a mapping.")

    result = {}

    for key, value in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Descriptor names must be non-empty strings.")

        key = key.strip()

        if len(key) > 100:
            raise ValueError("Descriptor names cannot exceed 100 characters.")

        if isinstance(value, str):
            if len(value) > 2000:
                raise ValueError("Descriptor text cannot exceed 2000 characters.")
            result[key] = value.strip()

        elif isinstance(value, list):
            if not all(isinstance(item, str) for item in value):
                raise ValueError(
                    f"Descriptor list {key!r} must contain only strings."
                )
            if any(len(item) > 500 for item in value):
                raise ValueError(
                    f"Descriptor list {key!r} contains an oversized item."
                )
            result[key] = [item.strip() for item in value]

        else:
            raise ValueError(
                f"Descriptor {key!r} must be text or a list of text."
            )

    return result


class IdentityStore:
    """Isolated v0.4 storage for one continuous HIVE identity."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

        if str(database_path) == ":memory:":
            raise ValueError(
                "Use a file-backed database for this prototype."
            )

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=10.0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self) -> None:
        with self._connect() as conn:
            # Acquire the write lock before inspecting or changing the schema.
            # All initialization and migration DDL is now transactional.
            conn.execute("BEGIN IMMEDIATE")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS haie_schema (
                    version INTEGER NOT NULL
                )
            """)

            row = conn.execute(
                "SELECT version FROM haie_schema LIMIT 1"
            ).fetchone()

            if row is None:
                conn.execute(
                    "INSERT INTO haie_schema (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            elif row["version"] not in (1, 2, 3, 4, 5):
                raise RuntimeError(
                    f"Unsupported HAIE schema version: {row['version']}"
                )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS identities (
                    identity_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS personality_profiles (
                    identity_id TEXT PRIMARY KEY
                        REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    traits_json TEXT NOT NULL,
                    descriptors_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    identity_id TEXT NOT NULL
                        REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    subject_id TEXT NOT NULL,
                    display_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (identity_id, subject_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS social_memories (
                    memory_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_reference TEXT,
                    certainty TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (identity_id, subject_id)
                        REFERENCES relationships(identity_id, subject_id)
                        ON DELETE CASCADE,
                    CHECK (status IN ('active', 'invalidated'))
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_social_memories_subject
                ON social_memories(identity_id, subject_id, status)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS social_memory_revisions (
                    revision_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL
                        REFERENCES social_memories(memory_id)
                        ON DELETE CASCADE,
                    previous_content TEXT NOT NULL,
                    new_content TEXT NOT NULL,
                    previous_source_type TEXT NOT NULL,
                    new_source_type TEXT NOT NULL,
                    previous_source_reference TEXT,
                    new_source_reference TEXT,
                    previous_certainty TEXT NOT NULL,
                    new_certainty TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    revised_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_memory_revisions_memory
                ON social_memory_revisions(memory_id, revised_at)
            """)

            # Complete the original v1-to-v2 migration before applying v3.
            # The surrounding connection context makes all DDL and version
            # changes part of the same SQLite transaction.
            if row is not None and row["version"] == 1:
                conn.execute(
                    "UPDATE haie_schema SET version = 2"
                )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_source_groups (
                    group_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL
                        REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    independence_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (identity_id, group_id),
                    CHECK (
                        independence_status IN (
                            'independent', 'correlated', 'unverified'
                        )
                    )
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_group_revisions (
                    revision_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    revised_at TEXT NOT NULL,
                    FOREIGN KEY (identity_id, group_id)
                        REFERENCES evidence_source_groups(
                            identity_id, group_id
                        )
                        ON DELETE CASCADE,
                    CHECK (
                        previous_status IN (
                            'independent', 'correlated', 'unverified'
                        )
                    ),
                    CHECK (
                        new_status IN (
                            'independent', 'correlated', 'unverified'
                        )
                    )
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_evidence_group_revisions
                ON evidence_group_revisions(
                    identity_id, group_id, revised_at
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_sources (
                    source_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL
                        REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    source_type TEXT NOT NULL,
                    source_reference TEXT,
                    group_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (identity_id, source_id),
                    FOREIGN KEY (identity_id, group_id)
                        REFERENCES evidence_source_groups(
                            identity_id, group_id
                        )
                        ON DELETE RESTRICT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_evidence_sources_group
                ON evidence_sources(identity_id, group_id)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    experience_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL
                        REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    subject_id TEXT,
                    interaction_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    observation TEXT,
                    interpretation TEXT,
                    outcome TEXT,
                    session_id TEXT,
                    source_id TEXT,
                    observed_at TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (identity_id, experience_id),
                    FOREIGN KEY (identity_id, subject_id)
                        REFERENCES relationships(identity_id, subject_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (identity_id, source_id)
                        REFERENCES evidence_sources(identity_id, source_id)
                        ON DELETE RESTRICT,
                    CHECK (confidence >= 0.0 AND confidence <= 1.0)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_experiences_identity_subject
                ON experiences(identity_id, subject_id, observed_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_experiences_source
                ON experiences(identity_id, source_id)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    experience_id TEXT NOT NULL
                        REFERENCES experiences(experience_id)
                        ON DELETE CASCADE,
                    claim_key TEXT NOT NULL,
                    claim_value TEXT NOT NULL,
                    stance TEXT NOT NULL,
                    context_key TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    CHECK (
                        stance IN ('supports', 'refutes', 'uncertain')
                    ),
                    CHECK (confidence >= 0.0 AND confidence <= 1.0)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_claims_experience
                ON claims(experience_id)
            """)

            # Schema v4: owner-reviewed personality revision proposals.
            # Evidence links retain the original claim ID and source-group
            # snapshot even when the live claim is later deleted.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personality_revisions (
                    revision_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL
                        REFERENCES identities(identity_id)
                        ON DELETE CASCADE,
                    trait_key TEXT NOT NULL,
                    interaction_type TEXT NOT NULL DEFAULT '',
                    previous_value REAL NOT NULL,
                    proposed_value REAL NOT NULL,
                    baseline_profile_revision INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    rationale TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    decision_reason TEXT,
                    CHECK (
                        trait_key IN (
                            'sociability',
                            'humor',
                            'competitiveness',
                            'formality',
                            'patience',
                            'playfulness'
                        )
                    ),
                    CHECK (
                        previous_value >= 0.0 AND previous_value <= 1.0
                    ),
                    CHECK (
                        proposed_value >= 0.0 AND proposed_value <= 1.0
                    ),
                    CHECK (previous_value != proposed_value),
                    CHECK (baseline_profile_revision > 0),
                    CHECK (
                        status IN (
                            'pending', 'accepted', 'rejected', 'invalidated'
                        )
                    ),
                    CHECK (
                        (status = 'pending' AND decided_at IS NULL)
                        OR
                        (status != 'pending' AND decided_at IS NOT NULL)
                    )
                )
            """)

            # Schema v5: retain the exact evidence proposition type
            # selected when a personality revision was proposed.
            revision_columns = {
                item["name"]
                for item in conn.execute(
                    "PRAGMA table_info(personality_revisions)"
                ).fetchall()
            }
            if "interaction_type" not in revision_columns:
                conn.execute(
                    """
                    ALTER TABLE personality_revisions
                    ADD COLUMN interaction_type TEXT NOT NULL DEFAULT ''
                    """
                )

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_personality_revisions_identity_status
                ON personality_revisions(
                    identity_id, status, created_at
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS revision_evidence (
                    evidence_link_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL
                        REFERENCES personality_revisions(revision_id)
                        ON DELETE CASCADE,
                    claim_id TEXT
                        REFERENCES claims(claim_id)
                        ON DELETE SET NULL,
                    original_claim_id TEXT NOT NULL,
                    source_group_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (revision_id, original_claim_id),
                    CHECK (
                        claim_id IS NULL
                        OR claim_id = original_claim_id
                    )
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_revision_evidence_revision
                ON revision_evidence(revision_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_revision_evidence_claim
                ON revision_evidence(claim_id)
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS
                    trg_haie_claim_delete_invalidates_revision
                BEFORE DELETE ON claims
                BEGIN
                    UPDATE personality_revisions
                    SET status = 'invalidated',
                        decided_at = strftime(
                            '%Y-%m-%dT%H:%M:%f+00:00', 'now'
                        ),
                        decision_reason =
                            'A supporting evidence claim was deleted.'
                    WHERE status = 'pending'
                      AND revision_id IN (
                          SELECT revision_id
                          FROM revision_evidence
                          WHERE claim_id = OLD.claim_id
                      );
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS
                    trg_haie_group_identity_immutable
                BEFORE UPDATE OF identity_id, group_id
                ON evidence_source_groups
                WHEN NEW.identity_id != OLD.identity_id
                  OR NEW.group_id != OLD.group_id
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'Evidence source group identity is immutable.'
                    );
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS
                    trg_haie_group_status_requires_revision
                BEFORE UPDATE OF independence_status
                ON evidence_source_groups
                WHEN NEW.independence_status != OLD.independence_status
                  AND NOT EXISTS (
                      SELECT 1
                      FROM evidence_group_revisions AS revision
                      WHERE revision.identity_id = OLD.identity_id
                        AND revision.group_id = OLD.group_id
                        AND revision.previous_status =
                            OLD.independence_status
                        AND revision.new_status =
                            NEW.independence_status
                        AND revision.revised_at = NEW.updated_at
                        AND length(trim(revision.reason)) > 0
                  )
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'Evidence status change requires a matching audit revision.'
                    );
                END
            """)

            conn.execute("""
                UPDATE haie_schema SET version = 5
            """)

    def create_identity(
        self,
        identity_id: str,
        display_name: str,
        traits: Mapping[str, Any] | None = None,
        descriptors: Mapping[str, Any] | None = None,
    ) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")
        display_name = _validate_identifier(display_name, "display_name")

        personality_traits = dict(DEFAULT_TRAITS)
        if traits is not None:
            personality_traits.update(_validate_traits(traits))

        personality_descriptors = (
            _validate_descriptors(descriptors)
            if descriptors is not None
            else {}
        )

        now = _now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO identities
                    (identity_id, display_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (identity_id, display_name, now, now),
            )

            conn.execute(
                """
                INSERT INTO personality_profiles
                    (identity_id, traits_json, descriptors_json,
                     revision, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (
                    identity_id,
                    _json(personality_traits),
                    _json(personality_descriptors),
                    now,
                    now,
                ),
            )

        return self.get_identity(identity_id)

    def get_identity(self, identity_id: str) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    i.identity_id,
                    i.display_name,
                    i.created_at AS identity_created_at,
                    i.updated_at AS identity_updated_at,
                    p.traits_json,
                    p.descriptors_json,
                    p.revision,
                    p.created_at AS profile_created_at,
                    p.updated_at AS profile_updated_at
                FROM identities AS i
                JOIN personality_profiles AS p
                    ON p.identity_id = i.identity_id
                WHERE i.identity_id = ?
                """,
                (identity_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown identity: {identity_id}")

        return {
            "identity_id": row["identity_id"],
            "display_name": row["display_name"],
            "created_at": row["identity_created_at"],
            "updated_at": row["identity_updated_at"],
            "personality": {
                "traits": json.loads(row["traits_json"]),
                "descriptors": json.loads(row["descriptors_json"]),
                "revision": row["revision"],
                "created_at": row["profile_created_at"],
                "updated_at": row["profile_updated_at"],
            },
        }

    def record_relationship(
        self,
        identity_id: str,
        subject_id: str,
        display_name: str | None = None,
    ) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")
        subject_id = _validate_identifier(subject_id, "subject_id")

        if display_name is not None:
            display_name = _validate_identifier(
                display_name, "display_name"
            )

        now = _now()

        with self._connect() as conn:
            identity = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if identity is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            existing = conn.execute(
                """
                SELECT display_name
                FROM relationships
                WHERE identity_id = ? AND subject_id = ?
                """,
                (identity_id, subject_id),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO relationships
                        (identity_id, subject_id, display_name,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (identity_id, subject_id, display_name, now, now),
                )
            else:
                conn.execute(
                    """
                    UPDATE relationships
                    SET display_name = COALESCE(?, display_name),
                        updated_at = ?
                    WHERE identity_id = ? AND subject_id = ?
                    """,
                    (display_name, now, identity_id, subject_id),
                )

        return self.get_relationship(identity_id, subject_id)

    def get_relationship(
        self,
        identity_id: str,
        subject_id: str,
    ) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")
        subject_id = _validate_identifier(subject_id, "subject_id")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM relationships
                WHERE identity_id = ? AND subject_id = ?
                """,
                (identity_id, subject_id),
            ).fetchone()

        if row is None:
            raise KeyError(
                f"Unknown relationship: {identity_id}/{subject_id}"
            )

        return dict(row)

    def list_relationships(self, identity_id: str) -> list[dict]:
        identity_id = _validate_identifier(identity_id, "identity_id")

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if exists is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            rows = conn.execute(
                """
                SELECT *
                FROM relationships
                WHERE identity_id = ?
                ORDER BY created_at, subject_id
                """,
                (identity_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def record_social_memory(
        self,
        memory_id: str,
        identity_id: str,
        subject_id: str,
        category: str,
        content: str,
        source_type: str = "unspecified",
        source_reference: str | None = None,
        certainty: str = "uncertain",
    ) -> dict:
        memory_id = _validate_identifier(memory_id, "memory_id")
        identity_id = _validate_identifier(identity_id, "identity_id")
        subject_id = _validate_identifier(subject_id, "subject_id")

        categories = {
            "preference",
            "communication_preference",
            "boundary",
            "shared_experience",
            "conversational_reference",
            "relationship_fact",
        }
        source_types = {
            "direct_statement",
            "observed_interaction",
            "owner_input",
            "external_record",
            "unspecified",
        }
        certainty_levels = {"explicit", "inferred", "uncertain"}

        if not isinstance(category, str) or category not in categories:
            raise ValueError("Invalid social-memory category.")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Memory content must be non-empty text.")

        if len(content) > 4000:
            raise ValueError("Memory content cannot exceed 4000 characters.")

        if not isinstance(source_type, str) or source_type not in source_types:
            raise ValueError("Invalid memory source type.")

        if not isinstance(certainty, str) or certainty not in certainty_levels:
            raise ValueError("Invalid memory certainty.")

        if source_reference is not None:
            if not isinstance(source_reference, str):
                raise ValueError("Source reference must be text.")
            if len(source_reference) > 1000:
                raise ValueError("Source reference is too long.")

        now = _now()

        with self._connect() as conn:
            relationship = conn.execute(
                """
                SELECT 1 FROM relationships
                WHERE identity_id = ? AND subject_id = ?
                """,
                (identity_id, subject_id),
            ).fetchone()

            if relationship is None:
                raise KeyError(
                    "Create the relationship before recording its memories."
                )

            conn.execute(
                """
                INSERT INTO social_memories
                    (memory_id, identity_id, subject_id, category,
                     content, source_type, source_reference, certainty,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    memory_id,
                    identity_id,
                    subject_id,
                    category,
                    content.strip(),
                    source_type,
                    source_reference,
                    certainty,
                    now,
                    now,
                ),
            )

        return self.get_social_memory(memory_id)

    def get_social_memory(self, memory_id: str) -> dict:
        memory_id = _validate_identifier(memory_id, "memory_id")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM social_memories
                WHERE memory_id = ?
                """,
                (memory_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown social memory: {memory_id}")

        return dict(row)

    def list_social_memories(
        self,
        identity_id: str,
        subject_id: str,
        include_inactive: bool = False,
    ) -> list[dict]:
        identity_id = _validate_identifier(identity_id, "identity_id")
        subject_id = _validate_identifier(subject_id, "subject_id")

        if not isinstance(include_inactive, bool):
            raise ValueError("include_inactive must be a boolean.")

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if exists is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            if include_inactive:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM social_memories
                    WHERE identity_id = ? AND subject_id = ?
                    ORDER BY created_at, memory_id
                    """,
                    (identity_id, subject_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM social_memories
                    WHERE identity_id = ?
                      AND subject_id = ?
                      AND status = 'active'
                    ORDER BY created_at, memory_id
                    """,
                    (identity_id, subject_id),
                ).fetchall()

        return [dict(row) for row in rows]

    def correct_social_memory(
        self,
        memory_id: str,
        content: str,
        reason: str,
        source_type: str | None = None,
        source_reference: str | None = None,
        certainty: str | None = None,
    ) -> dict:
        memory_id = _validate_identifier(memory_id, "memory_id")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Corrected content must be non-empty text.")
        if len(content) > 4000:
            raise ValueError("Corrected content cannot exceed 4000 characters.")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("A correction reason is required.")

        source_types = {
            "direct_statement",
            "observed_interaction",
            "owner_input",
            "external_record",
            "unspecified",
        }
        certainty_levels = {"explicit", "inferred", "uncertain"}

        if source_type is not None:
            if not isinstance(source_type, str) or source_type not in source_types:
                raise ValueError("Invalid memory source type.")

        if certainty is not None:
            if not isinstance(certainty, str) or certainty not in certainty_levels:
                raise ValueError("Invalid memory certainty.")

        if source_reference is not None:
            if not isinstance(source_reference, str):
                raise ValueError("Source reference must be text.")
            if len(source_reference) > 1000:
                raise ValueError("Source reference is too long.")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM social_memories
                WHERE memory_id = ? AND status = 'active'
                """,
                (memory_id,),
            ).fetchone()

            if row is None:
                raise KeyError(f"Active social memory not found: {memory_id}")

            new_source_type = source_type or row["source_type"]
            new_source_reference = (
                source_reference
                if source_reference is not None
                else row["source_reference"]
            )
            new_certainty = certainty or row["certainty"]
            now = _now()

            conn.execute(
                """
                INSERT INTO social_memory_revisions (
                    revision_id, memory_id,
                    previous_content, new_content,
                    previous_source_type, new_source_type,
                    previous_source_reference, new_source_reference,
                    previous_certainty, new_certainty,
                    reason, revised_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    memory_id,
                    row["content"],
                    content.strip(),
                    row["source_type"],
                    new_source_type,
                    row["source_reference"],
                    new_source_reference,
                    row["certainty"],
                    new_certainty,
                    reason.strip(),
                    now,
                ),
            )

            conn.execute(
                """
                UPDATE social_memories
                SET content = ?,
                    source_type = ?,
                    source_reference = ?,
                    certainty = ?,
                    updated_at = ?
                WHERE memory_id = ?
                """,
                (
                    content.strip(),
                    new_source_type,
                    new_source_reference,
                    new_certainty,
                    now,
                    memory_id,
                ),
            )

        return self.get_social_memory(memory_id)

    def list_social_memory_revisions(self, memory_id: str) -> list[dict]:
        memory_id = _validate_identifier(memory_id, "memory_id")

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM social_memories WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()

            if exists is None:
                raise KeyError(f"Unknown social memory: {memory_id}")

            rows = conn.execute(
                """
                SELECT *
                FROM social_memory_revisions
                WHERE memory_id = ?
                ORDER BY revised_at, revision_id
                """,
                (memory_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def forget_subject(self, identity_id: str, subject_id: str) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")
        subject_id = _validate_identifier(subject_id, "subject_id")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            exists = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if exists is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            conn.execute(
                """
                UPDATE personality_revisions
                SET status = 'invalidated',
                    decided_at = ?,
                    decision_reason = ?
                WHERE identity_id = ?
                  AND status = 'pending'
                  AND revision_id IN (
                      SELECT DISTINCT re.revision_id
                      FROM revision_evidence AS re
                      JOIN claims AS c
                        ON c.claim_id = re.claim_id
                      JOIN experiences AS e
                        ON e.experience_id = c.experience_id
                      WHERE e.identity_id = ?
                        AND e.subject_id = ?
                  )
                """,
                (
                    _now(),
                    "Supporting subject-specific evidence was deleted when the subject was forgotten.",
                    identity_id,
                    identity_id,
                    subject_id,
                ),
            )

            memory_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM social_memories
                WHERE identity_id = ? AND subject_id = ?
                """,
                (identity_id, subject_id),
            ).fetchone()["count"]

            relationship = conn.execute(
                """
                DELETE FROM relationships
                WHERE identity_id = ? AND subject_id = ?
                """,
                (identity_id, subject_id),
            )

        return {
            "identity_id": identity_id,
            "subject_id": subject_id,
            "memories_deleted": memory_count,
            "relationship_deleted": relationship.rowcount > 0,
        }

    def record_evidence_source_group(
        self,
        identity_id: str,
        group_id: str,
        independence_status: str,
    ) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")
        group_id = _validate_identifier(group_id, "group_id")

        allowed = {"independent", "correlated", "unverified"}
        if (
            not isinstance(independence_status, str)
            or independence_status not in allowed
        ):
            raise ValueError("Invalid evidence independence status.")

        now = _now()

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if exists is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            conn.execute(
                """
                INSERT INTO evidence_source_groups
                    (group_id, identity_id, independence_status,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (group_id, identity_id, independence_status, now, now),
            )

        return self.get_evidence_source_group(identity_id, group_id)

    def get_evidence_source_group(
        self,
        identity_id: str,
        group_id: str,
    ) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")
        group_id = _validate_identifier(group_id, "group_id")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM evidence_source_groups
                WHERE identity_id = ? AND group_id = ?
                """,
                (identity_id, group_id),
            ).fetchone()

        if row is None:
            raise KeyError(
                f"Unknown evidence source group: {identity_id}/{group_id}"
            )

        return dict(row)

    def list_evidence_source_groups(
        self,
        identity_id: str,
    ) -> list[dict]:
        identity_id = _validate_identifier(identity_id, "identity_id")

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if exists is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            rows = conn.execute(
                """
                SELECT *
                FROM evidence_source_groups
                WHERE identity_id = ?
                ORDER BY created_at, group_id
                """,
                (identity_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def revise_evidence_source_group(
        self,
        identity_id: str,
        group_id: str,
        new_status: str,
        reason: str,
    ) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")
        group_id = _validate_identifier(group_id, "group_id")

        allowed = {"independent", "correlated", "unverified"}
        if not isinstance(new_status, str) or new_status not in allowed:
            raise ValueError("Invalid evidence independence status.")

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("A non-empty revision reason is required.")

        now = _now()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            current = conn.execute(
                """
                SELECT independence_status
                FROM evidence_source_groups
                WHERE identity_id = ? AND group_id = ?
                """,
                (identity_id, group_id),
            ).fetchone()

            if current is None:
                raise KeyError(
                    f"Unknown evidence source group: {identity_id}/{group_id}"
                )

            previous_status = current["independence_status"]

            if previous_status != new_status:
                conn.execute(
                    """
                    INSERT INTO evidence_group_revisions
                        (revision_id, identity_id, group_id,
                         previous_status, new_status, reason, revised_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        identity_id,
                        group_id,
                        previous_status,
                        new_status,
                        reason.strip(),
                        now,
                    ),
                )

                if new_status != "independent":
                    conn.execute(
                        """
                        UPDATE personality_revisions
                        SET status = 'invalidated',
                            decided_at = ?,
                            decision_reason = ?
                        WHERE identity_id = ?
                          AND status = 'pending'
                          AND revision_id IN (
                              SELECT revision_id
                              FROM revision_evidence
                              WHERE source_group_id = ?
                          )
                        """,
                        (
                            now,
                            "A supporting evidence source group lost independent status.",
                            identity_id,
                            group_id,
                        ),
                    )

                conn.execute(
                    """
                    UPDATE evidence_source_groups
                    SET independence_status = ?, updated_at = ?
                    WHERE identity_id = ? AND group_id = ?
                    """,
                    (new_status, now, identity_id, group_id),
                )

        return self.get_evidence_source_group(identity_id, group_id)

    def list_evidence_group_revisions(
        self,
        identity_id: str,
        group_id: str,
    ) -> list[dict]:
        identity_id = _validate_identifier(identity_id, "identity_id")
        group_id = _validate_identifier(group_id, "group_id")

        self.get_evidence_source_group(identity_id, group_id)

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM evidence_group_revisions
                WHERE identity_id = ? AND group_id = ?
                ORDER BY revised_at, revision_id
                """,
                (identity_id, group_id),
            ).fetchall()

        return [dict(row) for row in rows]

    def record_evidence_source(
        self,
        source_id: str,
        identity_id: str,
        source_type: str,
        source_reference: str | None = None,
        group_id: str | None = None,
    ) -> dict:
        source_id = _validate_identifier(source_id, "source_id")
        identity_id = _validate_identifier(identity_id, "identity_id")
        source_type = _validate_identifier(source_type, "source_type")

        if source_reference is not None:
            if not isinstance(source_reference, str):
                raise ValueError("source_reference must be text or None.")

        if group_id is not None:
            group_id = _validate_identifier(group_id, "group_id")

        now = _now()

        with self._connect() as conn:
            identity = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if identity is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            if group_id is not None:
                group = conn.execute(
                    """
                    SELECT 1
                    FROM evidence_source_groups
                    WHERE identity_id = ? AND group_id = ?
                    """,
                    (identity_id, group_id),
                ).fetchone()

                if group is None:
                    raise KeyError(
                        f"Unknown evidence source group: {identity_id}/{group_id}"
                    )

            conn.execute(
                """
                INSERT INTO evidence_sources
                    (source_id, identity_id, source_type,
                     source_reference, group_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    identity_id,
                    source_type,
                    source_reference,
                    group_id,
                    now,
                    now,
                ),
            )

            row = conn.execute(
                "SELECT * FROM evidence_sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()

        return dict(row)

    def get_evidence_source(
        self,
        identity_id: str,
        source_id: str,
    ) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")
        source_id = _validate_identifier(source_id, "source_id")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM evidence_sources
                WHERE identity_id = ? AND source_id = ?
                """,
                (identity_id, source_id),
            ).fetchone()

        if row is None:
            raise KeyError(
                f"Unknown evidence source: {identity_id}/{source_id}"
            )

        return dict(row)

    def record_experience(
        self,
        experience_id: str,
        identity_id: str,
        interaction_type: str,
        summary: str,
        subject_id: str | None = None,
        observation: str | None = None,
        interpretation: str | None = None,
        outcome: str | None = None,
        session_id: str | None = None,
        source_id: str | None = None,
        observed_at: str | None = None,
        confidence: float = 1.0,
    ) -> dict:
        experience_id = _validate_identifier(
            experience_id, "experience_id"
        )
        identity_id = _validate_identifier(identity_id, "identity_id")
        interaction_type = _validate_identifier(
            interaction_type, "interaction_type"
        )

        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("summary must be non-empty text.")

        optional_text = {
            "subject_id": subject_id,
            "observation": observation,
            "interpretation": interpretation,
            "outcome": outcome,
            "session_id": session_id,
            "source_id": source_id,
            "observed_at": observed_at,
        }

        for field, value in optional_text.items():
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{field} must be text or None.")

        if subject_id is not None:
            subject_id = _validate_identifier(subject_id, "subject_id")

        if source_id is not None:
            source_id = _validate_identifier(source_id, "source_id")

        if isinstance(confidence, bool) or not isinstance(
            confidence, (int, float)
        ):
            raise ValueError("confidence must be numeric between 0 and 1.")

        confidence = float(confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be numeric between 0 and 1.")

        observed_at = observed_at or _now()
        now = _now()

        with self._connect() as conn:
            identity = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if identity is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            if subject_id is not None:
                relationship = conn.execute(
                    """
                    SELECT 1 FROM relationships
                    WHERE identity_id = ? AND subject_id = ?
                    """,
                    (identity_id, subject_id),
                ).fetchone()

                if relationship is None:
                    raise KeyError(
                        f"Unknown relationship: {identity_id}/{subject_id}"
                    )

            if source_id is not None:
                source = conn.execute(
                    """
                    SELECT 1 FROM evidence_sources
                    WHERE identity_id = ? AND source_id = ?
                    """,
                    (identity_id, source_id),
                ).fetchone()

                if source is None:
                    raise KeyError(
                        f"Unknown evidence source: {identity_id}/{source_id}"
                    )

            conn.execute(
                """
                INSERT INTO experiences
                    (experience_id, identity_id, subject_id,
                     interaction_type, summary, observation,
                     interpretation, outcome, session_id, source_id,
                     observed_at, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experience_id,
                    identity_id,
                    subject_id,
                    interaction_type,
                    summary,
                    observation,
                    interpretation,
                    outcome,
                    session_id,
                    source_id,
                    observed_at,
                    confidence,
                    now,
                ),
            )

            row = conn.execute(
                """
                SELECT * FROM experiences
                WHERE experience_id = ?
                """,
                (experience_id,),
            ).fetchone()

        return dict(row)

    def get_experience(self, experience_id: str) -> dict:
        experience_id = _validate_identifier(
            experience_id, "experience_id"
        )

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM experiences WHERE experience_id = ?",
                (experience_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown experience: {experience_id}")

        return dict(row)

    def list_experiences(
        self,
        identity_id: str,
        subject_id: str | None = None,
    ) -> list[dict]:
        identity_id = _validate_identifier(identity_id, "identity_id")

        if subject_id is not None:
            subject_id = _validate_identifier(subject_id, "subject_id")

        with self._connect() as conn:
            identity = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if identity is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            if subject_id is None:
                rows = conn.execute(
                    """
                    SELECT * FROM experiences
                    WHERE identity_id = ?
                    ORDER BY observed_at, experience_id
                    """,
                    (identity_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM experiences
                    WHERE identity_id = ? AND subject_id = ?
                    ORDER BY observed_at, experience_id
                    """,
                    (identity_id, subject_id),
                ).fetchall()

        return [dict(row) for row in rows]

    def record_claim(
        self,
        claim_id: str,
        experience_id: str,
        claim_key: str,
        claim_value: str,
        stance: str,
        context_key: str = "",
        confidence: float = 1.0,
    ) -> dict:
        claim_id = _validate_identifier(claim_id, "claim_id")
        experience_id = _validate_identifier(
            experience_id, "experience_id"
        )

        # Validate text without normalizing it. Original wording is retained;
        # normalization belongs to the evaluator, not the storage layer.
        for field, value in (
            ("claim_key", claim_key),
            ("claim_value", claim_value),
            ("context_key", context_key),
        ):
            if not isinstance(value, str):
                raise ValueError(f"{field} must be text.")
            if field != "context_key" and not value.strip():
                raise ValueError(f"{field} must be non-empty text.")

        allowed_stances = {"supports", "refutes", "uncertain"}
        if not isinstance(stance, str) or stance not in allowed_stances:
            raise ValueError("Invalid claim stance.")

        if isinstance(confidence, bool) or not isinstance(
            confidence, (int, float)
        ):
            raise ValueError("confidence must be numeric between 0 and 1.")

        confidence = float(confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be numeric between 0 and 1.")

        now = _now()

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM experiences WHERE experience_id = ?",
                (experience_id,),
            ).fetchone()

            if exists is None:
                raise KeyError(f"Unknown experience: {experience_id}")

            conn.execute(
                """
                INSERT INTO claims
                    (claim_id, experience_id, claim_key, claim_value,
                     stance, context_key, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    experience_id,
                    claim_key,
                    claim_value,
                    stance,
                    context_key,
                    confidence,
                    now,
                ),
            )

            row = conn.execute(
                "SELECT * FROM claims WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()

        return dict(row)

    def get_claim(self, claim_id: str) -> dict:
        claim_id = _validate_identifier(claim_id, "claim_id")

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM claims WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown claim: {claim_id}")

        return dict(row)

    def list_claims(self, experience_id: str) -> list[dict]:
        experience_id = _validate_identifier(
            experience_id, "experience_id"
        )

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM experiences WHERE experience_id = ?",
                (experience_id,),
            ).fetchone()

            if exists is None:
                raise KeyError(f"Unknown experience: {experience_id}")

            rows = conn.execute(
                """
                SELECT * FROM claims
                WHERE experience_id = ?
                ORDER BY created_at, claim_id
                """,
                (experience_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def propose_personality_revision(
        self,
        revision_id: str,
        identity_id: str,
        trait_key: str,
        proposed_value: float,
        rationale: str,
    ) -> dict:
        # Create a pending, evidence-backed proposal without changing identity.
        revision_id = _validate_identifier(revision_id, "revision_id")
        identity_id = _validate_identifier(identity_id, "identity_id")

        if not isinstance(trait_key, str) or trait_key not in TRAITS:
            raise ValueError("Unknown personality trait.")

        if isinstance(proposed_value, bool) or not isinstance(
            proposed_value, (int, float)
        ):
            raise ValueError("proposed_value must be numeric between 0 and 1.")

        proposed_value = float(proposed_value)
        if not 0.0 <= proposed_value <= 1.0:
            raise ValueError("proposed_value must be between 0 and 1.")

        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("rationale must be non-empty text.")
        rationale = rationale.strip()
        if len(rationale) > 2000:
            raise ValueError("rationale cannot exceed 2000 characters.")

        claim_key = f"personality_trait:{trait_key}:direction"
        now = _now()

        with self._connect() as conn:
            # Hold the write lock while checking evidence and saving the
            # proposal. This prevents evidence/profile changes between them.
            conn.execute("BEGIN IMMEDIATE")

            profile = conn.execute(
                """
                SELECT traits_json, revision
                FROM personality_profiles
                WHERE identity_id = ?
                """,
                (identity_id,),
            ).fetchone()

            if profile is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            current_traits = json.loads(profile["traits_json"])
            previous_value = float(current_traits[trait_key])
            baseline_revision = int(profile["revision"])

            change = proposed_value - previous_value
            if change == 0:
                raise ValueError("Proposed value must change the trait.")
            if abs(change) > 0.10:
                raise ValueError(
                    "A personality revision cannot change a trait by more than 0.10."
                )

            target_direction = "increase" if change > 0 else "decrease"
            opposite_direction = (
                "decrease" if target_direction == "increase" else "increase"
            )

            rows = conn.execute(
                """
                SELECT
                    c.claim_id,
                    c.claim_value,
                    c.stance,
                    e.experience_id,
                    e.interaction_type,
                    s.group_id,
                    g.independence_status
                FROM claims AS c
                JOIN experiences AS e
                    ON e.experience_id = c.experience_id
                LEFT JOIN evidence_sources AS s
                    ON s.identity_id = e.identity_id
                   AND s.source_id = e.source_id
                LEFT JOIN evidence_source_groups AS g
                    ON g.identity_id = s.identity_id
                   AND g.group_id = s.group_id
                WHERE e.identity_id = ?
                  AND e.subject_id IS NULL
                  AND c.claim_key = ?
                  AND c.context_key = 'global_personality'
                ORDER BY e.interaction_type, c.claim_id
                """,
                (identity_id, claim_key),
            ).fetchall()

            if not rows:
                raise ValueError(
                    "No global-personality evidence exists for this trait."
                )

            by_interaction = {}
            for row in rows:
                value = row["claim_value"].strip().casefold()
                stance = row["stance"]

                if value not in {"increase", "decrease"}:
                    raise ValueError(
                        "Trait-direction evidence contains an unsupported value."
                    )

                if stance == "uncertain":
                    continue

                if stance == "supports":
                    effective_direction = value
                elif stance == "refutes":
                    effective_direction = (
                        "decrease" if value == "increase" else "increase"
                    )
                else:
                    raise ValueError(
                        "Trait-direction evidence contains an invalid stance."
                    )

                interaction = row["interaction_type"].strip().casefold()
                by_interaction.setdefault(interaction, []).append(
                    (row, effective_direction)
                )

            eligible_sets = []

            for interaction, records in sorted(by_interaction.items()):
                # Opposing evidence blocks a proposal, including evidence
                # that lacks provenance or comes from a non-independent group.
                if any(
                    direction == opposite_direction
                    for _, direction in records
                ):
                    raise ValueError(
                        "Opposing global-personality evidence blocks this proposal."
                    )

                supporting_groups = {
                    row["group_id"]
                    for row, direction in records
                    if direction == target_direction
                    and row["group_id"] is not None
                    and row["independence_status"] == "independent"
                }

                if len(supporting_groups) >= 2:
                    eligible_sets.append(
                        (len(supporting_groups), interaction, records)
                    )

            if not eligible_sets:
                raise ValueError(
                    "At least two independent source groups must support "
                    "the proposed direction within one interaction type."
                )

            # Select one qualifying proposition deterministically. The
            # evaluator treats different interaction types as separate
            # propositions, so evidence is not pooled across them.
            _, selected_interaction, selected_records = sorted(
                eligible_sets,
                key=lambda item: (-item[0], item[1]),
            )[0]

            supporting_claims = []
            supporting_groups = set()

            for row, direction in selected_records:
                if direction != target_direction:
                    continue
                if (
                    row["group_id"] is None
                    or row["independence_status"] != "independent"
                ):
                    continue

                supporting_claims.append(row)
                supporting_groups.add(row["group_id"])

            if len(supporting_groups) < 2:
                raise ValueError(
                    "Insufficient independent evidence for this proposal."
                )

            conn.execute(
                """
                INSERT INTO personality_revisions (
                    revision_id, identity_id, trait_key,
                    interaction_type, previous_value, proposed_value,
                    baseline_profile_revision, status,
                    rationale, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    revision_id,
                    identity_id,
                    trait_key,
                    selected_interaction,
                    previous_value,
                    proposed_value,
                    baseline_revision,
                    rationale,
                    now,
                ),
            )

            for row in supporting_claims:
                conn.execute(
                    """
                    INSERT INTO revision_evidence (
                        evidence_link_id, revision_id, claim_id,
                        original_claim_id, source_group_id, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        revision_id,
                        row["claim_id"],
                        row["claim_id"],
                        row["group_id"],
                        now,
                    ),
                )

            revision = conn.execute(
                """
                SELECT * FROM personality_revisions
                WHERE revision_id = ?
                """,
                (revision_id,),
            ).fetchone()

            evidence = conn.execute(
                """
                SELECT *
                FROM revision_evidence
                WHERE revision_id = ?
                ORDER BY original_claim_id
                """,
                (revision_id,),
            ).fetchall()

        result = dict(revision)
        result["evidence"] = [dict(row) for row in evidence]
        result["evidence_interaction_type"] = selected_interaction
        result["independent_source_group_count"] = len(supporting_groups)
        return result


    def get_personality_revision(self, revision_id: str) -> dict:
        revision_id = _validate_identifier(revision_id, "revision_id")

        with self._connect() as conn:
            # Keep revision, evidence links, and live evidence in one
            # consistent SQLite read snapshot.
            conn.execute("BEGIN")

            row = conn.execute(
                "SELECT * FROM personality_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()

            if row is None:
                raise KeyError(f"Unknown personality revision: {revision_id}")

            evidence = conn.execute(
                """
                SELECT * FROM revision_evidence
                WHERE revision_id = ?
                ORDER BY original_claim_id
                """,
                (revision_id,),
            ).fetchall()

            live_evidence = conn.execute(
                """
                SELECT
                    re.claim_id,
                    re.original_claim_id,
                    re.source_group_id AS recorded_group_id,
                    c.claim_id AS live_claim_id,
                    c.claim_key,
                    c.claim_value,
                    c.stance,
                    c.context_key,
                    e.identity_id,
                    e.subject_id,
                    e.interaction_type,
                    s.group_id AS live_group_id,
                    g.independence_status
                FROM revision_evidence AS re
                LEFT JOIN claims AS c
                    ON c.claim_id = re.claim_id
                LEFT JOIN experiences AS e
                    ON e.experience_id = c.experience_id
                LEFT JOIN evidence_sources AS s
                    ON s.identity_id = e.identity_id
                   AND s.source_id = e.source_id
                LEFT JOIN evidence_source_groups AS g
                    ON g.identity_id = s.identity_id
                   AND g.group_id = s.group_id
                WHERE re.revision_id = ?
                """,
                (revision_id,),
            ).fetchall()

            revision = dict(row)
            evidence_items = [dict(item) for item in evidence]

            direction = (
                "increase"
                if revision["proposed_value"] > revision["previous_value"]
                else "decrease"
            )
            opposite_direction = (
                "decrease" if direction == "increase" else "increase"
            )
            expected_claim_key = (
                f"personality_trait:{revision['trait_key']}:direction"
            )
            expected_interaction = revision["interaction_type"].strip().casefold()

            valid_groups = set()

            for item in live_evidence:
                if (
                    item["claim_id"] is None
                    or item["live_claim_id"] != item["original_claim_id"]
                    or item["identity_id"] != revision["identity_id"]
                    or item["subject_id"] is not None
                    or item["claim_key"] != expected_claim_key
                    or item["context_key"] != "global_personality"
                    or item["interaction_type"].strip().casefold()
                        != expected_interaction
                    or item["live_group_id"] != item["recorded_group_id"]
                    or item["independence_status"] != "independent"
                ):
                    continue

                value = item["claim_value"].strip().casefold()
                stance = item["stance"]

                if stance == "supports":
                    effective_direction = value
                elif stance == "refutes":
                    effective_direction = (
                        opposite_direction
                        if value == direction
                        else direction
                    ) if value in {"increase", "decrease"} else None
                else:
                    effective_direction = None

                if effective_direction == direction:
                    valid_groups.add(item["live_group_id"])

        revision["evidence"] = evidence_items
        revision["independent_source_group_count"] = len(valid_groups)
        return revision


    def list_personality_revisions(
        self, identity_id: str, status: str | None = None
    ) -> list[dict]:
        identity_id = _validate_identifier(identity_id, "identity_id")
        allowed = {"pending", "accepted", "rejected", "invalidated"}
        if status is not None and (
            not isinstance(status, str) or status not in allowed
        ):
            raise ValueError("Invalid personality revision status.")

        with self._connect() as conn:
            identity = conn.execute(
                "SELECT 1 FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()
            if identity is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            if status is None:
                rows = conn.execute(
                    """
                    SELECT revision_id FROM personality_revisions
                    WHERE identity_id = ?
                    ORDER BY created_at, revision_id
                    """,
                    (identity_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT revision_id FROM personality_revisions
                    WHERE identity_id = ? AND status = ?
                    ORDER BY created_at, revision_id
                    """,
                    (identity_id, status),
                ).fetchall()

        return [
            self.get_personality_revision(row["revision_id"])
            for row in rows
        ]

    def accept_personality_revision(
        self, revision_id: str, decision_reason: str
    ) -> dict:
        """Record approval only after atomic revalidation of proposal evidence.

        This records an approval event, not the identity of an authenticated
        owner. Authorization must be enforced by the HIVE control layer.
        """
        revision_id = _validate_identifier(revision_id, "revision_id")
        if not isinstance(decision_reason, str) or not decision_reason.strip():
            raise ValueError("A non-empty decision_reason is required.")
        decision_reason = decision_reason.strip()
        if len(decision_reason) > 2000:
            raise ValueError("decision_reason cannot exceed 2000 characters.")

        now = _now()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            revision = conn.execute(
                "SELECT * FROM personality_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()

            if revision is None:
                raise KeyError(f"Unknown personality revision: {revision_id}")
            if revision["status"] != "pending":
                raise ValueError(
                    f"Personality revision is not pending: {revision['status']}"
                )

            def invalidate(reason):
                conn.execute(
                    """
                    UPDATE personality_revisions
                    SET status = 'invalidated',
                        decided_at = ?, decision_reason = ?
                    WHERE revision_id = ? AND status = 'pending'
                    """,
                    (now, reason, revision_id),
                )

            profile = conn.execute(
                """
                SELECT traits_json, revision
                FROM personality_profiles
                WHERE identity_id = ?
                """,
                (revision["identity_id"],),
            ).fetchone()

            reason = None

            if profile is None:
                reason = "The identity profile no longer exists."
            elif profile["revision"] != revision["baseline_profile_revision"]:
                reason = "The personality profile changed after this proposal was created."
            elif not revision["interaction_type"]:
                reason = "Legacy proposal has no recorded interaction type; evidence cannot be revalidated."

            if reason is None:
                traits = json.loads(profile["traits_json"])
                trait = revision["trait_key"]
                previous = float(revision["previous_value"])
                proposed = float(revision["proposed_value"])
                delta = proposed - previous
                direction = "increase" if delta > 0 else "decrease"
                current = float(traits.get(trait, -1))

                if current != previous:
                    reason = "The target trait no longer matches the proposal baseline."
                elif delta == 0 or abs(delta) > 0.10:
                    reason = "The proposed trait change exceeds the permitted revision limit."
                elif not 0.0 <= proposed <= 1.0:
                    reason = "The proposed trait value is outside the valid range."

            if reason is None:
                claim_key = f"personality_trait:{trait}:direction"

                links = conn.execute(
                    """
                    SELECT
                        re.claim_id, re.original_claim_id,
                        re.source_group_id AS recorded_group_id,
                        c.claim_id AS live_claim_id,
                        c.claim_key, c.claim_value, c.stance, c.context_key,
                        e.identity_id, e.subject_id, e.interaction_type,
                        s.group_id AS live_group_id,
                        g.independence_status
                    FROM revision_evidence AS re
                    LEFT JOIN claims AS c ON c.claim_id = re.claim_id
                    LEFT JOIN experiences AS e
                        ON e.experience_id = c.experience_id
                    LEFT JOIN evidence_sources AS s
                        ON s.identity_id = e.identity_id
                       AND s.source_id = e.source_id
                    LEFT JOIN evidence_source_groups AS g
                        ON g.identity_id = s.identity_id
                       AND g.group_id = s.group_id
                    WHERE re.revision_id = ?
                    """,
                    (revision_id,),
                ).fetchall()

                groups = set()

                if not links:
                    reason = "The proposal has no retained evidence links."

                for link in links:
                    if (
                        link["claim_id"] is None
                        or link["live_claim_id"] != link["original_claim_id"]
                    ):
                        reason = "A supporting evidence claim was deleted."
                        break

                    if (
                        link["identity_id"] != revision["identity_id"]
                        or link["subject_id"] is not None
                        or link["claim_key"] != claim_key
                        or link["context_key"] != "global_personality"
                        or link["interaction_type"].strip().casefold()
                            != revision["interaction_type"].strip().casefold()
                        or link["live_group_id"] != link["recorded_group_id"]
                        or link["independence_status"] != "independent"
                    ):
                        reason = "A supporting evidence source no longer meets the proposal requirements."
                        break

                    value = link["claim_value"].strip().casefold()
                    stance = link["stance"]

                    if value not in {"increase", "decrease"} or stance not in {
                        "supports", "refutes"
                    }:
                        reason = "A supporting evidence claim is no longer valid directional evidence."
                        break

                    effective = value if stance == "supports" else (
                        "decrease" if value == "increase" else "increase"
                    )

                    if effective != direction:
                        reason = "A linked claim no longer supports the proposed direction."
                        break

                    groups.add(link["live_group_id"])

                if reason is None and len(groups) < 2:
                    reason = "Fewer than two independent source groups remain."

            # Check all current evidence for the same proposition, including
            # evidence added after the proposal was created.
            if reason is None:
                current_claims = conn.execute(
                    """
                    SELECT c.claim_value, c.stance
                    FROM claims AS c
                    JOIN experiences AS e
                        ON e.experience_id = c.experience_id
                    WHERE e.identity_id = ?
                      AND e.subject_id IS NULL
                      AND c.claim_key = ?
                      AND c.context_key = 'global_personality'
                      AND lower(trim(e.interaction_type)) = lower(trim(?))
                    """,
                    (
                        revision["identity_id"],
                        claim_key,
                        revision["interaction_type"],
                    ),
                ).fetchall()

                for claim in current_claims:
                    value = claim["claim_value"].strip().casefold()
                    stance = claim["stance"]

                    if value not in {"increase", "decrease"}:
                        reason = "The current proposition contains unsupported directional evidence."
                        break

                    if stance == "uncertain":
                        continue
                    if stance not in {"supports", "refutes"}:
                        reason = "The current proposition contains an invalid evidence stance."
                        break

                    effective = value if stance == "supports" else (
                        "decrease" if value == "increase" else "increase"
                    )

                    if effective != direction:
                        reason = "New opposing evidence now conflicts with this proposal."
                        break

            if reason is not None:
                invalidate(reason)
            else:
                traits[trait] = proposed

                conn.execute(
                    """
                    UPDATE personality_profiles
                    SET traits_json = ?, revision = revision + 1,
                        updated_at = ?
                    WHERE identity_id = ?
                    """,
                    (_json(traits), now, revision["identity_id"]),
                )

                conn.execute(
                    "UPDATE identities SET updated_at = ? WHERE identity_id = ?",
                    (now, revision["identity_id"]),
                )

                conn.execute(
                    """
                    UPDATE personality_revisions
                    SET status = 'accepted',
                        decided_at = ?, decision_reason = ?
                    WHERE revision_id = ? AND status = 'pending'
                    """,
                    (now, decision_reason, revision_id),
                )

        return self.get_personality_revision(revision_id)

    def reject_personality_revision(
        self, revision_id: str, decision_reason: str
    ) -> dict:
        revision_id = _validate_identifier(revision_id, "revision_id")
        if not isinstance(decision_reason, str) or not decision_reason.strip():
            raise ValueError("A non-empty decision_reason is required.")
        decision_reason = decision_reason.strip()
        if len(decision_reason) > 2000:
            raise ValueError("decision_reason cannot exceed 2000 characters.")

        now = _now()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            revision = conn.execute(
                "SELECT status FROM personality_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()

            if revision is None:
                raise KeyError(f"Unknown personality revision: {revision_id}")
            if revision["status"] != "pending":
                raise ValueError(
                    f"Personality revision is not pending: {revision['status']}"
                )

            conn.execute(
                """
                UPDATE personality_revisions
                SET status = 'rejected',
                    decided_at = ?, decision_reason = ?
                WHERE revision_id = ? AND status = 'pending'
                """,
                (now, decision_reason, revision_id),
            )

        return self.get_personality_revision(revision_id)

    def update_personality_profile(
        self,
        identity_id: str,
        traits: Mapping[str, Any] | None = None,
        descriptors: Mapping[str, Any] | None = None,
    ) -> dict:
        identity_id = _validate_identifier(identity_id, "identity_id")

        if traits is None and descriptors is None:
            raise ValueError("At least one profile update is required.")

        validated_traits = (
            _validate_traits(traits) if traits is not None else None
        )
        validated_descriptors = (
            _validate_descriptors(descriptors)
            if descriptors is not None
            else None
        )

        now = _now()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute(
                """
                SELECT traits_json, descriptors_json
                FROM personality_profiles
                WHERE identity_id = ?
                """,
                (identity_id,),
            ).fetchone()

            if row is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            current_traits = json.loads(row["traits_json"])
            current_descriptors = json.loads(row["descriptors_json"])

            conn.execute(
                """
                UPDATE personality_revisions
                SET status = 'invalidated',
                    decided_at = ?,
                    decision_reason = ?
                WHERE identity_id = ? AND status = 'pending'
                """,
                (
                    now,
                    "The personality profile changed after this proposal was created.",
                    identity_id,
                ),
            )

            if validated_traits is not None:
                current_traits.update(validated_traits)

            if validated_descriptors is not None:
                current_descriptors.update(validated_descriptors)

            conn.execute(
                """
                UPDATE personality_profiles
                SET traits_json = ?,
                    descriptors_json = ?,
                    revision = revision + 1,
                    updated_at = ?
                WHERE identity_id = ?
                """,
                (
                    _json(current_traits),
                    _json(current_descriptors),
                    now,
                    identity_id,
                ),
            )

            conn.execute(
                """
                UPDATE identities
                SET updated_at = ?
                WHERE identity_id = ?
                """,
                (now, identity_id),
            )

        return self.get_identity(identity_id)
