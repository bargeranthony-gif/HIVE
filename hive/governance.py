from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


POLICY_ID = "HIVE-BROX-DEMO-POLICY"
POLICY_VERSION = "0.1"
POLICY_HASH = "synthetic-demo-policy-v1"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Datetime values must include a timezone.")
    return value.astimezone(timezone.utc)


def canonical_action_digest(
    *,
    actor: str,
    action: str,
    target: str,
    parameters: Mapping[str, Any],
    scope: str,
    environment: str,
    policy_id: str = POLICY_ID,
    policy_version: str = POLICY_VERSION,
    policy_hash: str = POLICY_HASH,
) -> str:
    """Bind approval to the complete action and policy context."""
    envelope = {
        "actor": actor,
        "action": action,
        "target": target,
        "parameters": dict(parameters),
        "scope": scope,
        "environment": environment,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "policy_hash": policy_hash,
    }

    encoded = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    original_text: str
    target_id: str
    recorded_status: str
    approval_recorded: bool


@dataclass(frozen=True)
class ActionRequest:
    actor: str
    action: str
    target: str
    parameters: Mapping[str, Any]
    scope: str
    environment: str


@dataclass(frozen=True)
class Approval:
    approval_id: str
    approver_id: str
    action_digest: str
    scope: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False
    issuer_type: str = "synthetic_test_fixture"


@dataclass(frozen=True)
class Decision:
    disposition: str
    approval_state: str
    action_digest: str
    rationale: str
    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION


@dataclass(frozen=True)
class ExecutionResult:
    result_id: str
    target: str
    resulting_status: str
    side_effect_count: int
    replayed: bool


def read_source_summary(source: SourceRecord) -> dict[str, str]:
    """Return a read-only summary without changing source evidence."""
    return {
        "source_id": source.source_id,
        "target_id": source.target_id,
        "recorded_status": source.recorded_status,
        "approval_state": (
            "RECORDED" if source.approval_recorded
            else "UNKNOWN / NOT_RECORDED"
        ),
        "original_text": source.original_text,
    }


class GovernanceGate:
    """A narrow, testable approval boundary for the synthetic demo."""

    def __init__(
        self,
        *,
        allow_synthetic_approvals: bool = False,
        policy_id: str = POLICY_ID,
        policy_version: str = POLICY_VERSION,
        policy_hash: str = POLICY_HASH,
    ):
        self.allow_synthetic_approvals = allow_synthetic_approvals
        self.policy_id = policy_id
        self.policy_version = policy_version
        self.policy_hash = policy_hash

    def digest(self, request: ActionRequest) -> str:
        return canonical_action_digest(
            actor=request.actor,
            action=request.action,
            target=request.target,
            parameters=request.parameters,
            scope=request.scope,
            environment=request.environment,
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            policy_hash=self.policy_hash,
        )

    def evaluate(
        self,
        source: SourceRecord,
        request: ActionRequest,
        approval: Approval | None = None,
        *,
        now: datetime | None = None,
    ) -> Decision:
        digest = self.digest(request)

        def hold(state: str, reason: str) -> Decision:
            return Decision("HOLD", state, digest, reason,
                            self.policy_id, self.policy_version)

        if request.target != source.target_id:
            return hold(
                "UNKNOWN / NOT_VERIFIED",
                "Requested target does not match the source record.",
            )

        if source.recorded_status != "pending":
            return hold(
                "UNKNOWN / NOT_VERIFIED",
                "Source does not establish the expected pending state.",
            )

        if request.action != "set_purchase_status":
            return hold("UNKNOWN / NOT_VERIFIED", "Action is outside demo scope.")

        if dict(request.parameters) != {"status": "approved"}:
            return hold(
                "UNKNOWN / NOT_VERIFIED",
                "Requested parameters are outside demo scope.",
            )

        if not approval:
            return hold(
                "UNKNOWN / NOT_RECORDED",
                "No approval record was supplied. No approval is inferred.",
            )

        if approval.action_digest != digest:
            return hold(
                "UNKNOWN / MISMATCH",
                "Approval does not match the exact requested action.",
            )

        if approval.scope != request.scope:
            return hold(
                "UNKNOWN / SCOPE_MISMATCH",
                "Approval scope does not match the requested action.",
            )

        if approval.revoked:
            return hold("REVOKED", "Approval has been revoked.")

        current_time = _utc(now or datetime.now(timezone.utc))

        if current_time >= _utc(approval.expires_at):
            return hold("EXPIRED", "Approval has expired.")

        if current_time < _utc(approval.issued_at):
            return hold("NOT_YET_VALID", "Approval is not yet valid.")

        if approval.issuer_type != "synthetic_test_fixture":
            return hold(
                "UNKNOWN / AUTHENTICATION_UNVERIFIED",
                "This demo has no production identity-verification mechanism.",
            )

        if not self.allow_synthetic_approvals:
            return hold(
                "UNKNOWN / TEST_APPROVAL_DISABLED",
                "Synthetic approvals are disabled by default.",
            )

        return Decision(
            "ALLOW",
            "APPROVED / SYNTHETIC TEST FIXTURE",
            digest,
            "Exact action matches the synthetic test approval.",
            self.policy_id,
            self.policy_version,
        )
