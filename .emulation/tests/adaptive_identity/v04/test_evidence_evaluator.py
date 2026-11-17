"""Tests for the read-only HAIE v0.4 evidence evaluator."""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from ._load_engine import _load_engine


def _load_evaluator():
    path = (
        Path(__file__).parents[3]
        / "prototypes"
        / "adaptive_identity"
        / "v04"
        / "evidence_evaluator.py"
    )
    spec = importlib.util.spec_from_file_location(
        "haie_v04_evidence_evaluator",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EvidenceEvaluator


@pytest.fixture
def engine_module():
    return _load_engine()


@pytest.fixture
def evaluator_class():
    return _load_evaluator()


@pytest.fixture
def store(tmp_path, engine_module):
    result = engine_module.IdentityStore(tmp_path / "haie-evaluator.sqlite")
    result.create_identity("hive-1", "HIVE")
    return result


@pytest.fixture
def evaluator(store, evaluator_class):
    return evaluator_class(store.database_path)


def _add_record(
    store,
    record_id,
    group_id="group-1",
    status="independent",
    value="tea",
    stance="supports",
    session_id=None,
    source=True,
    identity_id="hive-1",
    subject_id=None,
    claim_key="preferred beverage",
    context_key="general",
    interaction_type="conversation",
):
    if group_id is not None:
        try:
            store.get_evidence_source_group(identity_id, group_id)
        except KeyError:
            store.record_evidence_source_group(
                identity_id, group_id, status
            )

    source_id = None

    if source:
        source_id = f"source-{record_id}"
        store.record_evidence_source(
            source_id=source_id,
            identity_id=identity_id,
            source_type="observed_interaction",
            group_id=group_id,
        )

    experience_id = f"experience-{record_id}"
    store.record_experience(
        experience_id=experience_id,
        identity_id=identity_id,
        interaction_type=interaction_type,
        summary=f"Evidence record {record_id}",
        subject_id=subject_id,
        session_id=session_id,
        source_id=source_id,
    )

    store.record_claim(
        claim_id=f"claim-{record_id}",
        experience_id=experience_id,
        claim_key=claim_key,
        claim_value=value,
        stance=stance,
        context_key=context_key,
    )


def _only_assessment(result):
    assert result["proposition_count"] == 1
    return result["assessments"][0]


def test_repeated_sessions_from_one_group_count_as_one_origin(
    store, evaluator
):
    _add_record(store, "one", session_id="session-1")
    _add_record(store, "two", session_id="session-2")

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["experience_count"] == 2
    assert assessment["distinct_session_count"] == 2
    assert assessment["distinct_source_group_count"] == 1
    assert assessment["independent_source_group_count"] == 1
    assert assessment["supporting_independent_source_count"] == 1
    assert assessment["review_eligible"] is False


def test_two_independent_groups_meet_review_threshold(store, evaluator):
    _add_record(store, "one", group_id="group-1")
    _add_record(store, "two", group_id="group-2")

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["independent_source_group_count"] == 2
    assert assessment["supporting_independent_source_count"] == 2
    assert assessment["contradiction_detected"] is False
    assert assessment["review_eligible"] is True


@pytest.mark.parametrize("status", ["correlated", "unverified"])
def test_non_independent_groups_receive_no_independent_credit(
    store, evaluator, status
):
    _add_record(store, "one", group_id="group-1", status=status)
    _add_record(store, "two", group_id="group-2", status=status)

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["independent_source_group_count"] == 0
    assert assessment["supporting_independent_source_count"] == 0
    assert assessment["review_eligible"] is False


def test_missing_provenance_receives_no_independent_credit(
    store, evaluator
):
    _add_record(store, "one", group_id=None, source=False)
    _add_record(store, "two", group_id=None, source=True)

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["distinct_source_group_count"] == 0
    assert assessment["independent_source_group_count"] == 0
    assert assessment["missing_provenance_record_count"] == 2
    assert assessment["review_eligible"] is False


def test_independent_groups_supporting_competing_values_create_contradiction(
    store, evaluator
):
    _add_record(
        store, "one", group_id="group-1", value="tea"
    )
    _add_record(
        store, "two", group_id="group-2", value="coffee"
    )

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["contradiction_detected"] is True
    assert assessment["review_eligible"] is True
    assert assessment["independent_conflicts"]
    assert assessment["independent_conflicts"][0]["type"] == (
        "competing_supported_values"
    )


def test_conflicting_claims_within_one_group_are_source_level_conflicts(
    store, evaluator
):
    _add_record(
        store, "one", group_id="group-1", value="tea"
    )
    _add_record(
        store, "two", group_id="group-1", value="coffee"
    )

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["source_level_conflicts"]
    assert assessment["contradiction_detected"] is False
    assert assessment["independent_conflicts"] == []
    assert assessment["review_eligible"] is False


def test_opposing_stances_from_independent_groups_create_contradiction(
    store, evaluator
):
    _add_record(
        store, "one", group_id="group-1",
        value="tea", stance="supports",
    )
    _add_record(
        store, "two", group_id="group-2",
        value="tea", stance="refutes",
    )

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["contradiction_detected"] is True
    assert any(
        conflict["type"] == "opposing_stances"
        for conflict in assessment["independent_conflicts"]
    )


def test_uncertain_claims_do_not_count_directionally(store, evaluator):
    _add_record(
        store, "one", group_id="group-1", stance="uncertain"
    )
    _add_record(
        store, "two", group_id="group-2", stance="uncertain"
    )

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["uncertain_evidence_count"] == 2
    assert assessment["supporting_independent_source_count"] == 0
    assert assessment["refuting_independent_source_count"] == 0
    assert assessment["review_eligible"] is False


def test_claim_normalization_collapses_whitespace_and_case(
    store, evaluator
):
    _add_record(
        store, "one",
        group_id="group-1",
        value="  TEA   ",
        claim_key=" Preferred   Beverage ",
        context_key="At\tHome",
    )
    _add_record(
        store, "two",
        group_id="group-2",
        value="tea",
        claim_key="preferred beverage",
        context_key="at home",
    )

    result = evaluator.evaluate("hive-1")

    assert result["proposition_count"] == 1
    assessment = result["assessments"][0]

    assert assessment["claim_key"] == "preferred beverage"
    assert assessment["context_key"] == "at home"
    assert assessment["values"][0]["normalized_value"] == "tea"
    assert assessment["supporting_independent_source_count"] == 2
    assert assessment["contradiction_detected"] is False


def test_identity_boundaries_are_preserved(
    store, evaluator, engine_module
):
    store.create_identity("hive-2", "HIVE-2")

    _add_record(
        store, "one", identity_id="hive-1",
        group_id="group-1", value="tea",
    )
    _add_record(
        store, "two", identity_id="hive-2",
        group_id="group-2", value="coffee",
    )

    result = evaluator.evaluate("hive-1")

    assert result["proposition_count"] == 1
    assert result["assessments"][0]["values"][0]["normalized_value"] == "tea"


def test_unknown_identity_is_rejected(evaluator):
    with pytest.raises(KeyError):
        evaluator.evaluate("missing-identity")


def test_invalid_minimum_independent_groups_is_rejected(
    evaluator_class, store
):
    for invalid in (True, 1, 0, -1, 2.5, "2"):
        with pytest.raises(ValueError):
            evaluator_class(
                store.database_path,
                minimum_independent_groups=invalid,
            )


def test_evaluation_does_not_modify_database(
    store, evaluator
):
    before = store.database_path.read_bytes()

    evaluator.evaluate("hive-1")

    after = store.database_path.read_bytes()

    assert after == before


def test_evaluator_connection_is_read_only(evaluator):
    with evaluator._connect_read_only() as conn:
        with pytest.raises(
            sqlite3.OperationalError,
            match="readonly",
        ):
            conn.execute(
                "INSERT INTO identities "
                "(identity_id, display_name, created_at, updated_at) "
                "VALUES ('unauthorized', 'Unauthorized', 'now', 'now')"
            )



def test_conflicted_group_cannot_create_false_independent_contradiction(
    store, evaluator
):
    _add_record(
        store, "one", group_id="group-1", value="tea"
    )
    _add_record(
        store, "two", group_id="group-1", value="coffee"
    )
    _add_record(
        store, "three", group_id="group-2", value="tea"
    )

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["source_level_conflicts"]
    assert assessment["contradiction_detected"] is False
    assert assessment["independent_conflicts"] == []
    assert assessment["supporting_independent_source_count"] == 1
    assert assessment["review_eligible"] is False


def test_conflicted_group_is_excluded_from_opposing_stance_detection(
    store, evaluator
):
    _add_record(
        store, "one", group_id="group-1",
        value="tea", stance="supports",
    )
    _add_record(
        store, "two", group_id="group-1",
        value="tea", stance="refutes",
    )
    _add_record(
        store, "three", group_id="group-2",
        value="tea", stance="supports",
    )

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["source_level_conflicts"]
    assert assessment["contradiction_detected"] is False
    assert assessment["independent_conflicts"] == []


def test_subject_specific_evidence_is_isolated(
    store, evaluator
):
    store.record_relationship("hive-1", "person-a", "Person A")
    store.record_relationship("hive-1", "person-b", "Person B")

    _add_record(
        store, "one", group_id="group-1",
        subject_id="person-a", value="tea",
    )
    _add_record(
        store, "two", group_id="group-2",
        subject_id="person-b", value="coffee",
    )

    result = evaluator.evaluate("hive-1", subject_id="person-a")

    assert result["proposition_count"] == 1
    assessment = result["assessments"][0]
    assert assessment["subject_id"] == "person-a"
    assert assessment["values"][0]["normalized_value"] == "tea"


def test_confidence_ranges_are_reported_separately(
    store, evaluator
):
    _add_record(store, "one")

    assessment = _only_assessment(evaluator.evaluate("hive-1"))

    assert assessment["descriptive_claim_confidence_range"] == {
        "minimum": 1.0,
        "maximum": 1.0,
    }
    assert assessment["descriptive_experience_confidence_range"] == {
        "minimum": 1.0,
        "maximum": 1.0,
    }
    assert "descriptive_confidence_range" not in assessment
