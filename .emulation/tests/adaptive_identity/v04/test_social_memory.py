import pytest

from ._load_engine import _load_engine


@pytest.fixture
def engine_module():
    return _load_engine()


@pytest.fixture
def store(tmp_path, engine_module):
    return engine_module.IdentityStore(tmp_path / "haie-social.sqlite")


def make_relationship(store):
    store.create_identity("hive-1", "HIVE")
    return store.record_relationship(
        "hive-1", "person-1", "Alex"
    )


def test_schema_v1_migrates_without_losing_identity(
    tmp_path, engine_module
):
    database = tmp_path / "migration.sqlite"
    first = engine_module.IdentityStore(database)
    first.create_identity("hive-1", "HIVE")

    with first._connect() as conn:
        conn.execute("UPDATE haie_schema SET version = 1")

    migrated = engine_module.IdentityStore(database)

    assert migrated.get_identity("hive-1")["display_name"] == "HIVE"

    with migrated._connect() as conn:
        version = conn.execute(
            "SELECT version FROM haie_schema"
        ).fetchone()["version"]

    assert version == 3


def test_schema_v2_migrates_and_preserves_existing_data(
    tmp_path, engine_module
):
    database = tmp_path / "migration-v2.sqlite"
    first = engine_module.IdentityStore(database)

    first.create_identity(
        "hive-1",
        "HIVE",
        traits={"humor": 0.7},
        descriptors={"communication_style": "direct"},
    )
    first.record_relationship("hive-1", "person-1", "Alex")
    first.record_social_memory(
        "memory-1",
        "hive-1",
        "person-1",
        "preference",
        "Likes coffee.",
        source_type="observed_interaction",
        certainty="inferred",
    )
    first.correct_social_memory(
        "memory-1",
        "Prefers tea.",
        reason="Owner correction.",
        source_type="owner_input",
        certainty="explicit",
    )

    # Reconstruct a genuine v2 database by removing only v3 additions.
    with first._connect() as conn:
        conn.execute("DROP TABLE claims")
        conn.execute("DROP TABLE experiences")
        conn.execute("DROP TABLE evidence_sources")
        conn.execute("DROP TABLE evidence_group_revisions")
        conn.execute("DROP TABLE evidence_source_groups")
        conn.execute("UPDATE haie_schema SET version = 2")

    migrated = engine_module.IdentityStore(database)

    assert migrated.get_identity("hive-1")["display_name"] == "HIVE"
    assert migrated.get_relationship(
        "hive-1", "person-1"
    )["display_name"] == "Alex"

    memory = migrated.get_social_memory("memory-1")
    assert memory["content"] == "Prefers tea."
    assert memory["source_type"] == "owner_input"
    assert memory["certainty"] == "explicit"

    revisions = migrated.list_social_memory_revisions("memory-1")
    assert len(revisions) == 1
    assert revisions[0]["previous_content"] == "Likes coffee."
    assert revisions[0]["new_content"] == "Prefers tea."

    with migrated._connect() as conn:
        version = conn.execute(
            "SELECT version FROM haie_schema"
        ).fetchone()["version"]

        profile = conn.execute(
            """
            SELECT traits_json, descriptors_json
            FROM personality_profiles
            WHERE identity_id = ?
            """,
            ("hive-1",),
        ).fetchone()

        assert profile is not None
        assert '"humor":0.7' in profile["traits_json"]
        assert '"communication_style":"direct"' in (
            profile["descriptors_json"]
        )

    assert version == 3


def test_relationship_is_scoped_to_one_identity(store):
    store.create_identity("hive-1", "HIVE")
    store.create_identity("hive-2", "HIVE Copy")

    store.record_relationship("hive-1", "person-1", "Alex")

    assert len(store.list_relationships("hive-1")) == 1
    assert store.list_relationships("hive-2") == []


def test_record_and_retrieve_social_memory(store):
    make_relationship(store)

    memory = store.record_social_memory(
        "memory-1",
        "hive-1",
        "person-1",
        "communication_preference",
        "Prefers concise explanations.",
        source_type="direct_statement",
        source_reference="conversation-12",
        certainty="explicit",
    )

    assert memory["content"] == "Prefers concise explanations."
    assert memory["certainty"] == "explicit"
    assert memory["source_type"] == "direct_statement"
    assert memory["status"] == "active"


def test_memory_requires_existing_relationship(store):
    store.create_identity("hive-1", "HIVE")

    with pytest.raises(KeyError):
        store.record_social_memory(
            "memory-1",
            "hive-1",
            "person-1",
            "preference",
            "Likes concise answers.",
        )


def test_memories_are_isolated_by_subject(store):
    make_relationship(store)
    store.record_relationship("hive-1", "person-2", "Jordan")

    store.record_social_memory(
        "memory-1", "hive-1", "person-1",
        "preference", "Likes tea."
    )
    store.record_social_memory(
        "memory-2", "hive-1", "person-2",
        "preference", "Likes coffee."
    )

    alex = store.list_social_memories("hive-1", "person-1")
    jordan = store.list_social_memories("hive-1", "person-2")

    assert [item["content"] for item in alex] == ["Likes tea."]
    assert [item["content"] for item in jordan] == ["Likes coffee."]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"category": "unknown"},
        {"certainty": "certain"},
        {"source_type": "guess"},
    ],
)
def test_invalid_memory_classification_is_rejected(store, kwargs):
    make_relationship(store)

    values = {
        "category": "preference",
        "certainty": "explicit",
        "source_type": "owner_input",
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        store.record_social_memory(
            "memory-1",
            "hive-1",
            "person-1",
            values["category"],
            "Likes tea.",
            source_type=values["source_type"],
            certainty=values["certainty"],
        )


def test_memory_correction_preserves_revision_history(store):
    make_relationship(store)

    store.record_social_memory(
        "memory-1",
        "hive-1",
        "person-1",
        "preference",
        "Likes coffee.",
        source_type="observed_interaction",
        certainty="inferred",
    )

    corrected = store.correct_social_memory(
        "memory-1",
        "Prefers tea.",
        reason="Owner corrected the earlier inference.",
        source_type="owner_input",
        certainty="explicit",
    )

    revisions = store.list_social_memory_revisions("memory-1")

    assert corrected["content"] == "Prefers tea."
    assert corrected["source_type"] == "owner_input"
    assert corrected["certainty"] == "explicit"
    assert len(revisions) == 1
    assert revisions[0]["previous_content"] == "Likes coffee."
    assert revisions[0]["new_content"] == "Prefers tea."


def test_correction_requires_a_reason(store):
    make_relationship(store)
    store.record_social_memory(
        "memory-1", "hive-1", "person-1",
        "preference", "Likes coffee."
    )

    with pytest.raises(ValueError):
        store.correct_social_memory(
            "memory-1", "Prefers tea.", reason=" "
        )


def test_forgetting_subject_deletes_relationship_memories_and_revisions(
    store
):
    make_relationship(store)
    store.record_social_memory(
        "memory-1",
        "hive-1",
        "person-1",
        "preference",
        "Likes coffee.",
    )
    store.correct_social_memory(
        "memory-1",
        "Prefers tea.",
        reason="Correction.",
    )

    result = store.forget_subject("hive-1", "person-1")

    assert result["relationship_deleted"] is True
    assert result["memories_deleted"] == 1

    with pytest.raises(KeyError):
        store.get_relationship("hive-1", "person-1")

    with pytest.raises(KeyError):
        store.get_social_memory("memory-1")


def test_forgetting_one_subject_preserves_other_subject(store):
    make_relationship(store)
    store.record_relationship("hive-1", "person-2", "Jordan")

    store.record_social_memory(
        "memory-1", "hive-1", "person-1",
        "preference", "Likes coffee."
    )
    store.record_social_memory(
        "memory-2", "hive-1", "person-2",
        "preference", "Likes tea."
    )

    store.forget_subject("hive-1", "person-1")

    assert store.get_social_memory("memory-2")["content"] == "Likes tea."
    assert store.get_relationship("hive-1", "person-2")["display_name"] == (
        "Jordan"
    )


def test_duplicate_memory_id_is_rejected(store):
    make_relationship(store)

    store.record_social_memory(
        "memory-1", "hive-1", "person-1",
        "preference", "Likes coffee."
    )

    with pytest.raises(Exception):
        store.record_social_memory(
            "memory-1", "hive-1", "person-1",
            "preference", "Likes tea."
        )


def test_v3_migration_failure_rolls_back_all_schema_changes(
    tmp_path, engine_module
):
    import sqlite3

    database = tmp_path / "migration-rollback.sqlite"
    first = engine_module.IdentityStore(database)
    first.create_identity("hive-1", "HIVE")

    with first._connect() as conn:
        # Reconstruct a genuine v2 database before injecting the failure.
        conn.execute("DROP TABLE claims")
        conn.execute("DROP TABLE experiences")
        conn.execute("DROP TABLE evidence_sources")
        conn.execute("DROP TABLE evidence_group_revisions")
        conn.execute("DROP TABLE evidence_source_groups")
        conn.execute("UPDATE haie_schema SET version = 2")
        conn.execute("""
            CREATE TRIGGER reject_v3_version
            BEFORE UPDATE OF version ON haie_schema
            WHEN NEW.version = 3
            BEGIN
                SELECT RAISE(ABORT, 'forced migration failure');
            END
        """)

    with pytest.raises(sqlite3.IntegrityError):
        engine_module.IdentityStore(database)

    with first._connect() as conn:
        version = conn.execute(
            "SELECT version FROM haie_schema"
        ).fetchone()["version"]

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert version == 2
    assert "evidence_source_groups" not in tables
    assert "evidence_group_revisions" not in tables
    assert "evidence_sources" not in tables
    assert "experiences" not in tables
    assert "claims" not in tables
    assert first.get_identity("hive-1")["display_name"] == "HIVE"


def test_unsupported_schema_version_is_rejected_without_changes(
    tmp_path, engine_module
):
    database = tmp_path / "unsupported-schema.sqlite"
    first = engine_module.IdentityStore(database)
    first.create_identity("hive-1", "HIVE")

    with first._connect() as conn:
        conn.execute("UPDATE haie_schema SET version = 99")

    with pytest.raises(RuntimeError, match="Unsupported HAIE schema"):
        engine_module.IdentityStore(database)

    with first._connect() as conn:
        version = conn.execute(
            "SELECT version FROM haie_schema"
        ).fetchone()["version"]

    assert version == 99
    assert first.get_identity("hive-1")["display_name"] == "HIVE"


def test_v3_schema_has_no_foreign_key_violations(store):
    store.create_identity("hive-1", "HIVE")

    with store._connect() as conn:
        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    assert violations == []
