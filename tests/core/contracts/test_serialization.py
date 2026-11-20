from datetime import datetime, timezone
from uuid import UUID

import pytest

from hive.core.contracts import (
    ActionType,
    AuthorizationContext,
    AuthorizationScope,
    HiveID,
    IdentityType,
    PrincipalRef,
    PrincipalType,
    contract_json,
    to_primitive,
)


def make_context():
    return AuthorizationContext(
        requester=PrincipalRef(
            principal_type=PrincipalType.OWNER,
            identity=HiveID(
                IdentityType.OWNER,
                UUID("00000000-0000-0000-0000-000000000001"),
            ),
        ),
        action=ActionType.READ,
        scope=AuthorizationScope.LOCAL,
        requested_at=datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc),
    )


def test_json_serialization_is_deterministic():
    context = make_context()

    first = contract_json(context)
    second = contract_json(context)

    assert first == second
    assert '"action":"read"' in first
    assert '"scope":"local"' in first
    assert '"requested_at":"2026-11-20T12:00:00Z"' in first


def test_serialization_converts_ids_and_enums():
    primitive = to_primitive(make_context())

    assert primitive["action"] == "read"
    assert primitive["scope"] == "local"
    assert primitive["requester"]["principal_type"] == "owner"
    assert primitive["requester"]["identity"]["identity_type"] == "owner"


def test_unsupported_objects_rejected():
    with pytest.raises(TypeError):
        contract_json(object())


def test_naive_datetime_rejected_by_serializer():
    with pytest.raises(ValueError):
        contract_json(datetime(2026, 1, 1))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_are_rejected(value):
    with pytest.raises(ValueError):
        contract_json({"value": value})


def test_non_string_dictionary_keys_are_rejected():
    with pytest.raises(TypeError):
        contract_json({1: "integer key", "1": "string key"})
