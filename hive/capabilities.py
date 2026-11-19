from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .db import connect

LEVELS = {
    "claimed",
    "inferred",
    "build_verified",
    "test_verified",
    "benchmarked",
}

EVIDENCE_RANK = {
    "claimed": 0,
    "inferred": 1,
    "build_verified": 2,
    "test_verified": 3,
    "benchmarked": 4,
}

DEFAULT_MINIMUM_EVIDENCE = "test_verified"


@dataclass(frozen=True)
class CapabilityRecord:
    id: int
    repository_id: int
    name: str
    description: str | None
    evidence_level: str
    evidence: str | None


@dataclass(frozen=True)
class CapabilityEvaluation:
    available_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    insufficient_capabilities: tuple[str, ...]
    evidence_by_capability: tuple[tuple[str, str], ...]

    @property
    def ready(self) -> bool:
        return not self.missing_capabilities and not self.insufficient_capabilities

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "available_capabilities": list(self.available_capabilities),
            "missing_capabilities": list(self.missing_capabilities),
            "insufficient_capabilities": list(self.insufficient_capabilities),
            "evidence_by_capability": [
                {"name": name, "evidence_level": level}
                for name, level in self.evidence_by_capability
            ],
        }


def _validate_evidence_level(level: str) -> None:
    if not isinstance(level, str) or level not in LEVELS:
        raise ValueError(
            f"Invalid evidence level: {level!r}. "
            f"Expected one of: {', '.join(sorted(LEVELS))}"
        )


def add_capability(
    repository_id: int,
    name: str,
    description: str | None = None,
    evidence_level: str = "claimed",
    evidence: str | None = None,
) -> int:
    _validate_evidence_level(evidence_level)

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Capability name must be a non-empty string")

    name = name.strip()

    with connect() as conn:
        repository = conn.execute(
            "SELECT id FROM repositories WHERE id = ?",
            (repository_id,),
        ).fetchone()

        if repository is None:
            raise ValueError(f"Repository not found: {repository_id}")

        cursor = conn.execute(
            """
            INSERT INTO capabilities
                (repository_id, name, description, evidence_level, evidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (repository_id, name, description, evidence_level, evidence),
        )
        return int(cursor.lastrowid)


def list_capabilities() -> list[dict]:
    """List capability records without opening SQLite for writes."""
    with connect(readonly=True) as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.repository_id,
                c.name,
                c.description,
                c.evidence_level,
                c.evidence,
                r.owner,
                r.name AS repository
            FROM capabilities c
            JOIN repositories r ON r.id = c.repository_id
            ORDER BY c.id
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_capabilities(repository_id: int | None = None) -> list[CapabilityRecord]:
    query = """
        SELECT id, repository_id, name, description, evidence_level, evidence
        FROM capabilities
    """
    params: tuple = ()

    if repository_id is not None:
        query += " WHERE repository_id = ?"
        params = (repository_id,)

    query += " ORDER BY id"

    with connect(readonly=True) as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        CapabilityRecord(
            id=row["id"],
            repository_id=row["repository_id"],
            name=row["name"],
            description=row["description"],
            evidence_level=row["evidence_level"],
            evidence=row["evidence"],
        )
        for row in rows
    ]


def evaluate_capability_records(
    required_capabilities: Iterable[str],
    records: Iterable[CapabilityRecord],
    minimum_evidence_level: str = DEFAULT_MINIMUM_EVIDENCE,
) -> CapabilityEvaluation:
    """Evaluate required capabilities against an existing record snapshot."""
    _validate_evidence_level(minimum_evidence_level)

    if isinstance(required_capabilities, (str, bytes)):
        raise ValueError("Required capabilities must be an iterable of names")

    try:
        required = tuple(required_capabilities)
    except TypeError as exc:
        raise ValueError("Required capabilities must be iterable") from exc

    normalized: list[str] = []

    for name in required:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Required capability names must be non-empty strings")
        normalized.append(name.strip())

    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate required capability names are not allowed")

    try:
        record_snapshot = tuple(records)
    except TypeError as exc:
        raise ValueError("Capability records must be iterable") from exc

    if not all(isinstance(record, CapabilityRecord) for record in record_snapshot):
        raise ValueError("Every capability record must be a CapabilityRecord")

    evidence_by_name: dict[str, str] = {}

    for record in record_snapshot:
        current = evidence_by_name.get(record.name)
        if (
            current is None
            or EVIDENCE_RANK[record.evidence_level] > EVIDENCE_RANK[current]
        ):
            evidence_by_name[record.name] = record.evidence_level

    available: list[str] = []
    missing: list[str] = []
    insufficient: list[str] = []
    evidence: list[tuple[str, str]] = []

    threshold = EVIDENCE_RANK[minimum_evidence_level]

    for name in normalized:
        level = evidence_by_name.get(name)

        if level is None:
            missing.append(name)
            continue

        evidence.append((name, level))

        if EVIDENCE_RANK[level] >= threshold:
            available.append(name)
        else:
            insufficient.append(name)

    return CapabilityEvaluation(
        available_capabilities=tuple(available),
        missing_capabilities=tuple(missing),
        insufficient_capabilities=tuple(insufficient),
        evidence_by_capability=tuple(evidence),
    )


def evaluate_capabilities(
    required_capabilities: Iterable[str],
    minimum_evidence_level: str = DEFAULT_MINIMUM_EVIDENCE,
    repository_id: int | None = None,
) -> CapabilityEvaluation:
    """Evaluate capabilities using the current database records."""
    records = get_capabilities(repository_id)

    return evaluate_capability_records(
        required_capabilities,
        records,
        minimum_evidence_level,
    )
