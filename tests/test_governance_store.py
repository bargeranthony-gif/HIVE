import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from hive.db import initialize
from hive.governance import (
    ActionRequest,
    Approval,
    Decision,
    ExecutionResult,
    SourceRecord,
)
from hive.governance_store import (
    get_approval,
    initialize_governance,
    record_decision,
    record_execution,
    revoke_approval,
    store_approval,
    store_policy,
    verify_audit_chain,
)


def make_approval():
    now = datetime.now(timezone.utc)
    return Approval(
        approval_id="approval-test-001",
        approver_id="synthetic-approver",
        action_digest="digest-test-001",
        scope="test",
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=10),
        issuer_type="synthetic_test_fixture",
    )


def make_request():
    return ActionRequest(
        actor="test-actor",
        action="set_purchase_status",
        target="purchase-001",
        parameters={"status": "approved"},
        scope="test",
        environment="synthetic",
    )


def make_source():
    return SourceRecord(
        source_id="source-001",
        original_text="Synthetic test source",
        target_id="purchase-001",
        recorded_status="pending",
        approval_recorded=True,
    )


def make_decision():
    return Decision(
        disposition="ALLOW",
        approval_state="RECORDED",
        action_digest="digest-test-001",
        rationale="Synthetic test approval accepted",
    )


def test_governance_initialization_is_idempotent(tmp_path):
    db = tmp_path / "hive.db"

    initialize(db)
    initialize(db)

    with sqlite3.connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "governance_policies",
        "action_approvals",
        "governance_decisions",
        "execution_records",
        "audit_events",
        "schema_migrations",
    }.issubset(tables)


def test_existing_data_survives_governance_initialization(tmp_path):
    db = tmp_path / "hive.db"
    initialize(db)

    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO repositories (owner, name, url)
            VALUES ('test-owner', 'test-repo', 'https://example.com/test-repo')
            """
        )

    initialize_governance(db)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT owner, name FROM repositories WHERE url = ?",
            ("https://example.com/test-repo",),
        ).fetchone()

    assert row == ("test-owner", "test-repo")


def test_policy_is_stored_and_conflicting_version_rejected(tmp_path):
    db = tmp_path / "hive.db"
    initialize_governance(db)

    store_policy("policy-a", "1", "hash-a", {"rule": "allow-test"}, db)
    store_policy("policy-a", "1", "hash-a", {"rule": "allow-test"}, db)

    with pytest.raises(ValueError):
        store_policy("policy-a", "1", "hash-different", {"rule": "changed"}, db)

    assert verify_audit_chain(db)["events_checked"] == 1


def test_approval_round_trip_and_revocation(tmp_path):
    db = tmp_path / "hive.db"
    initialize_governance(db)
    approval = make_approval()

    store_approval(approval, db)

    restored = get_approval(approval.approval_id, db)
    assert restored == approval

    assert revoke_approval(approval.approval_id, db) is True
    assert revoke_approval(approval.approval_id, db) is False
    assert get_approval(approval.approval_id, db).revoked is True

    assert verify_audit_chain(db)["events_checked"] == 2


def test_decision_and_mock_execution_are_persisted(tmp_path):
    db = tmp_path / "hive.db"
    initialize_governance(db)

    decision_id = record_decision(
        make_decision(),
        make_request(),
        make_source(),
        make_approval(),
        db,
    )

    result = ExecutionResult(
        result_id="mock-result-001",
        target="purchase-001",
        resulting_status="approved",
        side_effect_count=1,
        replayed=False,
    )
    record_execution(result, "digest-test-001", db)

    with sqlite3.connect(db) as conn:
        decision = conn.execute(
            """
            SELECT disposition, action_digest, approval_id
            FROM governance_decisions
            WHERE decision_id = ?
            """,
            (decision_id,),
        ).fetchone()

        execution = conn.execute(
            """
            SELECT target, resulting_status, execution_type
            FROM execution_records
            WHERE result_id = ?
            """,
            ("mock-result-001",),
        ).fetchone()

    assert decision == (
        "ALLOW",
        "digest-test-001",
        "approval-test-001",
    )
    assert execution == ("purchase-001", "approved", "MOCK")
    assert verify_audit_chain(db)["events_checked"] == 2


def test_audit_events_reject_update_and_delete(tmp_path):
    db = tmp_path / "hive.db"
    initialize_governance(db)
    store_policy("policy-a", "1", "hash-a", {"rule": "test"}, db)

    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE audit_events SET event_type = 'ALTERED' WHERE sequence = 1"
            )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM audit_events WHERE sequence = 1")


def test_audit_verification_detects_tampering(tmp_path):
    db = tmp_path / "hive.db"
    initialize_governance(db)
    store_policy("policy-a", "1", "hash-a", {"rule": "test"}, db)

    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER audit_events_no_update")
        conn.execute(
            "UPDATE audit_events SET payload_json = '{}' WHERE sequence = 1"
        )

    result = verify_audit_chain(db)
    assert result["valid"] is False
    assert result["error"] == "Event-hash mismatch"


def test_existing_governance_database_upgrades_to_plan_migration(tmp_path):
    from hive.governance_store import (
        GOVERNANCE_SCHEMA,
        initialize_governance,
    )

    db = tmp_path / "legacy-hive.db"

    # Simulate a database created by the original 001 governance migration.
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE schema_migrations (
                migration_id TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.executescript(
            "BEGIN IMMEDIATE;\n"
            + GOVERNANCE_SCHEMA
            + """
            INSERT INTO schema_migrations (migration_id, applied_at)
            VALUES ('001_governance_store', '2026-01-01T00:00:00+00:00');
            COMMIT;
            """
        )
        conn.execute(
            """
            INSERT INTO governance_policies (
                policy_id, policy_version, policy_hash, policy_json, created_at
            )
            VALUES ('legacy-policy', '1', 'legacy-hash', '{}', '2026-01-01')
            """
        )

    initialize_governance(db)

    with sqlite3.connect(db) as conn:
        migrations = {
            row[0]
            for row in conn.execute(
                "SELECT migration_id FROM schema_migrations"
            )
        }
        policy = conn.execute(
            """
            SELECT policy_id, policy_version, policy_hash
            FROM governance_policies
            WHERE policy_id = 'legacy-policy'
            """
        ).fetchone()
        plan_table = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'plans'
            """
        ).fetchone()

    assert migrations == {
        "001_governance_store",
        "002_plan_persistence",
    }
    assert policy == ("legacy-policy", "1", "legacy-hash")
    assert plan_table == ("plans",)


def test_failed_migration_rolls_back_schema_and_ledger(tmp_path):
    from hive.governance_store import _apply_migration

    db = tmp_path / "migration-rollback.db"

    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE schema_migrations (
                migration_id TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )

        with pytest.raises(sqlite3.OperationalError):
            _apply_migration(
                conn,
                "003_test_failure",
                """
                CREATE TABLE migration_partial (
                    id INTEGER PRIMARY KEY
                );
                THIS IS NOT VALID SQL;
                """,
            )

        partial_table = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'migration_partial'
            """
        ).fetchone()
        migration_record = conn.execute(
            """
            SELECT 1 FROM schema_migrations
            WHERE migration_id = '003_test_failure'
            """
        ).fetchone()

        assert partial_table is None
        assert migration_record is None
        assert conn.in_transaction is False
