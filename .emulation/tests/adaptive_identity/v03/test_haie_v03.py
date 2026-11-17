import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROTO = ROOT / "prototypes/adaptive_identity/v03"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, PROTO / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = load("haie_v03_engine", "identity_engine.py")
evaluator = load("haie_v03_evaluator", "evidence_evaluator.py")
service_module = load("haie_v03_service", "evidence_service.py")


def make_claim(
    claim_id,
    experience_id,
    session,
    stance,
    *,
    context="friends",
    subject="person-1",
):
    return {
        "claim_id": claim_id,
        "experience_id": experience_id,
        "identity_id": "hive-1",
        "subject_id": subject,
        "interaction_type": "conversation",
        "session_id": session,
        "claim_key": "initiates_conversations",
        "claim_value": "regularly",
        "stance": stance,
        "context_key": context,
        "confidence": 0.8,
    }


def test_independent_supporting_sessions_are_eligible():
    result = evaluator.evaluate_claims([
        make_claim("c1", "e1", "s1", "supports"),
        make_claim("c2", "e2", "s2", "supports"),
    ])
    item = result["assessments"][0]
    assert item["supporting_session_count"] == 2
    assert item["review_status"] == "eligible_for_owner_review"
    assert result["read_only"] is True


def test_opposing_independent_sessions_detect_contradiction():
    result = evaluator.evaluate_claims([
        make_claim("c1", "e1", "s1", "supports"),
        make_claim("c2", "e2", "s2", "refutes"),
    ])
    item = result["assessments"][0]
    assert item["contradiction_status"] == "contradiction_detected"
    assert item["review_status"] == "conflict_requires_owner_review"


def test_duplicate_records_in_one_session_count_once():
    result = evaluator.evaluate_claims([
        make_claim("c1", "e1", "s1", "supports"),
        make_claim("c2", "e2", "s1", "supports"),
    ])
    item = result["assessments"][0]
    assert item["supporting_session_count"] == 1
    assert item["review_status"] == "insufficient_independent_sessions"


def test_conflicting_stances_inside_one_session_are_excluded():
    result = evaluator.evaluate_claims([
        make_claim("c1", "e1", "s1", "supports"),
        make_claim("c2", "e2", "s1", "refutes"),
        make_claim("c3", "e3", "s2", "supports"),
    ])
    item = result["assessments"][0]
    assert item["internally_conflicted_sessions"] == ["s1"]
    assert item["supporting_session_count"] == 1
    assert item["refuting_session_count"] == 0


def test_different_contexts_are_not_combined():
    result = evaluator.evaluate_claims([
        make_claim("c1", "e1", "s1", "supports", context="friends"),
        make_claim("c2", "e2", "s2", "refutes", context="work"),
    ])
    assert result["group_count"] == 2
    assert all(
        item["contradiction_status"] == "no_conflict_observed"
        for item in result["assessments"]
    )


def test_unscoped_evidence_does_not_count_as_independent():
    claim = make_claim("c1", "e1", None, "supports")
    result = evaluator.evaluate_claims([claim])
    item = result["assessments"][0]
    assert item["supporting_session_count"] == 0
    assert item["unscoped_observation_count"] == 1


def test_uncertain_evidence_does_not_support_or_refute():
    result = evaluator.evaluate_claims([
        make_claim("c1", "e1", "s1", "uncertain"),
    ])
    item = result["assessments"][0]
    assert item["uncertain_session_count"] == 1
    assert item["supporting_session_count"] == 0
    assert item["refuting_session_count"] == 0


def test_context_and_subject_are_part_of_group_identity():
    result = evaluator.evaluate_claims([
        make_claim("c1", "e1", "s1", "supports", subject="person-1"),
        make_claim("c2", "e2", "s2", "refutes", subject="person-2"),
    ])
    assert result["group_count"] == 2


def test_invalid_claim_is_rejected():
    claim = make_claim("c1", "e1", "s1", "maybe")
    try:
        evaluator.evaluate_claims([claim])
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid stance was accepted.")


def test_duplicate_claim_ids_are_rejected():
    claim = make_claim("same", "e1", "s1", "supports")
    other = make_claim("same", "e2", "s2", "supports")
    try:
        evaluator.evaluate_claims([claim, other])
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate claim IDs were accepted.")


def test_database_claim_storage_and_service(tmp_path):
    store = engine.IdentityStore(tmp_path / "haie-v03.sqlite")
    store.create_identity("hive-1", "HIVE")

    store.record_experience(
        "e1", "hive-1", "conversation", "Observed initiation",
        subject_id="person-1", session_id="s1",
    )
    store.record_experience(
        "e2", "hive-1", "conversation", "Observed initiation",
        subject_id="person-1", session_id="s2",
    )

    store.record_claim(
        "c1", "e1", "initiates_conversations", "regularly",
        "supports", context_key="friends", confidence=0.8,
    )
    store.record_claim(
        "c2", "e2", "initiates_conversations", "regularly",
        "refutes", context_key="friends", confidence=0.7,
    )

    service = service_module.EvidenceService(store)
    result = service.assess_subject("hive-1", "person-1")

    assert result["group_count"] == 1
    assert result["assessments"][0]["contradiction_status"] == (
        "contradiction_detected"
    )

    assert store.get_identity("hive-1")["adaptive"] == {}


def test_forgetting_subject_cascades_to_claims(tmp_path):
    store = engine.IdentityStore(tmp_path / "haie-v03-forget.sqlite")
    store.create_identity("hive-1", "HIVE")
    store.record_experience(
        "e1", "hive-1", "conversation", "Observed initiation",
        subject_id="person-1", session_id="s1",
    )
    store.record_claim(
        "c1", "e1", "initiates_conversations", "regularly",
        "supports",
    )

    store.forget_subject("hive-1", "person-1")

    try:
        store.get_claim("c1")
    except KeyError:
        pass
    else:
        raise AssertionError("Claim survived deletion of its experience.")


def test_unknown_identity_is_not_silently_treated_as_empty(tmp_path):
    store = engine.IdentityStore(tmp_path / "unknown-identity.sqlite")
    store.create_identity("hive-1", "HIVE")
    service = service_module.EvidenceService(store)
    try:
        service.assess_identity("missing")
    except KeyError:
        pass
    else:
        raise AssertionError("Unknown identity was silently accepted.")
