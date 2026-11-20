import pytest
from uuid import UUID

from hive.core.contracts import (
    HiveID,
    IdentityType,
    PrincipalRef,
    PrincipalType,
)


def test_id_creation_and_round_trip():
    original = HiveID.new(IdentityType.NODE)
    parsed = HiveID.parse(str(original))

    assert parsed == original
    assert parsed.identity_type is IdentityType.NODE
    assert isinstance(parsed.value, UUID)


def test_ids_are_type_distinct():
    value = UUID("00000000-0000-0000-0000-000000000001")

    node_id = HiveID(IdentityType.NODE, value)
    agent_id = HiveID(IdentityType.AGENT, value)

    assert node_id != agent_id
    assert str(node_id) != str(agent_id)


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "node",
        "unknown:00000000-0000-0000-0000-000000000001",
        "node:not-a-uuid",
        "node:00000000-0000-0000-0000-000000000001:extra",
    ],
)
def test_invalid_id_strings_are_rejected(invalid):
    with pytest.raises(ValueError):
        HiveID.parse(invalid)


def test_wrong_principal_identity_type_is_rejected():
    agent_id = HiveID.new(IdentityType.AGENT)

    with pytest.raises(ValueError):
        PrincipalRef(
            principal_type=PrincipalType.NODE,
            identity=agent_id,
        )


def test_matching_principal_identity_type_is_accepted():
    owner_id = HiveID.new(IdentityType.OWNER)

    principal = PrincipalRef(
        principal_type=PrincipalType.OWNER,
        identity=owner_id,
    )

    assert principal.identity == owner_id


@pytest.mark.parametrize(
    ("principal_type", "identity_type"),
    [
        (PrincipalType.USER, IdentityType.USER),
        (PrincipalType.SERVICE, IdentityType.SERVICE),
    ],
)
def test_user_and_service_principals_require_matching_identity(
    principal_type, identity_type
):
    principal = PrincipalRef(
        principal_type=principal_type,
        identity=HiveID.new(identity_type),
    )

    assert principal.identity.identity_type is identity_type


@pytest.mark.parametrize(
    ("principal_type", "identity_type"),
    [
        (PrincipalType.USER, IdentityType.OWNER),
        (PrincipalType.SERVICE, IdentityType.AGENT),
    ],
)
def test_user_and_service_principals_reject_mismatched_identity(
    principal_type, identity_type
):
    with pytest.raises(ValueError):
        PrincipalRef(
            principal_type=principal_type,
            identity=HiveID.new(identity_type),
        )


def test_new_id_rejects_invalid_identity_type():
    with pytest.raises(TypeError):
        HiveID.new("node")
