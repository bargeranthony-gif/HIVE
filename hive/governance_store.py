from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid

from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .config import database_path
from .db import connect
from .governance import Approval, Decision, ExecutionResult, ActionRequest, SourceRecord
from .plan_identity import PlanIdentity


MIGRATION_ID = "001_governance_store"
PLAN_MIGRATION_ID = "002_plan_persistence"
LIFECYCLE_MIGRATION_ID = "003_lifecycle_relationships"


GOVERNANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS governance_policies (
    policy_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    policy_hash TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (policy_id, policy_version)
);

CREATE TABLE IF NOT EXISTS action_approvals (
    approval_id TEXT PRIMARY KEY,
    approver_id TEXT NOT NULL,
    action_digest TEXT NOT NULL,
    scope TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1)),
    issuer_type TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_action_approvals_digest
    ON action_approvals(action_digest);

CREATE TABLE IF NOT EXISTS governance_decisions (
    decision_id TEXT PRIMARY KEY,
    disposition TEXT NOT NULL,
    approval_state TEXT NOT NULL,
    action_digest TEXT NOT NULL,
    rationale TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    source_snapshot_json TEXT NOT NULL,
    request_snapshot_json TEXT NOT NULL,
    approval_id TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_governance_decisions_digest
    ON governance_decisions(action_digest);

CREATE TABLE IF NOT EXISTS execution_records (
    result_id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    resulting_status TEXT NOT NULL,
    side_effect_count INTEGER NOT NULL,
    replayed INTEGER NOT NULL CHECK (replayed IN (0, 1)),
    execution_type TEXT NOT NULL DEFAULT 'MOCK',
    action_digest TEXT,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit events are append-only');
END;
"""


PLAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    plan_id TEXT PRIMARY KEY,
    repository_id INTEGER NOT NULL
        REFERENCES repositories(id) ON DELETE RESTRICT,
    identity_digest TEXT NOT NULL
        CHECK (length(identity_digest) = 64),
    identity_schema_version INTEGER NOT NULL
        CHECK (identity_schema_version > 0),
    canonical_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (
            status IN (
                'draft',
                'approved',
                'executing',
                'completed',
                'failed',
                'cancelled',
                'stale'
            )
        ),
    created_at TEXT NOT NULL,
    UNIQUE (repository_id, identity_digest)
);

CREATE INDEX IF NOT EXISTS idx_plans_repository_status
    ON plans(repository_id, status);

CREATE TRIGGER IF NOT EXISTS plans_identity_no_update
BEFORE UPDATE OF
    plan_id,
    repository_id,
    identity_digest,
    identity_schema_version,
    canonical_json,
    created_at
ON plans
BEGIN
    SELECT RAISE(ABORT, 'plan identity fields are immutable');
END;

CREATE TRIGGER IF NOT EXISTS plans_no_delete
BEFORE DELETE ON plans
BEGIN
    SELECT RAISE(ABORT, 'stored plans cannot be deleted');
END;
"""


LIFECYCLE_SCHEMA = """
ALTER TABLE action_approvals
    ADD COLUMN plan_id TEXT REFERENCES plans(plan_id) ON DELETE RESTRICT;

ALTER TABLE governance_decisions
    ADD COLUMN plan_id TEXT REFERENCES plans(plan_id) ON DELETE RESTRICT;

ALTER TABLE execution_records
    ADD COLUMN plan_id TEXT REFERENCES plans(plan_id) ON DELETE RESTRICT;

ALTER TABLE execution_records
    ADD COLUMN decision_id TEXT
    REFERENCES governance_decisions(decision_id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_action_approvals_plan
    ON action_approvals(plan_id);

CREATE INDEX IF NOT EXISTS idx_governance_decisions_plan
    ON governance_decisions(plan_id);

CREATE INDEX IF NOT EXISTS idx_execution_records_plan
    ON execution_records(plan_id);

CREATE INDEX IF NOT EXISTS idx_execution_records_decision
    ON execution_records(decision_id);
"""


def _apply_migration(
    conn: sqlite3.Connection,
    migration_id: str,
    schema: str,
) -> None:
    """Apply one schema migration and record it atomically."""
    conn.execute("BEGIN IMMEDIATE")

    try:
        existing = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE migration_id = ?",
            (migration_id,),
        ).fetchone()

        if existing is not None:
            conn.commit()
            return

        # Execute complete SQL statements individually so DDL remains
        # inside the transaction. This also handles trigger bodies.
        statement = ""
        for line in schema.splitlines():
            statement += line + "\n"

            if sqlite3.complete_statement(statement):
                if statement.strip():
                    conn.execute(statement)
                statement = ""

        if statement.strip():
            raise ValueError(
                f"Incomplete SQL statement in migration: {migration_id}"
            )

        conn.execute(
            """
            INSERT INTO schema_migrations (migration_id, applied_at)
            VALUES (?, CURRENT_TIMESTAMP)
            """,
            (migration_id,),
        )

        conn.commit()

    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _audit_hash(
    event_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload_json: str,
    occurred_at: str,
    previous_hash: str,
) -> str:
    envelope = {
        "event_id": event_id,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload_json": payload_json,
        "occurred_at": occurred_at,
        "previous_hash": previous_hash,
    }
    return hashlib.sha256(_json(envelope).encode("utf-8")).hexdigest()


def _open(path: Path | None = None) -> sqlite3.Connection:
    return connect(path or database_path())


def initialize_governance(path: Path | None = None) -> Path:
    """Apply governance and plan migrations without replacing existing data."""
    db_path = path or database_path()

    with closing(_open(db_path)) as conn:
        # The migration ledger must exist before versioned migrations run.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )

        _apply_migration(conn, MIGRATION_ID, GOVERNANCE_SCHEMA)
        _apply_migration(conn, PLAN_MIGRATION_ID, PLAN_SCHEMA)
        _apply_migration(conn, LIFECYCLE_MIGRATION_ID, LIFECYCLE_SCHEMA)

    return db_path



@dataclass(frozen=True)
class PlanRecord:
    """Persisted plan identity and its independently managed status."""

    plan_id: str
    repository_id: int
    identity_digest: str
    identity_schema_version: int
    canonical_json: str
    status: str
    created_at: str

    @property
    def snapshot(self) -> dict[str, Any]:
        """Return a fresh copy of the immutable identity snapshot."""
        return json.loads(self.canonical_json)


def _validate_plan_identity(identity: PlanIdentity) -> int:
    """Validate snapshot structure, canonical encoding, and digest."""
    if not isinstance(identity, PlanIdentity):
        raise TypeError("identity must be a PlanIdentity")

    if (
        isinstance(identity.repository_id, bool)
        or not isinstance(identity.repository_id, int)
        or identity.repository_id <= 0
    ):
        raise ValueError("Plan identity has an invalid repository_id")

    if not isinstance(identity.repository_url, str) or not identity.repository_url:
        raise ValueError("Plan identity has an invalid repository_url")

    if not isinstance(identity.canonical_json, str):
        raise ValueError("Plan identity canonical_json must be a string")

    try:
        snapshot = json.loads(identity.canonical_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Plan identity contains invalid JSON") from exc

    if not isinstance(snapshot, dict):
        raise ValueError("Plan identity snapshot must be a JSON object")

    canonical = _json(snapshot)
    if canonical != identity.canonical_json:
        raise ValueError("Plan identity JSON is not canonically encoded")

    expected_digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    if identity.digest != expected_digest:
        raise ValueError("Plan identity digest does not match its snapshot")

    repository = snapshot.get("repository")
    if not isinstance(repository, dict):
        raise ValueError("Plan identity snapshot has no repository object")

    if (
        repository.get("id") != identity.repository_id
        or repository.get("url") != identity.repository_url
    ):
        raise ValueError("Plan identity repository fields do not match snapshot")

    schema_version = snapshot.get("identity_schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version <= 0
    ):
        raise ValueError("Plan identity has an invalid schema version")

    return schema_version


def store_plan_identity(
    identity: PlanIdentity,
    path: Path | None = None,
) -> str:
    """
    Persist an immutable plan identity.

    Repeated storage of the same repository/digest is idempotent.
    This operation does not approve or execute a plan.
    """
    schema_version = _validate_plan_identity(identity)
    created_at = _timestamp(_now())
    proposed_plan_id = str(uuid.uuid4())

    with closing(_open(path)) as conn:
        with conn:
            # Serialize competing writers before checking for an existing plan.
            conn.execute("BEGIN IMMEDIATE")

            existing = conn.execute(
                """
                SELECT
                    plan_id,
                    canonical_json,
                    identity_schema_version
                FROM plans
                WHERE repository_id = ? AND identity_digest = ?
                """,
                (identity.repository_id, identity.digest),
            ).fetchone()

            if existing is not None:
                if (
                    existing["canonical_json"] != identity.canonical_json
                    or existing["identity_schema_version"] != schema_version
                ):
                    raise ValueError(
                        "Existing plan identity conflicts with submitted snapshot"
                    )

                return existing["plan_id"]

            repository = conn.execute(
                "SELECT id FROM repositories WHERE id = ?",
                (identity.repository_id,),
            ).fetchone()

            if repository is None:
                raise ValueError(
                    f"Repository not found: {identity.repository_id}"
                )

            conn.execute(
                """
                INSERT INTO plans (
                    plan_id,
                    repository_id,
                    identity_digest,
                    identity_schema_version,
                    canonical_json,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 'draft', ?)
                """,
                (
                    proposed_plan_id,
                    identity.repository_id,
                    identity.digest,
                    schema_version,
                    identity.canonical_json,
                    created_at,
                ),
            )

            _append_audit(
                conn,
                "PLAN_IDENTITY_RECORDED",
                "plan",
                proposed_plan_id,
                {
                    "repository_id": identity.repository_id,
                    "identity_digest": identity.digest,
                    "identity_schema_version": schema_version,
                    "status": "draft",
                },
            )

    return proposed_plan_id


def get_plan(
    plan_id: str,
    path: Path | None = None,
) -> PlanRecord | None:
    """Retrieve a persisted plan by its unique ID."""
    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("plan_id must be a non-empty string")

    with closing(_open(path)) as conn:
        row = conn.execute(
            """
            SELECT
                plan_id,
                repository_id,
                identity_digest,
                identity_schema_version,
                canonical_json,
                status,
                created_at
            FROM plans
            WHERE plan_id = ?
            """,
            (plan_id,),
        ).fetchone()

    if row is None:
        return None

    return PlanRecord(
        plan_id=row["plan_id"],
        repository_id=row["repository_id"],
        identity_digest=row["identity_digest"],
        identity_schema_version=row["identity_schema_version"],
        canonical_json=row["canonical_json"],
        status=row["status"],
        created_at=row["created_at"],
    )


def _append_audit(
    conn: sqlite3.Connection,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: Mapping[str, Any],
) -> str:
    previous = conn.execute(
        """
        SELECT event_hash
        FROM audit_events
        ORDER BY sequence DESC
        LIMIT 1
        """
    ).fetchone()

    previous_hash = previous["event_hash"] if previous else "GENESIS"
    event_id = str(uuid.uuid4())
    occurred_at = _timestamp(_now())
    payload_json = _json(dict(payload))

    event_hash = _audit_hash(
        event_id,
        event_type,
        entity_type,
        entity_id,
        payload_json,
        occurred_at,
        previous_hash,
    )

    conn.execute(
        """
        INSERT INTO audit_events (
            event_id, event_type, entity_type, entity_id,
            payload_json, occurred_at, previous_hash, event_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_type,
            entity_type,
            entity_id,
            payload_json,
            occurred_at,
            previous_hash,
            event_hash,
        ),
    )
    return event_id


def store_policy(
    policy_id: str,
    policy_version: str,
    policy_hash: str,
    policy: Mapping[str, Any],
    path: Path | None = None,
) -> None:
    if not all((policy_id, policy_version, policy_hash)):
        raise ValueError("Policy ID, version, and hash are required")

    policy_json = _json(dict(policy))
    now = _timestamp(_now())

    with closing(_open(path)) as conn:
        with conn:
            existing = conn.execute(
                """
                SELECT policy_hash, policy_json
                FROM governance_policies
                WHERE policy_id = ? AND policy_version = ?
                """,
                (policy_id, policy_version),
            ).fetchone()

            if existing:
                if (
                    existing["policy_hash"] != policy_hash
                    or existing["policy_json"] != policy_json
                ):
                    raise ValueError(
                        "A policy version already exists with different content"
                    )
                return

            conn.execute(
                """
                INSERT INTO governance_policies (
                    policy_id, policy_version, policy_hash,
                    policy_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (policy_id, policy_version, policy_hash, policy_json, now),
            )
            _append_audit(
                conn,
                "POLICY_RECORDED",
                "governance_policy",
                f"{policy_id}:{policy_version}",
                {
                    "policy_id": policy_id,
                    "policy_version": policy_version,
                    "policy_hash": policy_hash,
                },
            )


def store_approval(
    approval: Approval,
    path: Path | None = None,
    *,
    plan_id: str | None = None,
) -> None:
    issued_at = _timestamp(approval.issued_at)
    expires_at = _timestamp(approval.expires_at)
    recorded_at = _timestamp(_now())

    with closing(_open(path)) as conn:
        with conn:
            if plan_id is not None:
                plan = conn.execute(
                    "SELECT 1 FROM plans WHERE plan_id = ?",
                    (plan_id,),
                ).fetchone()
                if plan is None:
                    raise ValueError("Cannot store approval for an unknown plan")

            conn.execute(
                """
                INSERT INTO action_approvals (
                    approval_id, approver_id, action_digest, scope,
                    issued_at, expires_at, revoked, issuer_type,
                    recorded_at, plan_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.approver_id,
                    approval.action_digest,
                    approval.scope,
                    issued_at,
                    expires_at,
                    int(approval.revoked),
                    approval.issuer_type,
                    recorded_at,
                    plan_id,
                ),
            )
            _append_audit(
                conn,
                "APPROVAL_RECORDED",
                "action_approval",
                approval.approval_id,
                {
                    "approver_id": approval.approver_id,
                    "action_digest": approval.action_digest,
                    "scope": approval.scope,
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "revoked": approval.revoked,
                    "issuer_type": approval.issuer_type,
                    "plan_id": plan_id,
                },
            )

def get_approval(
    approval_id: str,
    path: Path | None = None,
) -> Approval | None:
    with closing(_open(path)) as conn:
        row = conn.execute(
            "SELECT * FROM action_approvals WHERE approval_id = ?",
            (approval_id,),
        ).fetchone()

    if row is None:
        return None

    return Approval(
        approval_id=row["approval_id"],
        approver_id=row["approver_id"],
        action_digest=row["action_digest"],
        scope=row["scope"],
        issued_at=datetime.fromisoformat(row["issued_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        revoked=bool(row["revoked"]),
        issuer_type=row["issuer_type"],
    )


def revoke_approval(
    approval_id: str,
    path: Path | None = None,
) -> bool:
    with closing(_open(path)) as conn:
        with conn:
            cursor = conn.execute(
                """
                UPDATE action_approvals
                SET revoked = 1
                WHERE approval_id = ? AND revoked = 0
                """,
                (approval_id,),
            )

            if cursor.rowcount:
                _append_audit(
                    conn,
                    "APPROVAL_REVOKED",
                    "action_approval",
                    approval_id,
                    {"approval_id": approval_id},
                )

            return cursor.rowcount == 1

def get_plan_approval(
    approval_id: str,
    plan_id: str,
    path: Path | None = None,
) -> Approval | None:
    """Retrieve an approval only when it belongs to the specified plan."""
    with closing(_open(path)) as conn:
        row = conn.execute(
            """
            SELECT *
            FROM action_approvals
            WHERE approval_id = ? AND plan_id = ?
            """,
            (approval_id, plan_id),
        ).fetchone()

    if row is None:
        return None

    return Approval(
        approval_id=row["approval_id"],
        approver_id=row["approver_id"],
        action_digest=row["action_digest"],
        scope=row["scope"],
        issued_at=datetime.fromisoformat(row["issued_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        revoked=bool(row["revoked"]),
        issuer_type=row["issuer_type"],
    )

def record_decision(
    decision: Decision,
    request: ActionRequest,
    source: SourceRecord,
    approval: Approval | None = None,
    path: Path | None = None,
    *,
    plan_id: str | None = None,
) -> str:
    decision_id = str(uuid.uuid4())
    recorded_at = _timestamp(_now())

    source_snapshot = {
        "source_id": source.source_id,
        "target_id": source.target_id,
        "recorded_status": source.recorded_status,
        "approval_recorded": source.approval_recorded,
    }

    request_snapshot = {
        "actor": request.actor,
        "action": request.action,
        "target": request.target,
        "parameters": dict(request.parameters),
        "scope": request.scope,
        "environment": request.environment,
    }

    source_json = _json(source_snapshot)
    request_json = _json(request_snapshot)
    approval_id = approval.approval_id if approval else None

    with closing(_open(path)) as conn:
        with conn:
            if plan_id is not None:
                plan = conn.execute(
                    "SELECT 1 FROM plans WHERE plan_id = ?",
                    (plan_id,),
                ).fetchone()
                if plan is None:
                    raise ValueError("Cannot record decision for an unknown plan")

                if approval_id is not None:
                    linked_approval = conn.execute(
                        """
                        SELECT 1 FROM action_approvals
                        WHERE approval_id = ? AND plan_id = ?
                        """,
                        (approval_id, plan_id),
                    ).fetchone()
                    if linked_approval is None:
                        raise ValueError(
                            "Approval does not belong to the specified plan"
                        )

            conn.execute(
                """
                INSERT INTO governance_decisions (
                    decision_id, disposition, approval_state, action_digest,
                    rationale, policy_id, policy_version,
                    source_snapshot_json, request_snapshot_json,
                    approval_id, recorded_at, plan_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    decision.disposition,
                    decision.approval_state,
                    decision.action_digest,
                    decision.rationale,
                    decision.policy_id,
                    decision.policy_version,
                    source_json,
                    request_json,
                    approval_id,
                    recorded_at,
                    plan_id,
                ),
            )

            _append_audit(
                conn,
                "GOVERNANCE_DECISION_RECORDED",
                "governance_decision",
                decision_id,
                {
                    "disposition": decision.disposition,
                    "approval_state": decision.approval_state,
                    "action_digest": decision.action_digest,
                    "policy_id": decision.policy_id,
                    "policy_version": decision.policy_version,
                    "approval_id": approval_id,
                    "plan_id": plan_id,
                },
            )

    return decision_id

def record_execution(
    result: ExecutionResult,
    action_digest: str | None = None,
    path: Path | None = None,
    *,
    plan_id: str | None = None,
    decision_id: str | None = None,
) -> None:
    if (plan_id is None) != (decision_id is None):
        raise ValueError(
            "plan_id and decision_id must be supplied together"
        )

    recorded_at = _timestamp(_now())

    with closing(_open(path)) as conn:
        with conn:
            if plan_id is not None:
                decision = conn.execute(
                    """
                    SELECT disposition, action_digest
                    FROM governance_decisions
                    WHERE decision_id = ? AND plan_id = ?
                    """,
                    (decision_id, plan_id),
                ).fetchone()

                if decision is None:
                    raise ValueError(
                        "Decision does not belong to the specified plan"
                    )
                if decision["disposition"] != "ALLOW":
                    raise ValueError(
                        "Execution cannot be linked to a non-ALLOW decision"
                    )
                if (
                    action_digest is not None
                    and decision["action_digest"] != action_digest
                ):
                    raise ValueError(
                        "Execution digest does not match its decision"
                    )

            conn.execute(
                """
                INSERT INTO execution_records (
                    result_id, target, resulting_status,
                    side_effect_count, replayed, execution_type,
                    action_digest, recorded_at, plan_id, decision_id
                )
                VALUES (?, ?, ?, ?, ?, 'MOCK', ?, ?, ?, ?)
                """,
                (
                    result.result_id,
                    result.target,
                    result.resulting_status,
                    result.side_effect_count,
                    int(result.replayed),
                    action_digest,
                    recorded_at,
                    plan_id,
                    decision_id,
                ),
            )

            _append_audit(
                conn,
                "MOCK_EXECUTION_RECORDED",
                "execution_record",
                result.result_id,
                {
                    "target": result.target,
                    "resulting_status": result.resulting_status,
                    "side_effect_count": result.side_effect_count,
                    "replayed": result.replayed,
                    "execution_type": "MOCK",
                    "action_digest": action_digest,
                    "plan_id": plan_id,
                    "decision_id": decision_id,
                },
            )

def verify_audit_chain(path: Path | None = None) -> dict[str, Any]:
    """Verify event hashes and links in sequence order."""
    with closing(_open(path)) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY sequence"
        ).fetchall()

    previous_hash = "GENESIS"

    for expected_sequence, row in enumerate(rows, start=1):
        if row["sequence"] != expected_sequence:
            return {
                "valid": False,
                "events_checked": expected_sequence - 1,
                "error": "Audit sequence discontinuity",
                "sequence": row["sequence"],
            }

        if row["previous_hash"] != previous_hash:
            return {
                "valid": False,
                "events_checked": expected_sequence - 1,
                "error": "Previous-hash mismatch",
                "sequence": row["sequence"],
            }

        expected_hash = _audit_hash(
            row["event_id"],
            row["event_type"],
            row["entity_type"],
            row["entity_id"],
            row["payload_json"],
            row["occurred_at"],
            row["previous_hash"],
        )

        if row["event_hash"] != expected_hash:
            return {
                "valid": False,
                "events_checked": expected_sequence - 1,
                "error": "Event-hash mismatch",
                "sequence": row["sequence"],
            }

        previous_hash = row["event_hash"]

    return {
        "valid": True,
        "events_checked": len(rows),
        "head_hash": previous_hash,
        "error": None,
    }
