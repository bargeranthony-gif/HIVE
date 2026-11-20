"""Versioned, side-effect-free HIVE Core contracts."""

from .authorization import (
    ActionType,
    AuthorizationContext,
    AuthorizationScope,
)
from .identity import HiveID, IdentityType, PrincipalRef, PrincipalType
from .lifecycle import (
    AgentLifecycle,
    ConnectorLifecycle,
    NodeLifecycle,
    ResourceLifecycle,
    TrustState,
)
from .serialization import contract_json, to_primitive
from .version import (
    CONTRACT_SCHEMA_VERSION,
    CONTRACT_VERSION,
    MAX_SUPPORTED_SCHEMA_VERSION,
    MIN_SUPPORTED_SCHEMA_VERSION,
)

__all__ = [
    "ActionType",
    "AgentLifecycle",
    "AuthorizationContext",
    "AuthorizationScope",
    "ConnectorLifecycle",
    "CONTRACT_SCHEMA_VERSION",
    "CONTRACT_VERSION",
    "HiveID",
    "IdentityType",
    "MAX_SUPPORTED_SCHEMA_VERSION",
    "MIN_SUPPORTED_SCHEMA_VERSION",
    "NodeLifecycle",
    "PrincipalRef",
    "PrincipalType",
    "ResourceLifecycle",
    "TrustState",
    "contract_json",
    "to_primitive",
]
