from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .config import hive_home


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKER = Path(__file__).with_name("browser_worker.py")


def validate_url(url: str) -> str:
    """Accept ordinary HTTP and HTTPS URLs only."""
    target = url.strip()
    parsed = urlsplit(target)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are supported.")

    if not parsed.hostname:
        raise ValueError("A valid hostname is required.")

    if parsed.username or parsed.password:
        raise ValueError(
            "URLs containing embedded credentials are not allowed."
        )

    return target


def browser_python() -> Path:
    """Find the configured or isolated browser Python interpreter."""
    configured = os.environ.get("HIVE_BROWSER_PYTHON")

    if configured:
        interpreter = Path(configured).expanduser()
        if not interpreter.is_file():
            raise RuntimeError(
                f"Configured browser Python does not exist: {interpreter}"
            )
        return interpreter.absolute()

    if os.name == "nt":
        legacy = PROJECT_ROOT / ".venv-browser-legacy" / "Scripts" / "python.exe"
    else:
        legacy = PROJECT_ROOT / ".venv-browser-legacy" / "bin" / "python"

    if legacy.is_file():
        return legacy.absolute()

    return Path(sys.executable).absolute()


def _run_worker(arguments: list[str]) -> subprocess.CompletedProcess:
    """Run the isolated browser worker and capture its output."""
    if not WORKER.is_file():
        raise RuntimeError(f"Browser worker is missing: {WORKER}")

    command = [
        str(browser_python()),
        str(WORKER),
        *arguments,
    ]

    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(details) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Browser worker exceeded its 180-second limit.") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start browser worker: {exc}") from exc


def browser_status() -> dict:
    """Report the selected browser interpreter and runtime status."""
    try:
        result = _run_worker(["status"])
        data = json.loads(result.stdout)

        return {
            "installed": data.get("installed", False),
            "version": data.get("version"),
            "chromium_installed": data.get("chromium_installed", False),
            "chromium_executable": data.get("chromium_executable"),
            "browser_python": str(browser_python()),
            "browser_runtime": (
                "Chromium ready"
                if data.get("chromium_installed")
                else "Playwright available; Chromium not installed"
            ),
        }

    except Exception as exc:
        return {
            "installed": False,
            "version": None,
            "chromium_installed": False,
            "browser_python": None,
            "browser_runtime": f"Unavailable: {exc}",
        }


def install_browser() -> None:
    """Install Chromium using the selected browser interpreter."""
    result = _run_worker(["install"])

    if result.stdout.strip():
        print(result.stdout.strip())


def inspect_url(url: str, timeout: int = 15000) -> dict:
    """Inspect a webpage through the isolated browser worker."""
    target = validate_url(url)

    if timeout <= 0:
        raise ValueError("Timeout must be positive.")

    output_dir = hive_home() / "browser"

    result = _run_worker([
        "inspect",
        "--url", target,
        "--timeout", str(timeout),
        "--output-dir", str(output_dir),
    ])

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Browser worker returned invalid JSON: {result.stdout[:500]}"
        ) from exc

    return data
