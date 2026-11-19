import sqlite3
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from ._load_engine import _load_engine


@pytest.fixture
def store(tmp_path):
    engine = _load_engine()
    result = engine.IdentityStore(tmp_path / "revision-proposals.sqlite")
    result.create_identity("hive-1", "HIVE")
    return result


def add_trait_evidence(
    store,
    record_id,
    group_id,
    direction="increase",
    stance="supports",
    status="independent",
    interaction_type="conversation",
    subject_id=None,
    context_key="global_personality",
):
    try:
        store.get_evidence_source_group("hive-1", group_id)
    except KeyError:
        store.record_evidence_source_group(
            "hive-1", group_id, status
        )

    source_id = f"source-{record_id}"
    store.record_evidence_source(
        source_id,
        "hive-1",
        "observed_interaction",
        group_id=group_id,
    )

    if subject_id is not None:
        try:
            store.get_relationship("hive-1", subject_id)
        except KeyError:
            store.record_relationship(
                "hive-1", subject_id, subject_id
            )

    experience_id = f"experience-{record_id}"
    store.record_experience(
        experience_id,
        "hive-1",
        interaction_type,
        f"Trait evidence {record_id}",
        subject_id=subject_id,
        source_id=source_id,
    )

    store.record_claim(
        f"claim-{record_id}",
        experience_id,
        "personality_trait:humor:direction",
        direction,
        stance,
        context_key=context_key,
    )


def get_revision(store, revision_id):
    with store._connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM personality_revisions
            WHERE revision_id = ?
            """,
            (revision_id,),
        ).fetchone()
    return dict(row) if row else None


def test_two_independent_groups_create_pending_proposal(store):
    add_trait_evidence(store, "one", "group-1")
    add_trait_evidence(store, "two", "group-2")

    proposal = store.propose_personality_revision(
        "revision-1",
        "hive-1",
        "humor",
        0.6,
        "Repeated global evidence supports a modest increase.",
    )

    assert proposal["status"] == "pending"
    assert proposal["previous_value"] == 0.5
    assert proposal["proposed_value"] == 0.6
    assert proposal["baseline_profile_revision"] == 1
    assert proposal["independent_source_group_count"] == 2
    assert len(proposal["evidence"]) == 2
    assert {
        item["source_group_id"] for item in proposal["evidence"]
    } == {"group-1", "group-2"}

    # Creating a proposal must not change the personality profile.
    assert store.get_identity("hive-1")["personality"]["traits"]["humor"] == 0.5


def test_one_independent_group_is_insufficient(store):
    add_trait_evidence(store, "one", "group-1")

    with pytest.raises(ValueError, match="two independent source groups"):
        store.propose_personality_revision(
            "revision-1", "hive-1", "humor", 0.6, "Insufficient evidence."
        )

    assert get_revision(store, "revision-1") is None


def test_correlated_groups_do_not_qualify(store):
    add_trait_evidence(
        store, "one", "group-1", status="correlated"
    )
    add_trait_evidence(
        store, "two", "group-2", status="correlated"
    )

    with pytest.raises(ValueError, match="two independent source groups"):
        store.propose_personality_revision(
            "revision-1", "hive-1", "humor", 0.6, "Correlated sources."
        )


def test_subject_specific_evidence_does_not_qualify(store):
    add_trait_evidence(
        store, "one", "group-1", subject_id="person-1"
    )
    add_trait_evidence(
        store, "two", "group-2", subject_id="person-1"
    )

    with pytest.raises(ValueError, match="No global-personality evidence"):
        store.propose_personality_revision(
            "revision-1", "hive-1", "humor", 0.6, "Relationship-only evidence."
        )


def test_non_global_context_does_not_qualify(store):
    add_trait_evidence(
        store, "one", "group-1", context_key="gaming"
    )
    add_trait_evidence(
        store, "two", "group-2", context_key="gaming"
    )

    with pytest.raises(ValueError, match="No global-personality evidence"):
        store.propose_personality_revision(
            "revision-1", "hive-1", "humor", 0.6, "Context-only evidence."
        )


def test_opposing_evidence_blocks_proposal(store):
    add_trait_evidence(store, "one", "group-1", direction="increase")
    add_trait_evidence(store, "two", "group-2", direction="increase")
    add_trait_evidence(store, "three", "group-3", direction="decrease")

    with pytest.raises(ValueError, match="Opposing global-personality evidence"):
        store.propose_personality_revision(
            "revision-1", "hive-1", "humor", 0.6, "Conflicting evidence."
        )


def test_refuting_increase_counts_as_evidence_for_decrease(store):
    add_trait_evidence(
        store, "one", "group-1", direction="increase", stance="refutes"
    )
    add_trait_evidence(
        store, "two", "group-2", direction="increase", stance="refutes"
    )

    proposal = store.propose_personality_revision(
        "revision-1",
        "hive-1",
        "humor",
        0.4,
        "Independent evidence refutes an increase.",
    )

    assert proposal["status"] == "pending"
    assert proposal["previous_value"] == 0.5
    assert proposal["proposed_value"] == 0.4
    assert proposal["independent_source_group_count"] == 2


def test_evidence_is_not_pooled_across_interaction_types(store):
    add_trait_evidence(
        store, "one", "group-1", interaction_type="conversation"
    )
    add_trait_evidence(
        store, "two", "group-2", interaction_type="gameplay"
    )

    with pytest.raises(ValueError, match="within one interaction type"):
        store.propose_personality_revision(
            "revision-1", "hive-1", "humor", 0.6, "Separate evidence types."
        )


@pytest.mark.parametrize(
    "proposed_value",
    [0.5, 0.61, 1.1, -0.1, True],
)
def test_invalid_or_excessive_trait_changes_are_rejected(
    store, proposed_value
):
    with pytest.raises(ValueError):
        store.propose_personality_revision(
            "revision-1",
            "hive-1",
            "humor",
            proposed_value,
            "Invalid proposal.",
        )


def test_unknown_trait_is_rejected(store):
    with pytest.raises(ValueError, match="Unknown personality trait"):
        store.propose_personality_revision(
            "revision-1",
            "hive-1",
            "kindness",
            0.6,
            "Unknown trait.",
        )


def test_duplicate_revision_id_is_rejected(store):
    add_trait_evidence(store, "one", "group-1")
    add_trait_evidence(store, "two", "group-2")

    store.propose_personality_revision(
        "revision-1", "hive-1", "humor", 0.6, "First proposal."
    )

    with pytest.raises(sqlite3.IntegrityError):
        store.propose_personality_revision(
            "revision-1", "hive-1", "humor", 0.55, "Duplicate ID."
        )


def test_separate_identity_evidence_cannot_support_proposal(store):
    store.create_identity("hive-2", "Other HIVE")

    # Evidence belonging to a different identity is not selected by the
    # proposal query and cannot satisfy this identity's threshold.
    for index, group in enumerate(("group-1", "group-2"), start=1):
        store.record_evidence_source_group("hive-2", group, "independent")
        store.record_evidence_source(
            f"other-source-{index}",
            "hive-2",
            "observed_interaction",
            group_id=group,
        )
        store.record_experience(
            f"other-experience-{index}",
            "hive-2",
            "conversation",
            "Other identity evidence",
            source_id=f"other-source-{index}",
        )
        store.record_claim(
            f"other-claim-{index}",
            f"other-experience-{index}",
            "personality_trait:humor:direction",
            "increase",
            "supports",
            context_key="global_personality",
        )

    with pytest.raises(ValueError, match="No global-personality evidence"):
        store.propose_personality_revision(
            "revision-1", "hive-1", "humor", 0.6, "Wrong identity evidence."
        )


def create_pending_revision(store, revision_id="revision-1"):
    add_trait_evidence(store, "one", "group-1")
    add_trait_evidence(store, "two", "group-2")
    return store.propose_personality_revision(
        revision_id,
        "hive-1",
        "humor",
        0.6,
        "Independent evidence supports a modest increase.",
    )


def test_accept_revision_updates_profile_and_records_decision(store):
    create_pending_revision(store)

    result = store.accept_personality_revision(
        "revision-1", "Owner approved after reviewing the evidence."
    )

    assert result["status"] == "accepted"
    assert result["decision_reason"] == (
        "Owner approved after reviewing the evidence."
    )
    assert result["decided_at"] is not None

    identity = store.get_identity("hive-1")
    assert identity["personality"]["traits"]["humor"] == 0.6
    assert identity["personality"]["revision"] == 2


def test_reject_revision_preserves_profile(store):
    create_pending_revision(store)

    result = store.reject_personality_revision(
        "revision-1", "Evidence is not representative enough."
    )

    assert result["status"] == "rejected"
    assert result["decision_reason"] == (
        "Evidence is not representative enough."
    )
    assert result["decided_at"] is not None

    identity = store.get_identity("hive-1")
    assert identity["personality"]["traits"]["humor"] == 0.5
    assert identity["personality"]["revision"] == 1


def test_deleted_supporting_claim_invalidates_pending_revision(store):
    create_pending_revision(store)

    with store._connect() as conn:
        conn.execute(
            "DELETE FROM claims WHERE claim_id = ?",
            ("claim-one",),
        )

    # Invalidation now occurs immediately at the database deletion boundary.
    result = store.get_personality_revision("revision-1")

    assert result["status"] == "invalidated"
    assert "deleted" in result["decision_reason"].lower()
    assert result["independent_source_group_count"] == 1

    # A later approval attempt must be rejected as a terminal-state action.
    with pytest.raises(ValueError, match="not pending"):
        store.accept_personality_revision(
            "revision-1", "Attempted approval after evidence deletion."
        )

    identity = store.get_identity("hive-1")
    assert identity["personality"]["traits"]["humor"] == 0.5
    assert identity["personality"]["revision"] == 1


def test_deleted_claim_immediately_invalidates_pending_revision(store):
    create_pending_revision(store)

    with store._connect() as conn:
        conn.execute(
            "DELETE FROM claims WHERE claim_id = ?",
            ("claim-one",),
        )

    result = store.get_personality_revision("revision-1")

    assert result["status"] == "invalidated"
    assert "deleted" in result["decision_reason"].lower()
    assert result["independent_source_group_count"] == 1


def test_revision_live_group_count_excludes_deleted_evidence(store):
    create_pending_revision(store)

    before = store.get_personality_revision("revision-1")
    assert before["independent_source_group_count"] == 2

    with store._connect() as conn:
        conn.execute(
            "DELETE FROM claims WHERE claim_id = ?",
            ("claim-one",),
        )

    after = store.get_personality_revision("revision-1")
    assert after["independent_source_group_count"] == 1


def test_revision_status_filter_rejects_non_string_values(store):
    with pytest.raises(ValueError, match="Invalid personality revision status"):
        store.list_personality_revisions("hive-1", status=[])


def test_cascaded_experience_deletion_invalidates_pending_revision(store):
    create_pending_revision(store)

    with store._connect() as conn:
        conn.execute(
            "DELETE FROM experiences WHERE experience_id = ?",
            ("experience-one",),
        )

    result = store.get_personality_revision("revision-1")

    assert result["status"] == "invalidated"
    assert "deleted" in result["decision_reason"].lower()
    assert result["independent_source_group_count"] == 1

    identity = store.get_identity("hive-1")
    assert identity["personality"]["traits"]["humor"] == 0.5
    assert identity["personality"]["revision"] == 1


def test_claim_deletion_rollback_preserves_pending_revision(store):
    create_pending_revision(store)

    try:
        with store._connect() as conn:
            conn.execute(
                "DELETE FROM claims WHERE claim_id = ?",
                ("claim-one",),
            )
            raise RuntimeError("Force transaction rollback.")
    except RuntimeError as exc:
        assert str(exc) == "Force transaction rollback."

    result = store.get_personality_revision("revision-1")
    assert result["status"] == "pending"
    assert result["independent_source_group_count"] == 2

    with store._connect() as conn:
        claim = conn.execute(
            "SELECT 1 FROM claims WHERE claim_id = ?",
            ("claim-one",),
        ).fetchone()

    assert claim is not None


def test_new_opposing_evidence_invalidates_pending_revision(store):
    create_pending_revision(store)

    add_trait_evidence(
        store,
        "three",
        "group-3",
        direction="decrease",
    )

    result = store.accept_personality_revision(
        "revision-1", "Attempted approval after new evidence arrived."
    )

    assert result["status"] == "invalidated"
    assert "opposing evidence" in result["decision_reason"].lower()

    identity = store.get_identity("hive-1")
    assert identity["personality"]["traits"]["humor"] == 0.5
    assert identity["personality"]["revision"] == 1


def test_concurrent_approvals_apply_revision_only_once(store):
    add_trait_evidence(store, "one", "group-1")
    add_trait_evidence(store, "two", "group-2")

    store.propose_personality_revision(
        "revision-1",
        "hive-1",
        "humor",
        0.6,
        "Concurrent approval test.",
    )

    barrier = Barrier(2)

    def attempt_approval():
        barrier.wait(timeout=5)
        try:
            result = store.accept_personality_revision(
                "revision-1",
                "Concurrent approval attempt.",
            )
            return ("accepted", result["status"])
        except ValueError as exc:
            return ("rejected", str(exc))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt_approval),
            executor.submit(attempt_approval),
        ]
        outcomes = [future.result(timeout=15) for future in futures]

    assert sum(outcome[0] == "accepted" for outcome in outcomes) == 1
    assert sum(outcome[0] == "rejected" for outcome in outcomes) == 1

    rejected = next(
        outcome for outcome in outcomes if outcome[0] == "rejected"
    )
    assert "not pending" in rejected[1]

    revision = store.get_personality_revision("revision-1")
    assert revision["status"] == "accepted"

    identity = store.get_identity("hive-1")
    assert identity["personality"]["traits"]["humor"] == 0.6
    assert identity["personality"]["revision"] == 2


def test_revision_cannot_be_accepted_twice(store):
    create_pending_revision(store)

    store.accept_personality_revision(
        "revision-1", "First approval."
    )

    with pytest.raises(ValueError, match="not pending"):
        store.accept_personality_revision(
            "revision-1", "Second approval attempt."
        )


def test_revision_cannot_be_rejected_after_acceptance(store):
    create_pending_revision(store)

    store.accept_personality_revision(
        "revision-1", "Approved."
    )

    with pytest.raises(ValueError, match="not pending"):
        store.reject_personality_revision(
            "revision-1", "Late rejection attempt."
        )


@pytest.mark.parametrize(
    "table,column,value,record_id",
    [
        ("claims", "claim_key", "unrelated_claim", "claim-one"),
        ("claims", "context_key", "gaming", "claim-one"),
        ("claims", "claim_value", "decrease", "claim-one"),
        ("claims", "stance", "refutes", "claim-one"),
        ("experiences", "interaction_type", "gameplay", "experience-one"),
    ],
)
def test_revision_live_group_count_excludes_no_longer_qualifying_evidence(
    store, table, column, value, record_id
):
    create_pending_revision(store)

    # Table and column names are restricted to the fixed test parameters.
    key_column = (
        "claim_id" if table == "claims" else "experience_id"
    )

    with store._connect() as conn:
        conn.execute(
            f"UPDATE {table} SET {column} = ? WHERE {key_column} = ?",
            (value, record_id),
        )

    result = store.get_personality_revision("revision-1")
    assert result["independent_source_group_count"] == 1


def test_revision_retrieval_and_listing(store):
    create_pending_revision(store)

    retrieved = store.get_personality_revision("revision-1")
    pending = store.list_personality_revisions(
        "hive-1", status="pending"
    )
    accepted = store.list_personality_revisions(
        "hive-1", status="accepted"
    )

    assert retrieved["revision_id"] == "revision-1"
    assert len(retrieved["evidence"]) == 2
    assert len(pending) == 1
    assert pending[0]["revision_id"] == "revision-1"
    assert accepted == []


def test_source_downgrade_proactively_invalidates_pending_revision(store):
    create_pending_revision(store)

    revised_group = store.revise_evidence_source_group(
        "hive-1",
        "group-1",
        "correlated",
        "Sources were found to share a common origin.",
    )

    result = store.get_personality_revision("revision-1")

    assert revised_group["independence_status"] == "correlated"
    assert result["status"] == "invalidated"
    assert "lost independent status" in result["decision_reason"]


def test_profile_update_proactively_invalidates_pending_revision(store):
    create_pending_revision(store)

    store.update_personality_profile(
        "hive-1",
        descriptors={"communication_style": "more concise"},
    )

    result = store.get_personality_revision("revision-1")

    assert result["status"] == "invalidated"
    assert "profile changed" in result["decision_reason"].lower()


def test_forgetting_subject_invalidates_any_linked_pending_revision(store):
    create_pending_revision(store)

    add_trait_evidence(
        store,
        "subject",
        "group-subject",
        subject_id="person-1",
    )

    # Current proposal creation rejects subject-specific evidence. This
    # manually constructed link tests the defensive deletion safeguard.
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO revision_evidence (
                evidence_link_id, revision_id, claim_id,
                original_claim_id, source_group_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "defensive-link",
                "revision-1",
                "claim-subject",
                "claim-subject",
                "group-subject",
                "2026-11-17T00:00:00+00:00",
            ),
        )

    result = store.forget_subject("hive-1", "person-1")
    revision = store.get_personality_revision("revision-1")

    assert result["relationship_deleted"] is True
    assert revision["status"] == "invalidated"
    assert "subject-specific evidence" in revision["decision_reason"].lower()
