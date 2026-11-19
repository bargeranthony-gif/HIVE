import pytest

from hive import cli


def test_graph_build_command(monkeypatch, capsys):
    monkeypatch.setattr(cli, "initialize", lambda: None)
    monkeypatch.setattr(
        cli,
        "build_graph",
        lambda repository_id, path: {
            "repository_id": repository_id,
            "files_considered": 14,
            "relationships_found": 36,
        },
    )

    cli.main(["graph", "build", "1", "/tmp/project"])

    output = capsys.readouterr().out

    assert "Knowledge graph build complete." in output
    assert "Repository ID: 1" in output
    assert "Files considered: 14" in output
    assert "Relationships found: 36" in output


def test_graph_show_command(monkeypatch, capsys):
    monkeypatch.setattr(cli, "initialize", lambda: None)
    monkeypatch.setattr(
        cli,
        "show_graph",
        lambda repository_id: [
            {
                "source_path": "main.py",
                "relation_type": "imports",
                "target_path": "helper.py",
                "line_number": 3,
                "imported_name": "helper",
            }
        ],
    )

    cli.main(["graph", "show", "1"])

    output = capsys.readouterr().out

    assert "main.py --[imports]--> helper.py" in output
    assert "line 3" in output
    assert "helper" in output


def test_graph_show_empty_result(monkeypatch, capsys):
    monkeypatch.setattr(cli, "initialize", lambda: None)
    monkeypatch.setattr(cli, "show_graph", lambda repository_id: [])

    cli.main(["graph", "show", "1"])

    assert "No source relationships found." in capsys.readouterr().out


def test_graph_build_handles_invalid_repository(monkeypatch):
    monkeypatch.setattr(cli, "initialize", lambda: None)

    def fail_build(repository_id, path):
        raise ValueError("Repository ID 999 is not registered")

    monkeypatch.setattr(cli, "build_graph", fail_build)

    with pytest.raises(SystemExit) as exc:
        cli.main(["graph", "build", "999", "/tmp/project"])

    assert exc.value.code == 2


def test_graph_dependencies_command(monkeypatch, capsys):
    monkeypatch.setattr(cli, "initialize", lambda: None)
    monkeypatch.setattr(
        cli,
        "dependencies_for_file",
        lambda repository_id, path: [
            {
                "source_path": "main.py",
                "relation_type": "imports",
                "target_path": "helper.py",
                "line_number": 3,
                "imported_name": "helper",
            }
        ],
    )

    cli.main(["graph", "dependencies", "1", "main.py"])

    output = capsys.readouterr().out

    assert "Dependencies for main.py:" in output
    assert "main.py --[imports]--> helper.py" in output
    assert "line 3" in output


def test_graph_dependents_command(monkeypatch, capsys):
    monkeypatch.setattr(cli, "initialize", lambda: None)
    monkeypatch.setattr(
        cli,
        "dependents_for_file",
        lambda repository_id, path: [
            {
                "source_path": "consumer.py",
                "relation_type": "imports",
                "target_path": "helper.py",
                "line_number": 5,
                "imported_name": "helper",
            }
        ],
    )

    cli.main(["graph", "dependents", "1", "helper.py"])

    output = capsys.readouterr().out

    assert "Dependents for helper.py:" in output
    assert "consumer.py --[imports]--> helper.py" in output
    assert "line 5" in output


def test_graph_dependencies_empty_result(monkeypatch, capsys):
    monkeypatch.setattr(cli, "initialize", lambda: None)
    monkeypatch.setattr(cli, "dependencies_for_file", lambda repository_id, path: [])

    cli.main(["graph", "dependencies", "1", "main.py"])

    assert "No relationships found." in capsys.readouterr().out


def test_graph_dependencies_handles_invalid_file(monkeypatch):
    monkeypatch.setattr(cli, "initialize", lambda: None)

    def fail_lookup(repository_id, path):
        raise ValueError("File main.py is not registered")

    monkeypatch.setattr(cli, "dependencies_for_file", fail_lookup)

    with pytest.raises(SystemExit) as exc:
        cli.main(["graph", "dependencies", "1", "main.py"])

    assert exc.value.code == 2


def test_ask_command(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ask", lambda prompt: f"Answer: {prompt}")

    cli.main(["ask", "Explain", "HIVE"])

    assert "Answer: Explain HIVE" in capsys.readouterr().out


def test_ai_status_command(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "get_status",
        lambda: {
            "available": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "configured_model": "test-model",
            "model_loaded": True,
            "available_models": ["test-model"],
        },
    )

    cli.main(["ai", "status"])

    output = capsys.readouterr().out
    assert "AI provider: llama.cpp" in output
    assert "Server: Available" in output
    assert "Model loaded: Yes" in output


def test_ai_status_fails_when_model_missing(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "get_status",
        lambda: {
            "available": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "configured_model": "missing-model",
            "model_loaded": False,
            "available_models": ["another-model"],
        },
    )

    with pytest.raises(SystemExit) as exc:
        cli.main(["ai", "status"])

    assert exc.value.code == 1
    error_output = capsys.readouterr().err
    assert error_output.endswith("\n")
    assert "\\n" not in error_output
