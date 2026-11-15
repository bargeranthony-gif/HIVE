from __future__ import annotations
import sqlite3
from pathlib import Path
from .config import database_path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS repositories (
 id INTEGER PRIMARY KEY AUTOINCREMENT, host TEXT NOT NULL DEFAULT 'github.com',
 owner TEXT NOT NULL, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
 description TEXT, language TEXT, stars INTEGER, forks INTEGER, default_branch TEXT,
 discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS capabilities (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
 name TEXT NOT NULL, description TEXT,
 evidence_level TEXT NOT NULL DEFAULT 'claimed'
 CHECK (evidence_level IN ('claimed','inferred','build_verified','test_verified','benchmarked')),
 evidence TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS analysis_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
 analyzer TEXT NOT NULL, analyzer_version TEXT, status TEXT NOT NULL, summary TEXT,
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_capabilities_repo ON capabilities(repository_id);
CREATE INDEX IF NOT EXISTS idx_repositories_language ON repositories(language);
"""

def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def initialize(path: Path | None = None) -> Path:
    db_path = path or database_path()

    with connect(db_path) as conn:
        conn.executescript(SCHEMA)

    # Import locally to avoid circular module imports.
    from .inspector import initialize_inspector
    from .graph import initialize_graph

    initialize_inspector(db_path)
    initialize_graph(db_path)

    # Import locally to avoid circular module imports.
    from .governance_store import initialize_governance
    initialize_governance(db_path)

    return db_path
