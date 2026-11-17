import pytest

from ._load_engine import _load_engine


@pytest.fixture
def engine_module():
    return _load_engine()


@pytest.fixture
def store(tmp_path, engine_module):
    return engine_module.IdentityStore(tmp_path / "haie-v04.sqlite")


def test_create_identity_has_one_unified_personality(store):
    identity = store.create_identity("hive-1", "HIVE")

    assert identity["identity_id"] == "hive-1"
    assert identity["display_name"] == "HIVE"
    assert set(identity["personality"]["traits"]) == {
        "sociability",
        "humor",
        "competitiveness",
        "formality",
        "patience",
        "playfulness",
    }
    assert identity["personality"]["descriptors"] == {}
    assert identity["personality"]["revision"] == 1


def test_identity_and_personality_persist_after_reopening(
    tmp_path, engine_module
):
    database = tmp_path / "persistent.sqlite"

    first = engine_module.IdentityStore(database)
    first.create_identity(
        "hive-1",
        "HIVE",
        descriptors={"temperament": "curious and observant"},
    )

    second = engine_module.IdentityStore(database)
    identity = second.get_identity("hive-1")

    assert identity["personality"]["descriptors"]["temperament"] == (
        "curious and observant"
    )


def test_profile_updates_preserve_other_personality_dimensions(store):
    store.create_identity("hive-1", "HIVE")

    updated = store.update_personality_profile(
        "hive-1",
        traits={"humor": 0.75},
        descriptors={"communication_style": "direct and analytical"},
    )

    personality = updated["personality"]

    assert personality["traits"]["humor"] == 0.75
    assert personality["traits"]["patience"] == 0.50
    assert personality["descriptors"]["communication_style"] == (
        "direct and analytical"
    )
    assert personality["revision"] == 2


def test_multiple_contexts_do_not_create_multiple_identities(store):
    store.create_identity("hive-1", "HIVE")

    store.update_personality_profile(
        "hive-1",
        descriptors={"work_expression": "technical and precise"},
    )
    store.update_personality_profile(
        "hive-1",
        descriptors={"social_expression": "relaxed and playful"},
    )

    identity = store.get_identity("hive-1")

    assert identity["identity_id"] == "hive-1"
    assert len(identity["personality"]) > 0
    assert identity["personality"]["descriptors"] == {
        "work_expression": "technical and precise",
        "social_expression": "relaxed and playful",
    }


def test_duplicate_identity_is_rejected(store):
    store.create_identity("hive-1", "HIVE")

    with pytest.raises(Exception):
        store.create_identity("hive-1", "Another HIVE")


@pytest.mark.parametrize(
    "traits",
    [
        {"humor": 1.5},
        {"humor": -0.1},
        {"humor": True},
        {"unknown_trait": 0.5},
        ["humor"],
    ],
)
def test_invalid_traits_are_rejected(store, traits):
    with pytest.raises(ValueError):
        store.create_identity("hive-1", "HIVE", traits=traits)


def test_invalid_descriptor_values_are_rejected(store):
    with pytest.raises(ValueError):
        store.create_identity(
            "hive-1",
            "HIVE",
            descriptors={"temperament": 42},
        )


def test_unknown_identity_raises_key_error(store):
    with pytest.raises(KeyError):
        store.get_identity("missing")


def test_empty_profile_update_is_rejected(store):
    store.create_identity("hive-1", "HIVE")

    with pytest.raises(ValueError):
        store.update_personality_profile("hive-1")
