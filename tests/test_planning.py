import pytest

from hive.capabilities import add_capability
from hive.db import initialize
from hive.planner import PlanStep
from hive.planning import assess_plan
from hive.repositories import add_repository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setenv("HIVE_HOME", str(tmp_path))
    initialize()
    return add_repository("https://github.com/example/planning")


def test_verified_capability_produces_ready_assessment(repository):
    add_capability(
        repository,
        "browser.inspect",
        evidence_level="test_verified",
        evidence="Passing automated tests",
    )

    result = assess_plan(
        "Inspect a website",
        [
            PlanStep(
                "inspect",
                "Inspect the website",
                required_capabilities=("browser.inspect",),
            )
        ],
    )

    assert result.ready is True
    assert result.plan.ready is True
    assert result.capability_evaluation.ready is True
    assert result.missing_by_step == ()
    assert result.insufficient_by_step == ()


def test_claimed_capability_is_not_sufficient(repository):
    add_capability(
        repository,
        "browser.inspect",
        evidence_level="claimed",
    )

    result = assess_plan(
        "Inspect a website",
        [
            PlanStep(
                "inspect",
                "Inspect the website",
                required_capabilities=("browser.inspect",),
            )
        ],
    )

    assert result.plan.ready is True
    assert result.ready is False
    assert result.insufficient_by_step == (
        ("inspect", "browser.inspect"),
    )


def test_missing_capability_is_reported_separately(repository):
    result = assess_plan(
        "Inspect a website",
        [
            PlanStep(
                "inspect",
                "Inspect the website",
                required_capabilities=("browser.inspect",),
            )
        ],
    )

    assert result.ready is False
    assert result.missing_by_step == (
        ("inspect", "browser.inspect"),
    )
    assert result.insufficient_by_step == ()


def test_missing_and_insufficient_are_distinguished(repository):
    add_capability(
        repository,
        "browser.inspect",
        evidence_level="build_verified",
    )

    result = assess_plan(
        "Research and inspect",
        [
            PlanStep(
                "research",
                "Research the target",
                required_capabilities=("web.research",),
            ),
            PlanStep(
                "inspect",
                "Inspect the target",
                required_capabilities=("browser.inspect",),
            ),
        ],
    )

    assert result.ready is False
    assert result.missing_by_step == (
        ("research", "web.research"),
    )
    assert result.insufficient_by_step == (
        ("inspect", "browser.inspect"),
    )

    report = result.to_dict()
    assert report["ready"] is False
    assert report["missing_by_step"][0]["capability"] == "web.research"
    assert report["insufficient_by_step"][0]["capability"] == "browser.inspect"


def test_dependency_order_is_preserved(repository):
    add_capability(
        repository,
        "build",
        evidence_level="test_verified",
    )
    add_capability(
        repository,
        "deploy",
        evidence_level="test_verified",
    )

    result = assess_plan(
        "Build and deploy",
        [
            PlanStep(
                "deploy",
                "Deploy application",
                depends_on=("build",),
                required_capabilities=("deploy",),
            ),
            PlanStep(
                "build",
                "Build application",
                required_capabilities=("build",),
            ),
        ],
    )

    assert [
        step.step_id for step in result.plan.ordered_steps
    ] == ["build", "deploy"]
    assert result.ready is True


def test_repository_scope_is_respected(repository):
    other = add_repository("https://github.com/example/other")

    add_capability(
        other,
        "browser.inspect",
        evidence_level="test_verified",
    )

    result = assess_plan(
        "Inspect repository",
        [
            PlanStep(
                "inspect",
                "Inspect repository",
                required_capabilities=("browser.inspect",),
            )
        ],
        repository_id=repository,
    )

    assert result.ready is False
    assert result.missing_by_step == (
        ("inspect", "browser.inspect"),
    )


def test_evidence_threshold_is_configurable(repository):
    add_capability(
        repository,
        "browser.inspect",
        evidence_level="build_verified",
    )

    result = assess_plan(
        "Inspect repository",
        [
            PlanStep(
                "inspect",
                "Inspect repository",
                required_capabilities=("browser.inspect",),
            )
        ],
        minimum_evidence_level="build_verified",
    )

    assert result.ready is True


def test_assessment_does_not_write_governance_records(repository):
    from hive.db import connect
    from hive.governance_store import initialize_governance

    initialize_governance()

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

    result = assess_plan(
        "Inspect repository",
        [
            PlanStep(
                "inspect",
                "Inspect repository",
                required_capabilities=("browser.inspect",),
            )
        ],
    )

    after = counts()

    assert result.ready is False
    assert after == before
