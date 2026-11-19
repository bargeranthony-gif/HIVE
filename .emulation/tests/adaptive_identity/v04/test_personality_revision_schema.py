import sqlite3

from ._load_engine import _load_engine


def test_new_database_uses_schema_v5_and_creates_revision_tables(tmp_path):
    engine = _load_engine()
    database = tmp_path / "schema-v5.sqlite"
    store = engine.IdentityStore(database)

    with store._connect() as conn:
        version = conn.execute(
            "SELECT version FROM haie_schema"
        ).fetchone()["version"]

        tables = {
            row["name"]
            for row in conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

    assert version == 5
    assert "personality_revisions" in tables
    assert "revision_evidence" in tables


def test_schema_v3_database_migrates_to_v5_without_losing_identity(
    tmp_path,
):
    engine = _load_engine()
    database = tmp_path / "migration-v3.sqlite"

    first = engine.IdentityStore(database)
    first.create_identity(
        "hive-1",
        "HIVE",
        traits={"humor": 0.7},
    )

    with first._connect() as conn:
        conn.execute("UPDATE haie_schema SET version = 3")
        conn.execute("DROP TABLE revision_evidence")
        conn.execute("DROP TABLE personality_revisions")

    migrated = engine.IdentityStore(database)
    identity = migrated.get_identity("hive-1")

    with migrated._connect() as conn:
        version = conn.execute(
            "SELECT version FROM haie_schema"
        ).fetchone()["version"]

    assert version == 5
    assert identity["personality"]["traits"]["humor"] == 0.7
    assert identity["personality"]["revision"] == 1


def test_deleted_claim_preserves_revision_evidence_audit_reference(
    tmp_path,
):
    engine = _load_engine()
    store = engine.IdentityStore(tmp_path / "evidence-retention.sqlite")
    store.create_identity("hive-1", "HIVE")

    store.record_evidence_source_group(
        "hive-1", "group-1", "independent"
    )
    store.record_evidence_source(
        "source-1",
        "hive-1",
        "test_source",
        group_id="group-1",
    )
    store.record_experience(
        "experience-1",
        "hive-1",
        "observation",
        "Observed a repeated humor-related behavior.",
        source_id="source-1",
    )
    store.record_claim(
        "claim-1",
        "experience-1",
        "personality_trait:humor:direction",
        "increase",
        "supports",
        context_key="global_personality",
    )

    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO personality_revisions (
                revision_id, identity_id, trait_key,
                previous_value, proposed_value,
                baseline_profile_revision, status,
                rationale, created_at
            )
            VALUES (
                'revision-1', 'hive-1', 'humor',
                0.5, 0.6, 1, 'pending',
                'Schema retention test', '2026-01-01T00:00:00+00:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO revision_evidence (
                evidence_link_id, revision_id, claim_id,
                original_claim_id, source_group_id, created_at
            )
            VALUES (
                'link-1', 'revision-1', 'claim-1',
                'claim-1', 'group-1', '2026-01-01T00:00:00+00:00'
            )
            """
        )
        conn.execute("DELETE FROM claims WHERE claim_id = 'claim-1'")

        row = conn.execute(
            """
            SELECT claim_id, original_claim_id, source_group_id
            FROM revision_evidence
            WHERE evidence_link_id = 'link-1'
            """
        ).fetchone()

    assert row["claim_id"] is None
    assert row["original_claim_id"] == "claim-1"
    assert row["source_group_id"] == "group-1"


def test_revision_schema_rejects_invalid_status(tmp_path):
    engine = _load_engine()
    store = engine.IdentityStore(tmp_path / "invalid-status.sqlite")
    store.create_identity("hive-1", "HIVE")

    with store._connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO personality_revisions (
                    revision_id, identity_id, trait_key,
                    previous_value, proposed_value,
                    baseline_profile_revision, status,
                    rationale, created_at
                )
                VALUES (
                    'revision-1', 'hive-1', 'humor',
                    0.5, 0.6, 1, 'approved',
                    'Invalid status test', '2026-01-01T00:00:00+00:00'
                )
                """
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Invalid revision status was accepted.")


def test_schema_v4_migrates_legacy_pending_revision_without_inventing_interaction_type(
    tmp_path,
):
    engine = _load_engine()
    database = tmp_path / "migration-v4.sqlite"

    first = engine.IdentityStore(database)
    first.create_identity("hive-1", "HIVE", traits={"humor": 0.6})

    with first._connect() as conn:
        conn.execute(
            """
            INSERT INTO personality_revisions (
                revision_id, identity_id, trait_key,
                previous_value, proposed_value,
                baseline_profile_revision, status,
                rationale, created_at
            )
            VALUES (
                'legacy-revision', 'hive-1', 'humor',
                0.5, 0.6, 1, 'pending',
                'Legacy v4 proposal', '2026-01-01T00:00:00+00:00'
            )
            """
        )

        # Reconstruct the v4 table layout and version.
        conn.execute(
            "ALTER TABLE personality_revisions DROP COLUMN interaction_type"
        )
        conn.execute("UPDATE haie_schema SET version = 4")

    migrated = engine.IdentityStore(database)
    identity = migrated.get_identity("hive-1")

    with migrated._connect() as conn:
        version = conn.execute(
            "SELECT version FROM haie_schema"
        ).fetchone()["version"]

        revision = conn.execute(
            """
            SELECT revision_id, status, interaction_type
            FROM personality_revisions
            WHERE revision_id = 'legacy-revision'
            """
        ).fetchone()

    assert version == 5
    assert identity["personality"]["traits"]["humor"] == 0.6
    assert identity["personality"]["revision"] == 1
    assert revision["revision_id"] == "legacy-revision"
    assert revision["status"] == "pending"
    assert revision["interaction_type"] == ""
