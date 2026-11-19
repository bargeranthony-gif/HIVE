from __future__ import annotations
from urllib.parse import urlparse
from .db import connect

def normalize_github_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url.strip())
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Only github.com repository URLs are supported in v0.1")
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError("Expected https://github.com/owner/repository")
    owner, name = parts[0], parts[1]
    if name.endswith(".git"): name = name[:-4]
    if not owner or not name: raise ValueError("Repository owner and name are required")
    return owner, name

def add_repository(url: str, description: str | None = None, language: str | None = None,
                   stars: int | None = None, forks: int | None = None,
                   default_branch: str | None = None) -> int:
    owner, name = normalize_github_url(url)
    canonical = f"https://github.com/{owner}/{name}"
    with connect() as conn:
        conn.execute("""INSERT INTO repositories
          (owner,name,url,description,language,stars,forks,default_branch,updated_at)
          VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
          ON CONFLICT(url) DO UPDATE SET
          description=COALESCE(excluded.description,repositories.description),
          language=COALESCE(excluded.language,repositories.language),
          stars=COALESCE(excluded.stars,repositories.stars),
          forks=COALESCE(excluded.forks,repositories.forks),
          default_branch=COALESCE(excluded.default_branch,repositories.default_branch),
          updated_at=CURRENT_TIMESTAMP""",
          (owner,name,canonical,description,language,stars,forks,default_branch))
        row=conn.execute("SELECT id FROM repositories WHERE url=?",(canonical,)).fetchone()
        return int(row["id"])

def list_repositories():
    """List registered repositories without opening SQLite for writes."""
    with connect(readonly=True) as conn:
        return conn.execute("SELECT id,owner,name,language,stars,url FROM repositories ORDER BY id").fetchall()
