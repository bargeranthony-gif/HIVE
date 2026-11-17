import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
MODULE_PATH = (
    ROOT / "prototypes/adaptive_identity/v02/evidence_evaluator.py"
)

spec = importlib.util.spec_from_file_location(
    "haie_evidence_evaluator",
    MODULE_PATH,
)
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)

evaluate_evidence = evaluator.evaluate_evidence


def experience(
    experience_id,
    observation="The teammate requested healing.",
    *,
    identity_id="hive-1",
    subject_id="player-1",
    interaction_type="teamwork",
    session_id=None,
    sentiment="unknown",
    confidence=0.5,
    source_type="direct_observation",
):
    return {
        "experience_id": experience_id,
        "identity_id": identity_id,
        "subject_id": subject_id,
        "interaction_type": interaction_type,
        "observation": observation,
        "sentiment": sentiment,
        "confidence": confidence,
        "source_type": source_type,
        "session_id": session_id,
    }


def test_empty_input_returns_empty_assessment():
    result = evaluate_evidence([])

    assert result["group_count"] == 0
    assert result["assessments"] == []
    assert result["read_only"] is True


def test_exact_observations_are_grouped():
    records = [
        experience("exp-1", session_id="session-a"),
        experience(
            "exp-2",
            "  THE   TEAMMATE REQUESTED HEALING. ",
            session_id="session-b",
        ),
    ]

    result = evaluate_evidence(records)
    assessment = result["assessments"][0]

    assert result["group_count"] == 1
    assert assessment["observation_count"] == 2
    assert assessment["repeated"] is True
    assert assessment["independent_session_count"] == 2


def test_same_session_does_not_count_as_independent():
    records = [
        experience("exp-1", session_id="session-a"),
        experience("exp-2", session_id="session-a"),
        experience("exp-3", session_id="session-a"),
    ]

    assessment = evaluate_evidence(records)["assessments"][0]

    assert assessment["observation_count"] == 3
    assert assessment["independent_session_count"] == 1
    assert assessment["review_status"] == (
        "insufficient_independent_sessions"
    )


def test_missing_session_ids_are_not_independent():
    records = [
        experience("exp-1"),
        experience("exp-2"),
        experience("exp-3"),
    ]

    assessment = evaluate_evidence(records)["assessments"][0]

    assert assessment["unscoped_observation_count"] == 3
    assert assessment["independent_session_count"] == 0
    assert assessment["review_status"] == (
        "insufficient_independent_sessions"
    )


def test_two_distinct_sessions_allow_owner_review():
    records = [
        experience("exp-1", session_id="session-a"),
        experience("exp-2", session_id="session-b"),
    ]

    assessment = evaluate_evidence(records)["assessments"][0]

    assert assessment["review_status"] == "eligible_for_owner_review"


def test_different_subjects_are_not_combined():
    records = [
        experience("exp-1", subject_id="player-1"),
        experience(
            "exp-2",
            subject_id="player-2",
        ),
    ]

    result = evaluate_evidence(records)

    assert result["group_count"] == 2


def test_different_interaction_types_are_not_combined():
    records = [
        experience("exp-1", interaction_type="teamwork"),
        experience("exp-2", interaction_type="conversation"),
    ]

    result = evaluate_evidence(records)

    assert result["group_count"] == 2


def test_sentiment_disagreement_is_not_called_contradiction():
    records = [
        experience(
            "exp-1",
            session_id="session-a",
            sentiment="positive",
        ),
        experience(
            "exp-2",
            session_id="session-b",
            sentiment="negative",
        ),
    ]

    assessment = evaluate_evidence(records)["assessments"][0]

    assert assessment["sentiment_disagreement"] is True
    assert assessment["contradiction_status"] == "not_assessed"


def test_provenance_and_confidence_are_preserved():
    records = [
        experience(
            "exp-1",
            session_id="session-a",
            confidence=0.4,
            source_type="direct_observation",
        ),
        experience(
            "exp-2",
            session_id="session-b",
            confidence=0.9,
            source_type="owner_feedback",
        ),
    ]

    assessment = evaluate_evidence(records)["assessments"][0]

    assert assessment["source_types"] == [
        "direct_observation",
        "owner_feedback",
    ]
    assert assessment["confidence_range"] == [0.4, 0.9]


def test_duplicate_experience_ids_are_rejected():
    records = [
        experience("exp-1", session_id="session-a"),
        experience("exp-1", session_id="session-b"),
    ]

    with pytest.raises(ValueError, match="Duplicate experience ID"):
        evaluate_evidence(records)


@pytest.mark.parametrize(
    "minimum",
    [0, -1, True, 1.5],
)
def test_invalid_session_threshold_is_rejected(minimum):
    with pytest.raises(ValueError, match="positive integer"):
        evaluate_evidence([], minimum_independent_sessions=minimum)


def test_invalid_confidence_is_rejected():
    record = experience("exp-1", confidence=1.5)

    with pytest.raises(ValueError, match="Confidence"):
        evaluate_evidence([record])


def test_invalid_sentiment_is_rejected():
    record = experience("exp-1", sentiment="hostile")

    with pytest.raises(ValueError, match="sentiment"):
        evaluate_evidence([record])


def test_input_records_are_not_modified():
    record = experience("exp-1", session_id="session-a")
    original = record.copy()

    evaluate_evidence([record])

    assert record == original
