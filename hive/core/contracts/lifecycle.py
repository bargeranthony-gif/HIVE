"""Lifecycle and trust states used by HIVE registry contracts."""

from enum import Enum


class NodeLifecycle(str, Enum):
    DISCOVERED = "discovered"
    INSTALLED = "installed"
    ENROLLED = "enrolled"
    VERIFIED = "verified"
    AUTHORIZED = "authorized"
    CONNECTED = "connected"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"
    RETIRED = "retired"


class AgentLifecycle(str, Enum):
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    AVAILABLE = "available"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    RETIRED = "retired"


class ConnectorLifecycle(str, Enum):
    DISCOVERED = "discovered"
    CONFIGURED = "configured"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    DISABLED = "disabled"
    REVOKED = "revoked"
    RETIRED = "retired"


class ResourceLifecycle(str, Enum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    AVAILABLE = "available"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    RESTRICTED = "restricted"
    REVOKED = "revoked"
    RETIRED = "retired"


class TrustState(str, Enum):
    UNKNOWN = "unknown"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    TRUSTED = "trusted"
    SUSPICIOUS = "suspicious"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"
