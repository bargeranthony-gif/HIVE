from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from .db import connect


def initialize_graph(path: Path | None = None):
    """Create the persistent source relationship table."""
    with connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id INTEGER NOT NULL
                    REFERENCES repositories(id) ON DELETE CASCADE,
                source_path TEXT NOT NULL,
                target_path TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                imported_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    repository_id,
                    source_path,
                    target_path,
                    relation_type,
                    line_number,
                    imported_name
                )
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_relationships_repo
            ON source_relationships(repository_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_relationships_source
            ON source_relationships(repository_id, source_path)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_relationships_target
            ON source_relationships(repository_id, target_path)
        """)


def _module_name(relative_path: str) -> str:
    path = Path(relative_path)
    parts = list(path.with_suffix("").parts)

    if parts and parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)


def _resolve_import(module_name: str, modules: dict[str, str]):
    """Resolve a Python module name to an inspected repository file."""
    if not module_name:
        return None

    return modules.get(module_name)


def _imports_for_file(
    source: str,
    relative_path: str,
    modules: dict[str, str],
):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    current_path = Path(relative_path)
    current_parts = list(current_path.with_suffix("").parts)

    if current_parts and current_parts[-1] == "__init__":
        package_parts = current_parts[:-1]
    else:
        package_parts = current_parts[:-1]

    relationships = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve_import(alias.name, modules)
                if target and target != relative_path:
                    relationships.append({
                        "target_path": target,
                        "line_number": node.lineno,
                        "imported_name": alias.name,
                    })

        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package_parts[
                    :len(package_parts) - node.level + 1
                ]
                if node.module:
                    base_parts.extend(node.module.split("."))
                base_module = ".".join(base_parts)
            else:
                base_module = node.module or ""

            for alias in node.names:
                candidate = ".".join(
                    part for part in (base_module, alias.name) if part
                )

                target = _resolve_import(candidate, modules)

                if target is None and base_module:
                    target = _resolve_import(base_module, modules)

                if target and target != relative_path:
                    relationships.append({
                        "target_path": target,
                        "line_number": node.lineno,
                        "imported_name": candidate or alias.name,
                    })

    return relationships


def build_graph(repository_id: int, root, path: Path | None = None):
    """Build an atomic, repeatable Python import graph."""
    root = Path(root).expanduser().resolve()

    if not root.is_dir():
        raise ValueError(f"Repository path is not a directory: {root}")

    initialize_graph(path)

    with connect(path) as conn:
        repository = conn.execute(
            "SELECT id FROM repositories WHERE id = ?",
            (repository_id,),
        ).fetchone()

        if repository is None:
            raise ValueError(f"Repository ID {repository_id} is not registered")

        files = conn.execute("""
            SELECT relative_path, sha256
            FROM source_files
            WHERE repository_id = ? AND language = 'Python'
            ORDER BY relative_path
        """, (repository_id,)).fetchall()

    if not files:
        raise ValueError(
            "No inspected Python files found. Run 'hive inspect' first."
        )

    file_paths = [row["relative_path"] for row in files]
    file_hashes = {
        row["relative_path"]: row["sha256"]
        for row in files
    }

    modules = {}
    for relative_path in file_paths:
        name = _module_name(relative_path)
        if name:
            modules[name] = relative_path

    relationships = []

    for relative_path in file_paths:
        source_path = root / relative_path

        try:
            source_bytes = source_path.read_bytes()
        except OSError as exc:
            raise ValueError(
                f"Cannot read inspected source file: {relative_path}: {exc}"
            ) from exc

        actual_hash = hashlib.sha256(source_bytes).hexdigest()
        expected_hash = file_hashes[relative_path]

        if actual_hash != expected_hash:
            raise ValueError(
                f"Source changed since inspection: {relative_path}. "
                "Run 'hive inspect' again before building the graph."
            )

        try:
            source = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Source is not valid UTF-8: {relative_path}"
            ) from exc

        for item in _imports_for_file(source, relative_path, modules):
            relationships.append({
                "source_path": relative_path,
                **item,
            })

    # Replace only this repository's graph, atomically.
    with connect(path) as conn:
        conn.execute(
            "DELETE FROM source_relationships WHERE repository_id = ?",
            (repository_id,),
        )

        for item in relationships:
            conn.execute("""
                INSERT INTO source_relationships (
                    repository_id,
                    source_path,
                    target_path,
                    relation_type,
                    line_number,
                    imported_name
                )
                VALUES (?, ?, ?, 'imports', ?, ?)
            """, (
                repository_id,
                item["source_path"],
                item["target_path"],
                item["line_number"],
                item["imported_name"],
            ))

    return {
        "repository_id": repository_id,
        "files_considered": len(file_paths),
        "relationships_found": len(relationships),
        "relationships": relationships,
    }



def _relationships_for_file(repository_id: int, relative_path: str, direction: str, path: Path | None = None):
    """Return direct dependencies or dependents for an inspected file."""
    columns = {
        "dependencies": "source_path",
        "dependents": "target_path",
    }

    if direction not in columns:
        raise ValueError(f"Unsupported graph direction: {direction}")

    column = columns[direction]

    with connect(path, readonly=True) as conn:
        repository = conn.execute(
            "SELECT id FROM repositories WHERE id = ?",
            (repository_id,),
        ).fetchone()

        if repository is None:
            raise ValueError(
                f"Repository ID {repository_id} is not registered"
            )

        inspected = conn.execute("""
            SELECT 1 FROM source_files
            WHERE repository_id = ? AND relative_path = ?
        """, (repository_id, relative_path)).fetchone()

        if inspected is None:
            raise ValueError(
                f"File is not registered as inspected: {relative_path}"
            )

        rows = conn.execute(f"""
            SELECT source_path, relation_type, target_path,
                   line_number, imported_name
            FROM source_relationships
            WHERE repository_id = ? AND {column} = ?
            ORDER BY source_path, line_number, target_path
        """, (repository_id, relative_path)).fetchall()

    return [dict(row) for row in rows]


def dependencies_for_file(repository_id: int, relative_path: str, path: Path | None = None):
    """Return files directly imported by the specified file."""
    return _relationships_for_file(
        repository_id, relative_path, "dependencies", path
    )


def dependents_for_file(repository_id: int, relative_path: str, path: Path | None = None):
    """Return files that directly import the specified file."""
    return _relationships_for_file(
        repository_id, relative_path, "dependents", path
    )


def show_graph(repository_id: int, path: Path | None = None):
    """Return stored relationships for one repository without schema writes."""
    with connect(path, readonly=True) as conn:
        repository = conn.execute(
            "SELECT id FROM repositories WHERE id = ?",
            (repository_id,),
        ).fetchone()

        if repository is None:
            raise ValueError(f"Repository ID {repository_id} is not registered")

        rows = conn.execute("""
            SELECT source_path, relation_type, target_path,
                   line_number, imported_name
            FROM source_relationships
            WHERE repository_id = ?
            ORDER BY source_path, line_number, target_path
        """, (repository_id,)).fetchall()

    return [dict(row) for row in rows]


def _load_graph_for_traversal(repository_id: int, relative_path: str, path: Path | None = None):
    """Load and validate a repository graph for traversal without schema writes."""
    with connect(path, readonly=True) as conn:
        repository = conn.execute(
            "SELECT id FROM repositories WHERE id = ?",
            (repository_id,),
        ).fetchone()

        if repository is None:
            raise ValueError(
                f"Repository ID {repository_id} is not registered"
            )

        inspected = conn.execute("""
            SELECT 1 FROM source_files
            WHERE repository_id = ? AND relative_path = ?
        """, (repository_id, relative_path)).fetchone()

        if inspected is None:
            raise ValueError(
                f"File is not registered as inspected: {relative_path}"
            )

        rows = conn.execute("""
            SELECT source_path, relation_type, target_path,
                   line_number, imported_name
            FROM source_relationships
            WHERE repository_id = ?
            ORDER BY source_path, line_number, target_path
        """, (repository_id,)).fetchall()

    return [dict(row) for row in rows]


def _recursive_traversal(
    repository_id: int,
    relative_path: str,
    direction: str,
    max_depth: int | None = None,
    path: Path | None = None,
):
    """Traverse dependencies or dependents using breadth-first search."""
    from collections import deque

    if direction not in ("dependencies", "dependents"):
        raise ValueError(f"Unsupported graph direction: {direction}")

    if max_depth is not None:
        if type(max_depth) is not int or max_depth <= 0:
            raise ValueError("max_depth must be a positive integer or None")

    rows = _load_graph_for_traversal(repository_id, relative_path, path)

    adjacency = {}

    for row in rows:
        if direction == "dependencies":
            start = row["source_path"]
            end = row["target_path"]
        else:
            start = row["target_path"]
            end = row["source_path"]

        adjacency.setdefault(start, []).append((end, row))

    visited = {relative_path}
    queue = deque([(relative_path, 0)])
    results = []

    while queue:
        current, depth = queue.popleft()

        if max_depth is not None and depth >= max_depth:
            continue

        for next_path, relationship in adjacency.get(current, []):
            if next_path in visited:
                continue

            visited.add(next_path)
            next_depth = depth + 1

            results.append({
                **relationship,
                "depth": next_depth,
            })

            queue.append((next_path, next_depth))

    return results


def recursive_dependencies_for_file(
    repository_id: int,
    relative_path: str,
    max_depth: int | None = None,
    path: Path | None = None,
):
    """Return all transitively imported files."""
    return _recursive_traversal(
        repository_id,
        relative_path,
        "dependencies",
        max_depth,
        path,
    )


def recursive_dependents_for_file(
    repository_id: int,
    relative_path: str,
    max_depth: int | None = None,
    path: Path | None = None,
):
    """Return all files transitively depending on the specified file."""
    return _recursive_traversal(
        repository_id,
        relative_path,
        "dependents",
        max_depth,
        path,
    )


def circular_dependency_groups(repository_id: int, path: Path | None = None):
    """Return strongly connected groups containing circular imports."""
    with connect(path, readonly=True) as conn:
        repository = conn.execute(
            "SELECT id FROM repositories WHERE id = ?",
            (repository_id,),
        ).fetchone()

        if repository is None:
            raise ValueError(
                f"Repository ID {repository_id} is not registered"
            )

        rows = conn.execute("""
            SELECT source_path, relation_type, target_path,
                   line_number, imported_name
            FROM source_relationships
            WHERE repository_id = ?
            ORDER BY source_path, line_number, target_path
        """, (repository_id,)).fetchall()

    relationships = [dict(row) for row in rows]
    adjacency = {}

    for row in relationships:
        adjacency.setdefault(row["source_path"], []).append(
            row["target_path"]
        )
        adjacency.setdefault(row["target_path"], [])

    # Iterative Tarjan SCC algorithm.
    index = 0
    indices = {}
    lowlinks = {}
    tarjan_stack = []
    on_stack = set()
    components = []

    for root in sorted(adjacency):
        if root in indices:
            continue

        indices[root] = index
        lowlinks[root] = index
        index += 1

        tarjan_stack.append(root)
        on_stack.add(root)

        # Each frame stores a node and its remaining neighbors.
        dfs_stack = [(root, iter(adjacency[root]))]

        while dfs_stack:
            node, neighbors = dfs_stack[-1]

            try:
                neighbor = next(neighbors)

            except StopIteration:
                dfs_stack.pop()

                if dfs_stack:
                    parent = dfs_stack[-1][0]
                    lowlinks[parent] = min(
                        lowlinks[parent],
                        lowlinks[node],
                    )

                if lowlinks[node] == indices[node]:
                    component = []

                    while True:
                        member = tarjan_stack.pop()
                        on_stack.remove(member)
                        component.append(member)

                        if member == node:
                            break

                    components.append(sorted(component))

                continue

            if neighbor not in indices:
                indices[neighbor] = index
                lowlinks[neighbor] = index
                index += 1

                tarjan_stack.append(neighbor)
                on_stack.add(neighbor)

                dfs_stack.append(
                    (neighbor, iter(adjacency[neighbor]))
                )

            elif neighbor in on_stack:
                lowlinks[node] = min(
                    lowlinks[node],
                    indices[neighbor],
                )

    # Map each file to its strongly connected component.
    component_for = {}

    for component_id, component in enumerate(components):
        for member in component:
            component_for[member] = component_id

    # Classify relationships in one pass.
    component_edges = {
        component_id: []
        for component_id in range(len(components))
    }

    self_loops = set()

    for row in relationships:
        source_id = component_for[row["source_path"]]
        target_id = component_for[row["target_path"]]

        if source_id == target_id:
            component_edges[source_id].append(row)

            if row["source_path"] == row["target_path"]:
                self_loops.add(source_id)

    circular_groups = []

    for component_id, component in enumerate(components):
        if len(component) > 1 or component_id in self_loops:
            circular_groups.append({
                "files": component,
                "relationships": component_edges[component_id],
            })

    return sorted(
        circular_groups,
        key=lambda group: group["files"],
    )
