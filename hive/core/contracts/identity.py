"""Canonical typed identities for HIVE contracts."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4


class IdentityType(str, Enum):
    HIVE = "hive"
    INSTALLATION = "installation"
    OWNER = "owner"
    USER = "user"
    NODE = "node"
    INTERFACE = "interface"
    AGENT = "agent"
    SERVICE = "service"
    CONNECTOR = "connector"
    RESOURCE = "resource"
    CAPABILITY = "capability"
    TASK = "task"
    EVENT = "event"
    EXECUTION = "execution"
    APPROVAL = "approval"


@dataclass(frozen=True, slots=True)
class HiveID:
    """Typed UUID identity. Identity alone conveys no trust or permission."""

    identity_type: IdentityType
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.identity_type, IdentityType):
            raise TypeError("identity_type must be an IdentityType")
        if not isinstance(self.value, UUID):
            raise TypeError("value must be a UUID")

    @classmethod
    def new(cls, identity_type: IdentityType) -> "HiveID":
        if not isinstance(identity_type, IdentityType):
            raise TypeError("identity_type must be an IdentityType")
        return cls(identity_type=identity_type, value=uuid4())

    @classmethod
    def parse(cls, text: str) -> "HiveID":
        if not isinstance(text, str):
            raise TypeError("ID must be a string")
        parts = text.split(":", 1)
        if len(parts) != 2:
            raise ValueError("ID must use type:uuid format")
        try:
            identity_type = IdentityType(parts[0])
            value = UUID(parts[1])
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid typed HIVE ID") from exc
        return cls(identity_type, value)

    def __str__(self) -> str:
        return f"{self.identity_type.value}:{self.value}"


class PrincipalType(str, Enum):
    OWNER = "owner"
    USER = "user"
    AGENT = "agent"
    INTERFACE = "interface"
    NODE = "node"
    SERVICE = "service"


@dataclass(frozen=True, slots=True)
class PrincipalRef:
    """Reference to an actor. This is descriptive, not an authentication proof."""

    principal_type: PrincipalType
    identity: HiveID

    def __post_init__(self) -> None:
        if not isinstance(self.principal_type, PrincipalType):
            raise TypeError("principal_type must be a PrincipalType")
        if not isinstance(self.identity, HiveID):
            raise TypeError("identity must be a HiveID")

        expected = {
            PrincipalType.OWNER: IdentityType.OWNER,
            PrincipalType.USER: IdentityType.USER,
            PrincipalType.AGENT: IdentityType.AGENT,
            PrincipalType.INTERFACE: IdentityType.INTERFACE,
            PrincipalType.NODE: IdentityType.NODE,
            PrincipalType.SERVICE: IdentityType.SERVICE,
        }[self.principal_type]

        if self.identity.identity_type != expected:
            raise ValueError(
                f"{self.principal_type.value} principal requires "
                f"{expected.value} identity"
            )
