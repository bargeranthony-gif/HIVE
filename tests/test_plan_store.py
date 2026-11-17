import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest

from hive.capabilities import add_capability
from hive.db import initialize
from hive.governance_store import (
    get_plan,
    store_plan_identity,
    verify_audit_chain,
)
from hive.plan_identity import create_plan_identity
from hive.planner import PlanStep
from hive.planning import assess_plan
from hive.repositories import add_repository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setenv("HIVE_HOME", str(tmp_path))
    initialize()
    return add_repository("https://github.com/example/plan-store")


def make_identity(repository):
    add_capability(
        repository,
        "browser.inspect",
        description="Browser inspection",
        evidence_level="test_verified",
        evidence="Automated integration test passed",
    )

    assessment = assess_plan(
        "Inspect a website",
        [
            PlanStep(
                "inspect",
                "Inspect the target website",
                required_capabilities=("browser.inspect",),
            )
        ],
        repository_id=repository,
    )

    return create_plan_identity(assessment, repository)


def test_plan_identity_round_trip(repository):
    identity = make_identity(repository)

    plan_id = store_plan_identity(identity)
    restored = get_plan(plan_id)

    assert restored is not None
    assert restored.plan_id == plan_id
    assert restored.repository_id == repository
    assert restored.identity_digest == identity.digest
    assert restored.identity_schema_version == 1
    assert restored.canonical_json == identity.canonical_json
    assert restored.snapshot == identity.snapshot
    assert restored.status == "draft"


def test_identical_plan_storage_is_idempotent(repository):
    identity = make_identity(repository)

    first_id = store_plan_identity(identity)
    second_id = store_plan_identity(identity)

    assert first_id == second_id

    from hive.db import connect

    with connect() as conn:
        plan_count = conn.execute(
            "SELECT COUNT(*) FROM plans"
        ).fetchone()[0]

        audit_count = conn.execute(
            """
            SELECT COUNT(*) FROM audit_events
            WHERE event_type = 'PLAN_IDENTITY_RECORDED'
            """
        ).fetchone()[0]

    assert plan_count == 1
    assert audit_count == 1
    assert verify_audit_chain()["valid"] is True


def test_plan_storage_does_not_approve_or_execute(repository):
    identity = make_identity(repository)
    store_plan_identity(identity)

    from hive.db import connect

    with connect() as conn:
        counts = {
            table: conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in (
                "action_approvals",
                "governance_decisions",
                "execution_records",
            )
        }

    assert counts == {
        "action_approvals": 0,
        "governance_decisions": 0,
        "execution_records": 0,
    }


def test_invalid_digest_is_rejected(repository):
    identity = make_identity(repository)
    invalid = replace(identity, digest="0" * 64)

    with pytest.raises(ValueError, match="digest"):
        store_plan_identity(invalid)


def test_noncanonical_json_is_rejected(repository):
    identity = make_identity(repository)
    snapshot = identity.snapshot
    noncanonical = json.dumps(snapshot, indent=2)

    invalid = replace(identity, canonical_json=noncanonical)

    with pytest.raises(ValueError, match="canonically encoded"):
        store_plan_identity(invalid)


def test_snapshot_repository_mismatch_is_rejected(repository):
    identity = make_identity(repository)
    snapshot = identity.snapshot
    snapshot["repository"]["id"] = repository + 100

    canonical_json = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    invalid = replace(
        identity,
        canonical_json=canonical_json,
        digest=digest,
    )

    with pytest.raises(ValueError, match="repository fields"):
        store_plan_identity(invalid)


def test_missing_plan_returns_none(repository):
    make_identity(repository)

    assert get_plan("missing-plan-id") is None


def test_plan_identity_fields_cannot_be_updated(repository):
    identity = make_identity(repository)
    plan_id = store_plan_identity(identity)

    from hive.db import connect

    with connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                """
                UPDATE plans
                SET canonical_json = '{}'
                WHERE plan_id = ?
                """,
                (plan_id,),
            )


def test_stored_plan_cannot_be_deleted(repository):
    identity = make_identity(repository)
    plan_id = store_plan_identity(identity)

    from hive.db import connect

    with connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            conn.execute(
                "DELETE FROM plans WHERE plan_id = ?",
                (plan_id,),
            )


def test_plan_migration_is_recorded(repository):
    from hive.db import connect

    with connect() as conn:
        migrations = {
            row[0]
            for row in conn.execute(
                "SELECT migration_id FROM schema_migrations"
            )
        }

    assert "001_governance_store" in migrations
    assert "002_plan_persistence" in migrations


def test_repository_with_stored_plan_cannot_be_deleted(repository):
    identity = make_identity(repository)
    store_plan_identity(identity)

    from hive.db import connect

    with connect() as conn:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="FOREIGN KEY constraint failed",
        ):
            conn.execute(
                "DELETE FROM repositories WHERE id = ?",
                (repository,),
            )
