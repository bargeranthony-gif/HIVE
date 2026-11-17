import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]

def load_engine(name, relative_path):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.IdentityStore


V1Store = load_engine(
    "haie_v1_engine",
    Path("prototypes/adaptive_identity/identity_engine.py"),
)

V2Store = load_engine(
    "haie_v2_engine",
    Path("prototypes/adaptive_identity/v02/identity_engine.py"),
)


@pytest.fixture
def store(tmp_path):
    instance = V2Store(tmp_path / "haie_v2.sqlite3")
    instance.create_identity("hive-1", "HIVE")
    return instance


def test_schema_version_is_two(tmp_path):
    path = tmp_path / "haie.sqlite3"
    V2Store(path)

    import sqlite3
    with sqlite3.connect(path) as conn:
        version = conn.execute(
            "SELECT version FROM haie_schema WHERE schema_id = 1"
        ).fetchone()[0]

    assert version == 2


def test_new_experience_preserves_separate_evidence_fields(store):
    result = store.record_experience(
        "exp-1",
        "hive-1",
        "teamwork",
        "A teammate requested regular healing.",
        subject_id="player-1",
        session_id="session-1",
        observation="The teammate requested healing three times.",
        interpretation="The teammate may value dependable support.",
        outcome="The team completed the encounter.",
        sentiment="positive",
        confidence=0.85,
        source_type="direct_observation",
        source_reference="session-log-001",
    )

    assert result["observation"] == (
        "The teammate requested healing three times."
    )
    assert result["interpretation"] == (
        "The teammate may value dependable support."
    )
    assert result["outcome"] == "The team completed the encounter."
    assert result["session_id"] == "session-1"
    assert result["sentiment"] == "positive"
    assert result["confidence"] == 0.85
    assert result["source_type"] == "direct_observation"
    assert result["source_reference"] == "session-log-001"


def test_legacy_summary_becomes_observation(store):
    result = store.record_experience(
        "exp-1",
        "hive-1",
        "conversation",
        "A teammate shared a preferred playstyle.",
    )

    assert result["observation"] == result["summary"]
    assert result["interpretation"] is None
    assert result["sentiment"] == "unknown"
    assert result["confidence"] == 0.5
    assert result["source_type"] == "unspecified"


def test_sessions_are_stored_separately(store):
    store.record_experience(
        "exp-1", "hive-1", "teamwork", "First session",
        session_id="session-a",
    )
    store.record_experience(
        "exp-2", "hive-1", "teamwork", "Second session",
        session_id="session-b",
    )

    records = store.list_experiences("hive-1")

    assert [item["session_id"] for item in records] == [
        "session-a", "session-b"
    ]


@pytest.mark.parametrize("confidence", [-0.01, 1.01, True, "high"])
def test_invalid_confidence_is_rejected(store, confidence):
    with pytest.raises(ValueError, match="Confidence"):
        store.record_experience(
            "exp-1",
            "hive-1",
            "conversation",
            "Test observation",
            confidence=confidence,
        )


def test_invalid_sentiment_is_rejected(store):
    with pytest.raises(ValueError, match="sentiment"):
        store.record_experience(
            "exp-1",
            "hive-1",
            "conversation",
            "Test observation",
            sentiment="extreme",
        )


def test_empty_source_type_is_rejected(store):
    with pytest.raises(ValueError, match="Source type"):
        store.record_experience(
            "exp-1",
            "hive-1",
            "conversation",
            "Test observation",
            source_type=" ",
        )


def test_observation_cannot_be_empty(store):
    with pytest.raises(ValueError, match="Observation"):
        store.record_experience(
            "exp-1",
            "hive-1",
            "conversation",
            "Original summary",
            observation=" ",
        )


def test_v1_database_migrates_without_losing_experiences(tmp_path):
    path = tmp_path / "legacy.sqlite3"

    old_store = V1Store(path)
    old_store.create_identity("hive-1", "HIVE")
    old_store.record_experience(
        "legacy-1",
        "hive-1",
        "conversation",
        "A legacy experience from v0.1.",
        subject_id="player-1",
    )

    upgraded_store = V2Store(path)
    migrated = upgraded_store.get_experience("legacy-1")

    assert migrated["summary"] == "A legacy experience from v0.1."
    assert migrated["observation"] == "A legacy experience from v0.1."
    assert migrated["interpretation"] is None
    assert migrated["session_id"] is None
    assert migrated["sentiment"] == "unknown"
    assert migrated["confidence"] == 0.5
    assert migrated["source_type"] == "unspecified"

    identity = upgraded_store.get_identity("hive-1")
    assert identity["display_name"] == "HIVE"


def test_v2_database_can_be_reopened(tmp_path):
    path = tmp_path / "persistent.sqlite3"

    first = V2Store(path)
    first.create_identity("hive-1", "HIVE")
    first.record_experience(
        "exp-1",
        "hive-1",
        "teamwork",
        "A stored observation.",
        session_id="session-1",
        confidence=0.9,
    )

    second = V2Store(path)
    result = second.get_experience("exp-1")

    assert result["session_id"] == "session-1"
    assert result["confidence"] == 0.9
