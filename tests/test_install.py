import shlex

from install import MODEL_NAME, write_launchers


def test_generated_ai_launchers_advertise_the_hive_model_id(tmp_path):
    home = tmp_path / "hive-home"
    venv = tmp_path / "venv"
    server = tmp_path / "llama-server"
    model = tmp_path / MODEL_NAME

    write_launchers(home, venv, server, model)

    shell_launcher = (home / "start-ai.sh").read_text(encoding="utf-8")
    powershell_launcher = (home / "start-ai.ps1").read_text(encoding="utf-8")

    expected_shell_alias = f"--alias {shlex.quote(MODEL_NAME)}"
    expected_powershell_alias = f"--alias '{MODEL_NAME}'"

    assert expected_shell_alias in shell_launcher
    assert expected_powershell_alias in powershell_launcher
    assert f"HIVE_LLM_MODEL={shlex.quote(MODEL_NAME)}" in shell_launcher
