import sqlite3

import pytest

from ._load_engine import _load_engine


@pytest.fixture
def engine_module():
    return _load_engine()


@pytest.fixture
def store(tmp_path, engine_module):
    return engine_module.IdentityStore(
        tmp_path / "haie-evidence.sqlite"
    )


def _identity(store):
    store.create_identity("hive-1", "HIVE")
    store.record_relationship("hive-1", "person-1", "Alex")


def test_record_and_retrieve_evidence_source_group(store):
    store.create_identity("hive-1", "HIVE")

    group = store.record_evidence_source_group(
        "hive-1", "group-1", "independent"
    )

    assert group["identity_id"] == "hive-1"
    assert group["group_id"] == "group-1"
    assert group["independence_status"] == "independent"

    assert store.get_evidence_source_group(
        "hive-1", "group-1"
    )["independence_status"] == "independent"


def test_source_group_requires_existing_identity(store):
    with pytest.raises(KeyError):
        store.record_evidence_source_group(
            "missing-hive", "group-1", "independent"
        )


@pytest.mark.parametrize(
    "status",
    ["unknown", "", None, 1],
)
def test_invalid_source_group_status_is_rejected(store, status):
    store.create_identity("hive-1", "HIVE")

    with pytest.raises(ValueError):
        store.record_evidence_source_group(
            "hive-1", "group-1", status
        )


def test_source_group_reclassification_preserves_audit_history(store):
    store.create_identity("hive-1", "HIVE")
    store.record_evidence_source_group(
        "hive-1", "group-1", "unverified"
    )

    updated = store.revise_evidence_source_group(
        "hive-1",
        "group-1",
        "independent",
        reason="Owner verified the source origin.",
    )

    assert updated["independence_status"] == "independent"

    revisions = store.list_evidence_group_revisions(
        "hive-1", "group-1"
    )

    assert len(revisions) == 1
    assert revisions[0]["previous_status"] == "unverified"
    assert revisions[0]["new_status"] == "independent"
    assert revisions[0]["reason"] == (
        "Owner verified the source origin."
    )


def test_source_group_reclassification_requires_reason(store):
    store.create_identity("hive-1", "HIVE")
    store.record_evidence_source_group(
        "hive-1", "group-1", "unverified"
    )

    with pytest.raises(ValueError):
        store.revise_evidence_source_group(
            "hive-1", "group-1", "independent", reason=" "
        )

    assert store.get_evidence_source_group(
        "hive-1", "group-1"
    )["independence_status"] == "unverified"


def test_record_source_with_and_without_group(store):
    store.create_identity("hive-1", "HIVE")
    store.record_evidence_source_group(
        "hive-1", "group-1", "independent"
    )

    grouped = store.record_evidence_source(
        "source-1",
        "hive-1",
        "direct_statement",
        source_reference="conversation-001",
        group_id="group-1",
    )
    ungrouped = store.record_evidence_source(
        "source-2",
        "hive-1",
        "observed_interaction",
    )

    assert grouped["group_id"] == "group-1"
    assert grouped["source_reference"] == "conversation-001"
    assert ungrouped["group_id"] is None


def test_source_cannot_reference_another_identitys_group(store):
    store.create_identity("hive-1", "HIVE")
    store.create_identity("hive-2", "HIVE-2")
    store.record_evidence_source_group(
        "hive-2", "group-2", "independent"
    )

    with pytest.raises((KeyError, ValueError)):
        store.record_evidence_source(
            "source-1",
            "hive-1",
            "direct_statement",
            group_id="group-2",
        )


def test_record_experience_preserves_observation_and_interpretation(store):
    _identity(store)
    store.record_evidence_source_group(
        "hive-1", "group-1", "independent"
    )
    store.record_evidence_source(
        "source-1", "hive-1", "observed_interaction",
        group_id="group-1",
    )

    experience = store.record_experience(
        experience_id="experience-1",
        identity_id="hive-1",
        subject_id="person-1",
        interaction_type="conversation",
        summary="Discussed a preferred beverage.",
        observation="Alex explicitly requested tea.",
        interpretation="Alex may prefer tea.",
        outcome="Tea was prepared.",
        session_id="session-1",
        source_id="source-1",
        confidence=0.8,
    )

    assert experience["observation"] == "Alex explicitly requested tea."
    assert experience["interpretation"] == "Alex may prefer tea."
    assert experience["source_id"] == "source-1"
    assert experience["subject_id"] == "person-1"
    assert experience["confidence"] == 0.8


def test_experience_requires_existing_relationship_when_subject_is_set(store):
    store.create_identity("hive-1", "HIVE")

    with pytest.raises((KeyError, ValueError)):
        store.record_experience(
            experience_id="experience-1",
            identity_id="hive-1",
            subject_id="missing-person",
            interaction_type="conversation",
            summary="An interaction.",
        )


@pytest.mark.parametrize("confidence", [True, -0.1, 1.1, "0.8", None])
def test_invalid_experience_confidence_is_rejected(
    store, confidence
):
    store.create_identity("hive-1", "HIVE")

    with pytest.raises(ValueError):
        store.record_experience(
            experience_id="experience-1",
            identity_id="hive-1",
            interaction_type="observation",
            summary="An observation.",
            confidence=confidence,
        )


def test_record_claim_preserves_original_text(store):
    store.create_identity("hive-1", "HIVE")
    store.record_experience(
        experience_id="experience-1",
        identity_id="hive-1",
        interaction_type="conversation",
        summary="Discussed beverages.",
    )

    claim = store.record_claim(
        claim_id="claim-1",
        experience_id="experience-1",
        claim_key=" Preferred   Beverage ",
        claim_value="  Green   Tea ",
        stance="supports",
        context_key=" Casual   Conversation ",
        confidence=0.75,
    )

    assert claim["claim_key"] == " Preferred   Beverage "
    assert claim["claim_value"] == "  Green   Tea "
    assert claim["context_key"] == " Casual   Conversation "
    assert claim["stance"] == "supports"
    assert claim["confidence"] == 0.75


@pytest.mark.parametrize(
    "stance",
    ["agree", "disagree", "unknown", "", None],
)
def test_invalid_claim_stance_is_rejected(store, stance):
    store.create_identity("hive-1", "HIVE")
    store.record_experience(
        experience_id="experience-1",
        identity_id="hive-1",
        interaction_type="observation",
        summary="An observation.",
    )

    with pytest.raises(ValueError):
        store.record_claim(
            claim_id="claim-1",
            experience_id="experience-1",
            claim_key="preference",
            claim_value="tea",
            stance=stance,
        )


def test_claim_requires_existing_experience(store):
    with pytest.raises(KeyError):
        store.record_claim(
            claim_id="claim-1",
            experience_id="missing-experience",
            claim_key="preference",
            claim_value="tea",
            stance="supports",
        )


def test_evidence_records_are_isolated_by_identity(store):
    store.create_identity("hive-1", "HIVE")
    store.create_identity("hive-2", "HIVE-2")

    store.record_evidence_source_group(
        "hive-1", "group-1", "independent"
    )

    with pytest.raises(KeyError):
        store.get_evidence_source_group("hive-2", "group-1")


def test_direct_sql_group_status_change_requires_revision(store):
    store.create_identity("hive-1", "HIVE")
    store.record_evidence_source_group(
        "hive-1", "group-1", "unverified"
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="requires a matching audit revision",
    ):
        with store._connect() as conn:
            conn.execute(
                """
                UPDATE evidence_source_groups
                SET independence_status = 'independent',
                    updated_at = '2099-01-01T00:00:00+00:00'
                WHERE identity_id = 'hive-1'
                  AND group_id = 'group-1'
                """
            )

    assert store.get_evidence_source_group(
        "hive-1", "group-1"
    )["independence_status"] == "unverified"

    assert store.list_evidence_group_revisions(
        "hive-1", "group-1"
    ) == []


def test_source_group_identity_fields_are_immutable(store):
    store.create_identity("hive-1", "HIVE")
    store.create_identity("hive-2", "HIVE-2")
    store.record_evidence_source_group(
        "hive-1", "group-1", "independent"
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="identity is immutable",
    ):
        with store._connect() as conn:
            conn.execute(
                """
                UPDATE evidence_source_groups
                SET identity_id = 'hive-2'
                WHERE identity_id = 'hive-1'
                  AND group_id = 'group-1'
                """
            )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="identity is immutable",
    ):
        with store._connect() as conn:
            conn.execute(
                """
                UPDATE evidence_source_groups
                SET group_id = 'group-renamed'
                WHERE identity_id = 'hive-1'
                  AND group_id = 'group-1'
                """
            )

    assert store.get_evidence_source_group(
        "hive-1", "group-1"
    )["independence_status"] == "independent"


def test_existing_v3_database_installs_integrity_triggers(tmp_path, engine_module):
    database = tmp_path / "existing-v3.sqlite"

    first_store = engine_module.IdentityStore(database)
    first_store.create_identity("hive-1", "HIVE")
    first_store.record_evidence_source_group(
        "hive-1", "group-1", "unverified"
    )

    # Reinitializing an existing v3 database must install the triggers.
    second_store = engine_module.IdentityStore(database)

    with pytest.raises(
        sqlite3.IntegrityError,
        match="requires a matching audit revision",
    ):
        with second_store._connect() as conn:
            conn.execute(
                """
                UPDATE evidence_source_groups
                SET independence_status = 'independent',
                    updated_at = '2099-01-01T00:00:00+00:00'
                WHERE identity_id = 'hive-1'
                  AND group_id = 'group-1'
                """
            )

    assert second_store.get_evidence_source_group(
        "hive-1", "group-1"
    )["independence_status"] == "unverified"
