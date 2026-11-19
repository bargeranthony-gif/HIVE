import hashlib
import sqlite3

import pytest

from hive.cli import main
from hive.db import connect, initialize
from hive.repositories import add_repository
from hive.capabilities import add_capability


@pytest.fixture
def hive_environment(monkeypatch, tmp_path):
    home = tmp_path / "hive-home"
    monkeypatch.setenv("HIVE_HOME", str(home))
    database = initialize()
    repository_id = add_repository(
        "https://github.com/example/read-only-cli",
        language="Python",
    )
    add_capability(
        repository_id,
        "example capability",
        evidence_level="claimed",
        evidence="test fixture",
    )
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO source_files
                (repository_id, relative_path, language, size_bytes, sha256)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                repository_id,
                "src.py",
                "Python",
                0,
                hashlib.sha256(b"").hexdigest(),
            ),
        )
    return home, database, repository_id


@pytest.mark.parametrize(
    "command",
    [
        ["status"],
        ["repo", "list"],
        ["capability", "list"],
        ["graph", "show"],
        ["graph", "dependencies"],
        ["graph", "dependents"],
        ["graph", "recursive-dependencies"],
        ["graph", "recursive-dependents"],
        ["graph", "cycles"],
    ],
)
def test_informational_database_commands_do_not_write(
    command, hive_environment, capsys
):
    home, database, repository_id = hive_environment
    args = ["--read-only", *command]
    if command[0] == "graph":
        if command[1] == "show" or command[1] == "cycles":
            args.append(str(repository_id))
        else:
            args.extend([str(repository_id), "src.py"])

    before_bytes = database.read_bytes()
    before_stat = database.stat()
    log_dir = home / "logs"

    main(args)
    capsys.readouterr()

    after_stat = database.stat()
    assert database.read_bytes() == before_bytes
    assert after_stat.st_size == before_stat.st_size
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
    assert not log_dir.exists()


def test_readonly_connection_rejects_writes(hive_environment):
    _, database, _ = hive_environment

    with connect(readonly=True) as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE must_not_exist (id INTEGER)")


def test_status_does_not_create_missing_hive_home(monkeypatch, tmp_path):
    home = tmp_path / "not-created"
    monkeypatch.setenv("HIVE_HOME", str(home))

    with pytest.raises(SystemExit) as exc:
        main(["--read-only", "status"])

    assert exc.value.code == 1
    assert not home.exists()


def test_version_does_not_create_hive_home(monkeypatch, tmp_path, capsys):
    home = tmp_path / "not-created"
    monkeypatch.setenv("HIVE_HOME", str(home))

    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert "HIVE " in capsys.readouterr().out
    assert not home.exists()



def test_status_preserves_initialization_behavior_without_read_only_flag(
    monkeypatch, tmp_path, capsys
):
    home = tmp_path / "default-home"
    monkeypatch.setenv("HIVE_HOME", str(home))

    main(["status"])

    assert (home / "hive.db").is_file()
    assert (home / "logs" / "hive.log").is_file()
    assert "Repositories: 0" in capsys.readouterr().out


def test_read_only_flag_is_rejected_for_mutating_commands():
    with pytest.raises(SystemExit) as exc:
        main(["--read-only", "repo", "add", "https://github.com/example/repo"])

    assert exc.value.code == 2
