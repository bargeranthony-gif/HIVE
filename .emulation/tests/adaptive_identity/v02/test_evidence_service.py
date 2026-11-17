import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
PROTOTYPE = ROOT / "prototypes/adaptive_identity/v02"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, PROTOTYPE / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = load_module("haie_service_engine", "identity_engine.py")
service_module = load_module("haie_evidence_service", "evidence_service.py")

IdentityStore = engine.IdentityStore
EvidenceService = service_module.EvidenceService


@pytest.fixture
def setup(tmp_path):
    store = IdentityStore(tmp_path / "service.sqlite3")
    store.create_identity("hive-1", "HIVE")

    store.record_experience(
        "exp-1",
        "hive-1",
        "teamwork",
        "Teammate requested healing.",
        subject_id="player-1",
        session_id="session-a",
        observation="Teammate requested healing.",
        source_type="direct_observation",
    )

    store.record_experience(
        "exp-2",
        "hive-1",
        "teamwork",
        "Teammate requested healing again.",
        subject_id="player-1",
        session_id="session-b",
        observation="Teammate requested healing.",
        source_type="direct_observation",
    )

    store.record_experience(
        "exp-3",
        "hive-1",
        "conversation",
        "Different player interaction.",
        subject_id="player-2",
        session_id="session-c",
    )

    return store, EvidenceService(store)


def test_assess_identity_uses_persisted_records(setup):
    store, service = setup

    result = service.assess_identity("hive-1")

    assert result["group_count"] == 2

    teamwork = next(
        item for item in result["assessments"]
        if item["interaction_type"] == "teamwork"
    )

    assert teamwork["observation_count"] == 2
    assert teamwork["independent_session_count"] == 2
    assert teamwork["review_status"] == "eligible_for_owner_review"


def test_assess_subject_filters_results(setup):
    store, service = setup

    result = service.assess_subject("hive-1", "player-1")

    assert result["group_count"] == 1
    assert result["assessments"][0]["subject_id"] == "player-1"


def test_assessment_does_not_modify_experiences(setup):
    store, service = setup

    before = store.list_experiences("hive-1")
    service.assess_identity("hive-1")
    after = store.list_experiences("hive-1")

    assert before == after


def test_unknown_identity_returns_empty_assessment(setup):
    store, service = setup

    result = service.assess_identity("unknown")

    assert result["group_count"] == 0


def test_empty_identity_id_is_rejected(setup):
    store, service = setup

    with pytest.raises(ValueError):
        service.assess_identity(" ")


def test_empty_subject_id_is_rejected(setup):
    store, service = setup

    with pytest.raises(ValueError):
        service.assess_subject("hive-1", " ")
