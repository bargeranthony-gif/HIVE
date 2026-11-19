from __future__ import annotations
import os
from pathlib import Path

def hive_home(*, create: bool = True) -> Path:
    """Return the configured HIVE data directory.

    Read-only callers pass create=False so inspection never creates it.
    """
    path = Path(os.environ.get("HIVE_HOME", Path.home() / ".hive")).expanduser()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def database_path(*, create_parent: bool = True) -> Path:
    return hive_home(create=create_parent) / "hive.db"


def log_path() -> Path:
    return hive_home() / "logs" / "hive.log"
