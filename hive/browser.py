from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .config import hive_home


def validate_url(url: str) -> str:
    """Accept ordinary HTTP and HTTPS URLs only."""
    parsed = urlsplit(url.strip())

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are supported.")

    if not parsed.hostname:
        raise ValueError("A valid hostname is required.")

    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not allowed.")

    return url.strip()


def browser_status() -> dict:
    """Report whether the optional Playwright package is installed."""
    try:
        version = importlib.metadata.version("playwright")
        installed = True
    except importlib.metadata.PackageNotFoundError:
        version = None
        installed = False

    return {
        "installed": installed,
        "version": version,
        "browser_runtime": "Check with 'hive browser install'",
    }


def install_browser() -> None:
    """Install the Chromium runtime for the installed Playwright package."""
    if not browser_status()["installed"]:
        raise RuntimeError(
            "Playwright is not installed. Run: "
            "python -m pip install -e '.[browser]'"
        )

    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )


def inspect_url(url: str, timeout: int = 15000) -> dict:
    """Inspect a page without submitting forms or intentionally changing state."""
    target = validate_url(url)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: "
            "python -m pip install -e '.[browser]'"
        ) from exc

    output_dir = hive_home() / "browser"
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                response = page.goto(
                    target,
                    wait_until="domcontentloaded",
                    timeout=timeout,
                )

                title = page.title()
                final_url = page.url

                try:
                    page_text = page.locator("body").inner_text(timeout=5000)
                except Exception:
                    page_text = ""

                page_text = page_text[:50000]

                screenshot_path = run_dir / "screenshot.png"
                page.screenshot(
                    path=str(screenshot_path),
                    full_page=True,
                    timeout=10000,
                )

                result = {
                    "requested_url": target,
                    "final_url": final_url,
                    "title": title,
                    "http_status": response.status if response else None,
                    "text": page_text,
                    "screenshot": str(screenshot_path),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                }

                evidence_path = run_dir / "evidence.json"
                evidence_path.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                result["evidence"] = str(evidence_path)
                return result
            finally:
                browser.close()

    except Exception as exc:
        raise RuntimeError(f"Browser inspection failed: {exc}") from exc
