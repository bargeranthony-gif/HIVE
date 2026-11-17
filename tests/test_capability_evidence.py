import pytest

from hive.capabilities import (
    add_capability,
    evaluate_capabilities,
    get_capabilities,
)
from hive.db import initialize
from hive.repositories import add_repository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setenv("HIVE_HOME", str(tmp_path))
    initialize()
    return add_repository("https://github.com/example/capabilities")


def test_get_capabilities_returns_structured_records(repository):
    add_capability(
        repository,
        "browser.inspect",
        evidence_level="test_verified",
        evidence="Automated integration test",
    )

    records = get_capabilities(repository)

    assert len(records) == 1
    assert records[0].name == "browser.inspect"
    assert records[0].evidence_level == "test_verified"
    assert records[0].evidence == "Automated integration test"


def test_default_threshold_rejects_build_verified(repository):
    add_capability(repository, "browser.inspect", evidence_level="build_verified")

    result = evaluate_capabilities(["browser.inspect"])

    assert not result.ready
    assert result.insufficient_capabilities == ("browser.inspect",)


def test_test_verified_meets_default_threshold(repository):
    add_capability(repository, "browser.inspect", evidence_level="test_verified")

    result = evaluate_capabilities(["browser.inspect"])

    assert result.ready
    assert result.available_capabilities == ("browser.inspect",)


def test_benchmarked_meets_test_verified_threshold(repository):
    add_capability(repository, "browser.inspect", evidence_level="benchmarked")

    result = evaluate_capabilities(["browser.inspect"])

    assert result.ready


def test_missing_and_insufficient_are_distinct(repository):
    add_capability(repository, "browser.inspect", evidence_level="claimed")

    result = evaluate_capabilities(
        ["browser.inspect", "browser.navigate"]
    )

    assert result.insufficient_capabilities == ("browser.inspect",)
    assert result.missing_capabilities == ("browser.navigate",)
    assert not result.ready


def test_minimum_evidence_level_is_configurable(repository):
    add_capability(repository, "browser.inspect", evidence_level="build_verified")

    result = evaluate_capabilities(
        ["browser.inspect"],
        minimum_evidence_level="build_verified",
    )

    assert result.ready


def test_repository_scope_filters_capabilities(repository):
    second = add_repository("https://github.com/example/second")

    add_capability(repository, "browser.inspect", evidence_level="test_verified")
    add_capability(second, "browser.navigate", evidence_level="test_verified")

    result = evaluate_capabilities(
        ["browser.navigate"],
        repository_id=repository,
    )

    assert result.missing_capabilities == ("browser.navigate",)


def test_best_evidence_level_across_repositories_is_used(repository):
    second = add_repository("https://github.com/example/verified")

    add_capability(repository, "browser.inspect", evidence_level="claimed")
    add_capability(second, "browser.inspect", evidence_level="test_verified")

    result = evaluate_capabilities(["browser.inspect"])

    assert result.ready
    assert result.evidence_by_capability == (
        ("browser.inspect", "test_verified"),
    )


def test_invalid_minimum_evidence_level_is_rejected():
    with pytest.raises(ValueError, match="Invalid evidence level"):
        evaluate_capabilities([], minimum_evidence_level="unverified")


def test_non_string_minimum_evidence_level_is_rejected():
    with pytest.raises(ValueError, match="Invalid evidence level"):
        evaluate_capabilities([], minimum_evidence_level=[])


def test_invalid_required_name_is_rejected():
    with pytest.raises(ValueError, match="non-empty strings"):
        evaluate_capabilities(["browser.inspect", " "])


def test_duplicate_names_after_normalization_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate_capabilities(["browser.inspect", " browser.inspect "])


def test_string_is_not_accepted_as_collection():
    with pytest.raises(ValueError, match="iterable of names"):
        evaluate_capabilities("browser.inspect")


def test_evaluation_serializes_to_dictionary(repository):
    add_capability(repository, "browser.inspect", evidence_level="test_verified")

    result = evaluate_capabilities(["browser.inspect"])
    serialized = result.to_dict()

    assert serialized["ready"] is True
    assert serialized["available_capabilities"] == ["browser.inspect"]
    assert serialized["missing_capabilities"] == []
    assert serialized["insufficient_capabilities"] == []

def test_list_capabilities_preserves_cli_repository_fields(repository):
    from hive.capabilities import list_capabilities

    add_capability(
        repository,
        "browser.inspect",
        evidence_level="test_verified",
    )

    rows = list_capabilities()

    assert len(rows) == 1
    assert rows[0]["owner"] == "example"
    assert rows[0]["repository"] == "capabilities"
    assert rows[0]["name"] == "browser.inspect"
