from datetime import datetime, timezone

import pytest

from hive.core.contracts import (
    ActionType,
    AuthorizationContext,
    AuthorizationScope,
    HiveID,
    IdentityType,
    PrincipalRef,
    PrincipalType,
)


def make_owner():
    return PrincipalRef(
        principal_type=PrincipalType.OWNER,
        identity=HiveID.new(IdentityType.OWNER),
    )


def test_context_creation_uses_utc_timestamp():
    context = AuthorizationContext.create(
        requester=make_owner(),
        action=ActionType.READ,
        scope=AuthorizationScope.LOCAL,
    )

    assert context.requested_at is not None
    assert context.requested_at.utcoffset().total_seconds() == 0


def test_context_accepts_correctly_typed_references():
    context = AuthorizationContext(
        requester=make_owner(),
        action=ActionType.EXECUTE,
        scope=AuthorizationScope.NODE,
        task_id=HiveID.new(IdentityType.TASK),
        node_id=HiveID.new(IdentityType.NODE),
        agent_id=HiveID.new(IdentityType.AGENT),
        interface_id=HiveID.new(IdentityType.INTERFACE),
    )

    assert context.task_id.identity_type is IdentityType.TASK
    assert context.node_id.identity_type is IdentityType.NODE


def test_context_rejects_wrong_task_id_type():
    with pytest.raises(ValueError):
        AuthorizationContext(
            requester=make_owner(),
            action=ActionType.READ,
            scope=AuthorizationScope.LOCAL,
            task_id=HiveID.new(IdentityType.AGENT),
        )


def test_context_rejects_naive_datetime():
    with pytest.raises(ValueError):
        AuthorizationContext(
            requester=make_owner(),
            action=ActionType.READ,
            scope=AuthorizationScope.LOCAL,
            requested_at=datetime(2026, 1, 1),
        )


def test_context_rejects_invalid_enum_types():
    with pytest.raises(TypeError):
        AuthorizationContext(
            requester=make_owner(),
            action="read",
            scope=AuthorizationScope.LOCAL,
        )


def test_authorization_context_is_not_an_approval():
    context = AuthorizationContext.create(
        requester=make_owner(),
        action=ActionType.EXECUTE,
        scope=AuthorizationScope.EXTERNAL,
    )

    assert context.approval_id is None
    assert context.policy_version is None


def test_context_rejects_non_datetime_requested_at():
    with pytest.raises(TypeError):
        AuthorizationContext(
            requester=make_owner(),
            action=ActionType.READ,
            scope=AuthorizationScope.LOCAL,
            requested_at="2026-11-20T12:00:00Z",
        )
