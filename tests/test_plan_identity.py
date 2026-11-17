import pytest

from hive.capabilities import add_capability
from hive.db import initialize
from hive.planner import PlanStep
from hive.planning import assess_plan
from hive.plan_identity import create_plan_identity
from hive.repositories import add_repository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setenv("HIVE_HOME", str(tmp_path))
    initialize()
    return add_repository("https://github.com/example/identity")


def make_assessment(repository):
    add_capability(
        repository,
        "browser.inspect",
        description="Browser inspection",
        evidence_level="test_verified",
        evidence="Automated integration test passed",
    )

    return assess_plan(
        "Inspect a website",
        [
            PlanStep(
                "inspect",
                "Inspect the target website",
                required_capabilities=("browser.inspect",),
            )
        ],
        repository_id=repository,
    )


def test_identity_is_deterministic(repository):
    assessment = make_assessment(repository)

    first = create_plan_identity(assessment, repository)
    second = create_plan_identity(assessment, repository)

    assert first.digest == second.digest
    assert first.canonical_json == second.canonical_json
    assert len(first.digest) == 64


def test_identity_contains_repository_and_capability_snapshot(repository):
    assessment = make_assessment(repository)
    identity = create_plan_identity(assessment, repository)
    snapshot = identity.snapshot

    assert snapshot["repository"]["id"] == repository
    assert snapshot["repository"]["url"] == (
        "https://github.com/example/identity"
    )
    assert snapshot["minimum_evidence_level"] == "test_verified"
    assert snapshot["capability_records"][0]["name"] == "browser.inspect"
    assert snapshot["capability_records"][0]["evidence"] == (
        "Automated integration test passed"
    )


def test_relevant_capability_change_changes_digest(repository):
    assessment = make_assessment(repository)
    original = create_plan_identity(assessment, repository)

    add_capability(
        repository,
        "browser.inspect",
        description="Additional verification",
        evidence_level="benchmarked",
        evidence="Benchmark run completed",
    )

    updated = create_plan_identity(assessment, repository)

    assert updated.digest != original.digest


def test_other_repository_capabilities_do_not_change_identity(repository):
    assessment = make_assessment(repository)
    original = create_plan_identity(assessment, repository)

    other = add_repository("https://github.com/example/unrelated")
    add_capability(
        other,
        "unrelated.capability",
        evidence_level="benchmarked",
        evidence="Unrelated evidence",
    )

    unchanged = create_plan_identity(assessment, repository)

    assert unchanged.digest == original.digest


def test_repository_scope_is_mandatory(repository):
    assessment = make_assessment(repository)

    with pytest.raises(ValueError, match="repository_id"):
        create_plan_identity(assessment, None)


def test_unknown_repository_is_rejected(repository):
    assessment = make_assessment(repository)

    with pytest.raises(ValueError, match="Repository not found"):
        create_plan_identity(assessment, 999999)


def test_unready_assessment_is_rejected(repository):
    assessment = assess_plan(
        "Inspect a website",
        [
            PlanStep(
                "inspect",
                "Inspect the target website",
                required_capabilities=("browser.inspect",),
            )
        ],
        repository_id=repository,
    )

    with pytest.raises(ValueError, match="not ready"):
        create_plan_identity(assessment, repository)


def test_identity_creation_does_not_write_governance_records(repository):
    from hive.db import connect

    assessment = make_assessment(repository)

    tables = (
        "action_approvals",
        "governance_decisions",
        "execution_records",
        "audit_events",
    )

    def counts():
        with connect() as conn:
            return {
                table: conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in tables
            }

    before = counts()
    create_plan_identity(assessment, repository)
    after = counts()

    assert after == before


def test_identity_snapshot_is_defensive_copy(repository):
    assessment = make_assessment(repository)
    identity = create_plan_identity(assessment, repository)

    snapshot = identity.snapshot
    snapshot["repository"]["url"] = "https://example.invalid/changed"

    assert identity.snapshot["repository"]["url"] == identity.repository_url


def test_identity_evaluates_exact_records_used_in_snapshot(
    repository,
    monkeypatch,
):
    import hive.plan_identity as identity_module

    assessment = make_assessment(repository)

    original_evaluator = identity_module.evaluate_capability_records
    evaluated_records = []

    def recording_evaluator(required, records, minimum_level):
        records = tuple(records)
        evaluated_records.extend(records)

        return original_evaluator(
            required,
            records,
            minimum_level,
        )

    monkeypatch.setattr(
        identity_module,
        "evaluate_capability_records",
        recording_evaluator,
    )

    identity = create_plan_identity(assessment, repository)

    relevant_records = sorted(
        (
            record
            for record in evaluated_records
            if record.name in {
                capability
                for step in assessment.plan.ordered_steps
                for capability in step.required_capabilities
            }
        ),
        key=lambda record: (record.name, record.id),
    )

    expected_snapshot = [
        {
            "id": record.id,
            "repository_id": record.repository_id,
            "name": record.name,
            "description": record.description,
            "evidence_level": record.evidence_level,
            "evidence": record.evidence,
        }
        for record in relevant_records
    ]

    assert identity.snapshot["capability_records"] == expected_snapshot
    assert evaluated_records
