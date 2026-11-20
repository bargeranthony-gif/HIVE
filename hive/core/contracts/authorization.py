"""Authorization request context contracts. These records grant no authority."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .identity import HiveID, IdentityType, PrincipalRef


class ActionType(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    SEND = "send"
    DELETE = "delete"
    SHARE = "share"
    APPROVE = "approve"
    SPEND = "spend"
    TRADE = "trade"
    ENROLL = "enroll"
    CONFIGURE = "configure"


class AuthorizationScope(str, Enum):
    SELF = "self"
    LOCAL = "local"
    NODE = "node"
    INSTALLATION = "installation"
    HIVE = "hive"
    FEDERATION = "federation"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Describes a request for policy evaluation; it is not an approval."""

    requester: PrincipalRef
    action: ActionType
    scope: AuthorizationScope
    target: Optional[HiveID] = None
    task_id: Optional[HiveID] = None
    node_id: Optional[HiveID] = None
    interface_id: Optional[HiveID] = None
    agent_id: Optional[HiveID] = None
    policy_version: Optional[str] = None
    approval_id: Optional[HiveID] = None
    requested_at: Optional[datetime] = None
    correlation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.requester, PrincipalRef):
            raise TypeError("requester must be a PrincipalRef")
        if not isinstance(self.action, ActionType):
            raise TypeError("action must be an ActionType")
        if not isinstance(self.scope, AuthorizationScope):
            raise TypeError("scope must be an AuthorizationScope")

        typed_fields = {
            "target": self.target,
            "task_id": self.task_id,
            "node_id": self.node_id,
            "interface_id": self.interface_id,
            "agent_id": self.agent_id,
            "approval_id": self.approval_id,
        }
        expected_types = {
            "task_id": IdentityType.TASK,
            "node_id": IdentityType.NODE,
            "interface_id": IdentityType.INTERFACE,
            "agent_id": IdentityType.AGENT,
            "approval_id": IdentityType.APPROVAL,
        }

        for field_name, value in typed_fields.items():
            if value is not None and not isinstance(value, HiveID):
                raise TypeError(f"{field_name} must be a HiveID")

            expected = expected_types.get(field_name)
            if value is not None and expected is not None:
                if value.identity_type != expected:
                    raise ValueError(
                        f"{field_name} must use {expected.value} identity"
                    )

        if self.requested_at is not None:
            if not isinstance(self.requested_at, datetime):
                raise TypeError("requested_at must be a datetime")
            if (
                self.requested_at.tzinfo is None
                or self.requested_at.utcoffset() is None
            ):
                raise ValueError("requested_at must be timezone-aware")

        if self.policy_version is not None:
            if not isinstance(self.policy_version, str) or not self.policy_version.strip():
                raise ValueError("policy_version must be a non-empty string")

        if self.correlation_id is not None:
            if not isinstance(self.correlation_id, str) or not self.correlation_id.strip():
                raise ValueError("correlation_id must be a non-empty string")

    @classmethod
    def create(
        cls,
        *,
        requester: PrincipalRef,
        action: ActionType,
        scope: AuthorizationScope,
        **kwargs,
    ) -> "AuthorizationContext":
        """Convenience constructor with a UTC request timestamp."""
        kwargs.setdefault("requested_at", datetime.now(timezone.utc))
        return cls(
            requester=requester,
            action=action,
            scope=scope,
            **kwargs,
        )
