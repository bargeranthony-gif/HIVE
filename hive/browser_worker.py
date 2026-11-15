from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def status():
    try:
        version = importlib.metadata.version("playwright")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            executable = Path(p.chromium.executable_path)
            chromium_installed = executable.is_file()

        return {
            "installed": True,
            "version": version,
            "chromium_installed": chromium_installed,
            "chromium_executable": str(executable),
        }
    except Exception as exc:
        return {
            "installed": False,
            "version": None,
            "chromium_installed": False,
            "error": str(exc),
        }


def install():
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )


def inspect(url, timeout, output_dir):
    from playwright.sync_api import sync_playwright

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )

    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        try:
            page = browser.new_page()

            response = page.goto(
                url,
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
                "requested_url": url,
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


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status")
    commands.add_parser("install")

    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("--url", required=True)
    inspect_parser.add_argument("--timeout", type=int, default=15000)
    inspect_parser.add_argument("--output-dir", required=True)

    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(status()))

    elif args.command == "install":
        install()
        print(json.dumps({"installed": True}))

    elif args.command == "inspect":
        if args.timeout <= 0:
            parser.error("Timeout must be positive.")

        result = inspect(
            args.url,
            args.timeout,
            args.output_dir,
        )

        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Browser worker error: {exc}", file=sys.stderr)
        sys.exit(1)
