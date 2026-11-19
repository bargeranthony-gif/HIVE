#!/usr/bin/env python3
"""Universal HIVE installer for macOS, Linux and Windows."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

MODEL_NAME = "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"
MODEL_URL = (
    "https://huggingface.co/second-state/"
    "Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
    + MODEL_NAME
)
MODEL_SHA256 = (
    "8ffcf166d3467df1c38991fa6196c8798b7e2bb9101d8fa34f6cd3c186913f14"
)
LLAMA_REPO = "https://github.com/ggml-org/llama.cpp.git"
ROOT = Path(__file__).resolve().parent


def run(command, cwd=None, env=None):
    print("\n>", " ".join(map(str, command)), flush=True)
    subprocess.run(
        list(map(str, command)),
        cwd=cwd,
        env=env,
        check=True,
    )


def require_tool(name):
    if not shutil.which(name):
        raise RuntimeError(
            f"Missing required tool: {name}. Install it and rerun."
        )


def check_system():
    print("\n===== SYSTEM CHECK =====")
    print("OS:", platform.system())
    print("Architecture:", platform.machine())
    print("Python:", platform.python_version())

    if sys.version_info < (3, 10):
        raise RuntimeError("HIVE requires Python 3.10 or newer.")

    for tool in ("git", "cmake"):
        require_tool(tool)

    if not any(
        shutil.which(tool)
        for tool in ("c++", "clang++", "g++", "cl")
    ):
        raise RuntimeError(
            "A C++ compiler is required to build llama.cpp. "
            "Install Xcode Command Line Tools on macOS, "
            "build-essential on Debian/Ubuntu, or Visual Studio "
            "2022 C++ Build Tools on Windows."
        )


def get_home():
    return Path(
        os.environ.get("HIVE_HOME", Path.home() / ".hive")
    ).expanduser().resolve()


def backup_database(home):
    db = home / "hive.db"

    if not db.exists():
        print("No existing database. Fresh installation.")
        return

    backup_dir = home / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"hive-preinstall-{stamp}.db"

    print("Backing up existing HIVE database:", backup)

    with sqlite3.connect(db) as source:
        with sqlite3.connect(backup) as destination:
            source.backup(destination)


def install_core(home):
    print("\n===== HIVE CORE INSTALLATION =====")

    venv = ROOT / ".venv"

    if not venv.exists():
        run([sys.executable, "-m", "venv", venv])
    else:
        print("Existing virtual environment preserved.")

    python = (
        venv / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv / "bin" / "python"
    )

    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-e", ".[dev]"])

    backup_database(home)

    env = os.environ.copy()
    env["HIVE_HOME"] = str(home)

    run(
        [
            python,
            "-c",
            "from hive.db import initialize; print(initialize())",
        ],
        env=env,
    )

    if (ROOT / "tests").is_dir():
        run([python, "-m", "pytest", "-q"], env=env)

    return venv


def sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def find_model(home):
    candidates = [
        Path(os.environ.get("HIVE_LLM_MODEL", "")),
        home / "models" / MODEL_NAME,
        Path.home() / "LOCAL_AI" / "models" / MODEL_NAME,
        ROOT / "models" / MODEL_NAME,
    ]

    for path in candidates:
        if not str(path) or not path.is_file():
            continue

        print("Checking existing model:", path)

        if sha256(path) == MODEL_SHA256:
            print("Existing model verified. Reusing it.")
            return path.resolve()

        print("Checksum differs. Preserving existing file.")

    return None


def download_model(home):
    model_dir = home / "models"
    model_dir.mkdir(parents=True, exist_ok=True)

    destination = model_dir / MODEL_NAME

    if destination.exists():
        destination = model_dir / (
            "Qwen2.5-1.5B-Instruct-Q4_K_M-verified.gguf"
        )

    if destination.exists():
        raise RuntimeError(
            f"Model destination already exists: {destination}. "
            "Inspect it before replacing anything."
        )

    partial = destination.with_suffix(destination.suffix + ".part")

    print("\nDownloading model (approximately 986 MB).")

    request = urllib.request.Request(
        MODEL_URL,
        headers={"User-Agent": "HIVE-Installer/1.0"},
    )

    digest = hashlib.sha256()
    downloaded = 0

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with partial.open("wb") as output:
                while True:
                    chunk = response.read(8 * 1024 * 1024)
                    if not chunk:
                        break

                    output.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)

                    print(
                        f"\rDownloaded: {downloaded / 1048576:.1f} MB",
                        end="",
                        flush=True,
                    )

        print()

        if digest.hexdigest() != MODEL_SHA256:
            raise RuntimeError("Downloaded model checksum failed.")

        partial.replace(destination)

    except Exception:
        print("\nDownload incomplete. Partial file preserved:", partial)
        raise

    print("Model verified:", destination)
    return destination.resolve()


def build_llama(home):
    print("\n===== LLAMA.CPP INSTALLATION =====")

    runtime = home / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)

    candidates = [
        Path(os.environ["HIVE_LLAMA_CPP_DIR"]).expanduser()
        if os.environ.get("HIVE_LLAMA_CPP_DIR")
        else None,
        Path.home() / "llama.cpp",
        runtime / "llama.cpp",
    ]

    source = next(
        (
            path.resolve()
            for path in candidates
            if path is not None
            and path.is_dir()
            and (path / ".git").exists()
        ),
        None,
    )

    if source is None:
        source = runtime / "llama.cpp"
        run(["git", "clone", LLAMA_REPO, source])

    print("Using llama.cpp:", source)

    build = source / "build"

    binaries = [
        build / "bin" / "llama-server",
        build / "bin" / "llama-server.exe",
        build / "bin" / "Release" / "llama-server.exe",
        build / "bin" / "Release" / "llama-server",
    ]

    for binary in binaries:
        if binary.is_file():
            print("Existing llama-server found:", binary)
            return binary.resolve()

    run([
        "cmake", "-S", source, "-B", build,
        "-DCMAKE_BUILD_TYPE=Release",
    ])

    run([
        "cmake", "--build", build,
        "--config", "Release",
        "--parallel",
        "--target", "llama-server",
    ])

    for binary in binaries:
        if binary.is_file():
            return binary.resolve()

    raise RuntimeError(
        "llama-server build completed but executable was not found."
    )

def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def write_launchers(home, venv, server, model):
    print("\n===== CREATING LAUNCHERS =====")

    home.mkdir(parents=True, exist_ok=True)

    base_url = "http://127.0.0.1:8080/v1"

    shell = home / "start-ai.sh"
    shell.write_text(
        "#!/bin/sh\n"
        f"export HIVE_HOME={sh_quote(home)}\n"
        f"export HIVE_LLM_BASE_URL={sh_quote(base_url)}\n"
        f"export HIVE_LLM_MODEL={sh_quote(MODEL_NAME)}\n"
        f"exec {sh_quote(server)} -m {sh_quote(model)} "
        f"--alias {sh_quote(MODEL_NAME)} "
        "--host 127.0.0.1 --port 8080 --ctx-size 2048 \"$@\"\n",
        encoding="utf-8",
    )
    shell.chmod(0o755)

    ps = home / "start-ai.ps1"
    ps.write_text(
        f"$env:HIVE_HOME = {ps_quote(home)}\n"
        f"$env:HIVE_LLM_BASE_URL = {ps_quote(base_url)}\n"
        f"$env:HIVE_LLM_MODEL = {ps_quote(MODEL_NAME)}\n"
        f"& {ps_quote(server)} -m {ps_quote(model)} "
        f"--alias {ps_quote(MODEL_NAME)} "
        "--host 127.0.0.1 --port 8080 --ctx-size 2048 @args\n"
        "exit $LASTEXITCODE\n",
        encoding="utf-8",
    )

    hive_sh = home / "hive.sh"
    hive_sh.write_text(
        "#!/bin/sh\n"
        f"export HIVE_HOME={sh_quote(home)}\n"
        f"export HIVE_LLM_BASE_URL={sh_quote(base_url)}\n"
        f"export HIVE_LLM_MODEL={sh_quote(MODEL_NAME)}\n"
        f"exec {sh_quote(venv / 'bin' / 'hive')} \"$@\"\n",
        encoding="utf-8",
    )
    hive_sh.chmod(0o755)

    hive_ps = home / "hive.ps1"
    hive_ps.write_text(
        f"$env:HIVE_HOME = {ps_quote(home)}\n"
        f"$env:HIVE_LLM_BASE_URL = {ps_quote(base_url)}\n"
        f"$env:HIVE_LLM_MODEL = {ps_quote(MODEL_NAME)}\n"
        f"& {ps_quote(venv / 'Scripts' / 'hive.exe')} @args\n"
        "exit $LASTEXITCODE\n",
        encoding="utf-8",
    )


def sh_quote(value):
    import shlex
    return shlex.quote(str(value))


def main():
    parser = argparse.ArgumentParser(
        description="Install HIVE Core and local llama.cpp AI."
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Install HIVE Core without building local AI.",
    )
    args = parser.parse_args()

    home = get_home()
    home.mkdir(parents=True, exist_ok=True)
    os.environ["HIVE_HOME"] = str(home)

    print("HIVE Universal Installer")
    print("Repository:", ROOT)
    print("Data directory:", home)

    if not args.skip_ai:
        check_system()

    venv = install_core(home)

    if not args.skip_ai:
        server = build_llama(home)
        model = find_model(home) or download_model(home)
        write_launchers(home, venv, server, model)

    print("\n===== INSTALLATION COMPLETE =====")
    print("HIVE data:", home)
    print("Virtual environment:", venv)

    if not args.skip_ai:
        print("\nOpen terminal 1 and start AI:")
        print(f"  {home / 'start-ai.sh'}")
        print("On Windows, use:")
        print(f"  . {home / 'start-ai.ps1'}")

        print("\nOpen terminal 2 and use HIVE:")
        print(f"  {home / 'hive.sh'} status")
        print("On Windows, use:")
        print(f"  . {home / 'hive.ps1'} status")

        print("\nTest AI:")
        print(f"  {home / 'hive.sh'} ai status")
        print(
            f"  {home / 'hive.sh'} ask "
            "\"Explain HIVE in three concise points.\""
        )
    else:
        print("\nCore-only installation completed.")
        print("Run the installer again without --skip-ai for full AI setup.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\nINSTALLATION FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
