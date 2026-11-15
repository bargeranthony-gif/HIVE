from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .config import database_path
from .db import connect
from .governance import Approval, Decision, ExecutionResult, ActionRequest, SourceRecord


MIGRATION_ID = "001_governance_store"


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

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
    """Create governance storage tables without replacing existing data."""
    db_path = path or database_path()

    with closing(_open(db_path)) as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations
                (migration_id, applied_at)
            VALUES (?, ?)
            """,
            (MIGRATION_ID, _timestamp(_now())),
        )
        conn.commit()

    return db_path


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
) -> None:
    issued_at = _timestamp(approval.issued_at)
    expires_at = _timestamp(approval.expires_at)
    recorded_at = _timestamp(_now())

    with closing(_open(path)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO action_approvals (
                    approval_id, approver_id, action_digest, scope,
                    issued_at, expires_at, revoked, issuer_type, recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def record_decision(
    decision: Decision,
    request: ActionRequest,
    source: SourceRecord,
    approval: Approval | None = None,
    path: Path | None = None,
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
            conn.execute(
                """
                INSERT INTO governance_decisions (
                    decision_id, disposition, approval_state, action_digest,
                    rationale, policy_id, policy_version,
                    source_snapshot_json, request_snapshot_json,
                    approval_id, recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                },
            )

    return decision_id


def record_execution(
    result: ExecutionResult,
    action_digest: str | None = None,
    path: Path | None = None,
) -> None:
    recorded_at = _timestamp(_now())

    with closing(_open(path)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO execution_records (
                    result_id, target, resulting_status,
                    side_effect_count, replayed, execution_type,
                    action_digest, recorded_at
                )
                VALUES (?, ?, ?, ?, ?, 'MOCK', ?, ?)
                """,
                (
                    result.result_id,
                    result.target,
                    result.resulting_status,
                    result.side_effect_count,
                    int(result.replayed),
                    action_digest,
                    recorded_at,
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
