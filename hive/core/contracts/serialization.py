"""Deterministic serialization helpers for HIVE contracts."""

import json
import math
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


def to_primitive(value: Any) -> Any:
    """Convert supported contract values into JSON-compatible primitives."""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_primitive(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Contract dictionary keys must be strings")
        return {
            key: to_primitive(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite floats are not valid contract values")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported serialization type: {type(value).__name__}")


def contract_json(value: Any) -> str:
    """Produce deterministic compact JSON for supported contract values."""
    return json.dumps(
        to_primitive(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
