import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).parents[2]
    / "prototypes"
    / "adaptive_identity"
    / "identity_engine.py"
)

spec = importlib.util.spec_from_file_location(
    "hive_adaptive_identity",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

IdentityStore = module.IdentityStore


@pytest.fixture
def store(tmp_path):
    instance = IdentityStore(tmp_path / "identity.sqlite3")
    instance.create_identity("hive-1", "HIVE")
    return instance


def add_three_experiences(store):
    ids = ["exp-1", "exp-2", "exp-3"]
    for number, experience_id in enumerate(ids, start=1):
        store.record_experience(
            experience_id,
            "hive-1",
            "multiplayer_interaction",
            f"Meaningful interaction {number}",
            subject_id="player-1",
            tags=["teamwork"],
        )
    return ids


def test_identity_persists_across_store_instances(tmp_path):
    path = tmp_path / "identity.sqlite3"
    first = IdentityStore(path)
    first.create_identity("hive-1", "HIVE")

    second = IdentityStore(path)
    identity = second.get_identity("hive-1")

    assert identity["display_name"] == "HIVE"
    assert identity["baseline"]["humor"] == 0.5
    assert identity["adaptive"] == {}


def test_experiences_and_social_memory_are_persisted(store):
    store.record_experience(
        "exp-1",
        "hive-1",
        "conversation",
        "A teammate shared a preferred playstyle.",
        subject_id="player-1",
    )
    store.update_social_contact(
        "hive-1",
        "player-1",
        display_name="Player One",
        notes="Prefers cooperative play.",
    )

    contact = store.get_social_contact("hive-1", "player-1")

    assert contact["display_name"] == "Player One"
    assert contact["interaction_count"] == 1
    assert contact["notes"] == "Prefers cooperative play."
    assert len(store.list_experiences("hive-1")) == 1


def test_personality_revision_requires_three_experiences(store):
    store.record_experience(
        "exp-1", "hive-1", "conversation", "A useful interaction."
    )
    store.record_experience(
        "exp-2", "hive-1", "conversation", "Another useful interaction."
    )

    with pytest.raises(ValueError, match="three distinct"):
        store.propose_personality_revision(
            "rev-1",
            "hive-1",
            {"humor": 0.55},
            "Repeated positive feedback.",
            ["exp-1", "exp-2"],
        )


def test_personality_revision_requires_valid_evidence(store):
    with pytest.raises(ValueError, match="must exist"):
        store.propose_personality_revision(
            "rev-1",
            "hive-1",
            {"humor": 0.55},
            "Evidence must exist.",
            ["missing-1", "missing-2", "missing-3"],
        )


def test_personality_changes_only_after_explicit_acceptance(store):
    evidence = add_three_experiences(store)

    proposal = store.propose_personality_revision(
        "rev-1",
        "hive-1",
        {"humor": 0.55},
        "Repeated positive social interactions support a small adjustment.",
        evidence,
    )

    assert proposal["status"] == "pending"
    assert store.get_identity("hive-1")["adaptive"] == {}

    updated = store.accept_revision("rev-1")

    assert updated["adaptive"]["humor"] == 0.55
    assert store.get_revision("rev-1")["status"] == "accepted"


def test_rejected_revision_does_not_change_personality(store):
    evidence = add_three_experiences(store)

    store.propose_personality_revision(
        "rev-1",
        "hive-1",
        {"playfulness": 0.55},
        "Repeated playful interactions.",
        evidence,
    )
    store.reject_revision("rev-1")

    assert store.get_identity("hive-1")["adaptive"] == {}
    assert store.get_revision("rev-1")["status"] == "rejected"


def test_single_revision_cannot_make_large_personality_change(store):
    evidence = add_three_experiences(store)

    with pytest.raises(ValueError, match="0.10"):
        store.propose_personality_revision(
            "rev-1",
            "hive-1",
            {"competitiveness": 0.90},
            "Attempted excessive change.",
            evidence,
        )


def test_forgetting_subject_removes_contact_and_experiences(store):
    store.record_experience(
        "exp-1",
        "hive-1",
        "conversation",
        "Stored social interaction.",
        subject_id="player-1",
    )

    store.forget_subject("hive-1", "player-1")

    assert store.list_experiences("hive-1") == []
    with pytest.raises(KeyError):
        store.get_social_contact("hive-1", "player-1")


def test_personality_traits_cannot_modify_unknown_fields(store):
    evidence = add_three_experiences(store)

    with pytest.raises(ValueError, match="Unknown personality traits"):
        store.propose_personality_revision(
            "rev-1",
            "hive-1",
            {"authorization": 1.0},
            "This must not alter governance.",
            evidence,
        )


def test_revision_cannot_be_accepted_twice(store):
    evidence = add_three_experiences(store)

    store.propose_personality_revision(
        "rev-1",
        "hive-1",
        {"humor": 0.55},
        "Repeated positive interactions.",
        evidence,
    )
    store.accept_revision("rev-1")

    with pytest.raises(ValueError, match="pending"):
        store.accept_revision("rev-1")
