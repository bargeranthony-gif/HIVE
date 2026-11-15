from __future__ import annotations

import argparse
import logging

from . import __version__
from .browser import browser_status, install_browser, inspect_url, browser_python
from .ai import ask, get_status
from .db import initialize, connect
from .logging_setup import configure_logging
from .repositories import add_repository, list_repositories
from .capabilities import add_capability, list_capabilities
from .discovery import search_github
from .inspector import inspect_repository
from .graph import (
    build_graph,
    show_graph,
    dependencies_for_file,
    dependents_for_file,
    recursive_dependencies_for_file,
    recursive_dependents_for_file,
    circular_dependency_groups,
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="hive",
        description="HIVE software capability registry"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"HIVE {__version__}"
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize the local HIVE database")
    sub.add_parser("status", help="Show local HIVE database status")

    browser = sub.add_parser("browser", help="Inspect websites with Playwright")
    browser_sub = browser.add_subparsers(
        dest="browser_command", required=True
    )
    browser_sub.add_parser("status", help="Check Playwright installation")
    browser_sub.add_parser("install", help="Install the Chromium browser runtime")
    browser_inspect = browser_sub.add_parser(
        "inspect", help="Inspect a webpage and save local evidence"
    )
    browser_inspect.add_argument("url")
    browser_inspect.add_argument(
        "--timeout", type=int, default=15000,
        help="Navigation timeout in milliseconds (default: 15000)"
    )


    ask_parser = sub.add_parser(
        "ask",
        help="Send a prompt to the configured AI model"
    )
    ask_parser.add_argument("prompt", nargs="+", help="Prompt text")

    ai_parser = sub.add_parser("ai", help="Manage AI provider")
    ai_sub = ai_parser.add_subparsers(dest="ai_command", required=True)
    ai_sub.add_parser("status", help="Check AI server and model availability")

    inspect = sub.add_parser("inspect", help="Inspect a registered repository")
    inspect.add_argument("repository_id", type=int)
    inspect.add_argument("path")

    repo = sub.add_parser("repo", help="Manage repositories")
    rs = repo.add_subparsers(dest="repo_command", required=True)

    add = rs.add_parser("add", help="Add a GitHub repository URL")
    add.add_argument("url")
    rs.add_parser("list", help="List registered repositories")

    discover = sub.add_parser(
        "discover",
        help="Search GitHub and save repository metadata"
    )
    discover.add_argument("query")
    discover.add_argument("--limit", type=int, default=10)

    cap = sub.add_parser("capability", help="Manage capability records")
    cs = cap.add_subparsers(dest="cap_command", required=True)

    ca = cs.add_parser("add")
    ca.add_argument("repository_id", type=int)
    ca.add_argument("name")
    ca.add_argument("--description")
    ca.add_argument(
        "--evidence-level",
        choices=[
            "claimed",
            "inferred",
            "build_verified",
            "test_verified",
            "benchmarked"
        ],
        default="claimed"
    )
    ca.add_argument("--evidence")
    cs.add_parser("list")

    graph = sub.add_parser("graph", help="Build and inspect source relationships")
    gs = graph.add_subparsers(dest="graph_command", required=True)

    graph_build = gs.add_parser(
        "build",
        help="Build Python import relationships"
    )
    graph_build.add_argument("repository_id", type=int)
    graph_build.add_argument("path")

    graph_show = gs.add_parser(
        "show",
        help="Show stored source relationships"
    )
    graph_show.add_argument("repository_id", type=int)

    graph_dependencies = gs.add_parser(
        "dependencies",
        help="Show files imported by a source file"
    )
    graph_dependencies.add_argument("repository_id", type=int)
    graph_dependencies.add_argument("path")

    graph_dependents = gs.add_parser(
        "dependents",
        help="Show files importing a source file"
    )
    graph_dependents.add_argument("repository_id", type=int)
    graph_dependents.add_argument("path")

    graph_recursive_dependencies = gs.add_parser(
        "recursive-dependencies",
        help="Show transitive dependencies of a source file"
    )
    graph_recursive_dependencies.add_argument("repository_id", type=int)
    graph_recursive_dependencies.add_argument("path")
    graph_recursive_dependencies.add_argument(
        "--max-depth", type=int, default=None
    )

    graph_recursive_dependents = gs.add_parser(
        "recursive-dependents",
        help="Show transitive dependents of a source file"
    )
    graph_recursive_dependents.add_argument("repository_id", type=int)
    graph_recursive_dependents.add_argument("path")
    graph_recursive_dependents.add_argument(
        "--max-depth", type=int, default=None
    )

    graph_cycles = gs.add_parser(
        "cycles",
        help="Show circular dependency groups"
    )
    graph_cycles.add_argument("repository_id", type=int)

    return parser


def main(argv=None):
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        print(f"HIVE database initialized: {initialize()}")

    elif args.command == "status":
        path = initialize()
        with connect() as c:
            repos = c.execute(
                "SELECT COUNT(*) FROM repositories"
            ).fetchone()[0]
            caps = c.execute(
                "SELECT COUNT(*) FROM capabilities"
            ).fetchone()[0]

        print(
            f"HIVE {__version__}\n"
            f"Database: {path}\n"
            f"Repositories: {repos}\n"
            f"Capabilities: {caps}"
        )

    elif args.command == "browser":
        if args.browser_command == "status":
            result = browser_status()
            print(f"Playwright installed: {'Yes' if result['installed'] else 'No'}")
            if result["version"]:
                print(f"Playwright version: {result['version']}")
            else:
                print("Install Playwright with the browser interpreter:")
                print(f"  {browser_python()} -m pip install -e '.[browser]'")
            print(result["browser_runtime"])

        elif args.browser_command == "install":
            try:
                install_browser()
                print("Chromium browser runtime installed.")
            except Exception as exc:
                parser.exit(1, f"Browser installation failed: {exc}\\n")

        elif args.browser_command == "inspect":
            try:
                result = inspect_url(args.url, timeout=args.timeout)
                print(f"Title: {result['title']}")
                print(f"Final URL: {result['final_url']}")
                print(f"HTTP status: {result['http_status']}")
                print(f"Screenshot: {result['screenshot']}")
                print(f"Evidence: {result['evidence']}")
                print("\\nPage text (first 50,000 characters):\\n")
                print(result["text"])
            except (ValueError, RuntimeError) as exc:
                parser.exit(1, f"Browser inspection failed: {exc}\\n")

    elif args.command == "ask":
        try:
            print(ask(" ".join(args.prompt)))
        except Exception as exc:
            parser.exit(1, f"AI request failed: {exc}\\n")

    elif args.command == "ai" and args.ai_command == "status":
        try:
            result = get_status()
        except Exception as exc:
            parser.exit(1, f"AI status check failed: {exc}\\n")

        print("AI provider: llama.cpp")
        print(f"Server: {'Available' if result['available'] else 'Unavailable'}")
        print(f"Server URL: {result['base_url']}")
        print(f"Configured model: {result['configured_model']}")
        print(f"Model loaded: {'Yes' if result['model_loaded'] else 'No'}")

        if result["available_models"]:
            print("Models reported by server:")
            for model in result["available_models"]:
                print(f"  {model}")

        if not result["model_loaded"]:
            parser.exit(1, "Configured model was not found on the AI server.\\n")

    elif args.command == "inspect":
        initialize()
        try:
            result = inspect_repository(args.repository_id, args.path)
            print(
                f"Inspection complete: "
                f"{result['files_inspected']} files"
            )
            print(f"Skipped: {result['files_skipped']}")
            print(
                f"Languages: "
                f"{', '.join(result['languages']) or 'none'}"
            )
            print(f"Symbols found: {result['symbols_found']}")
        except ValueError as exc:
            parser.error(str(exc))

    elif args.command == "repo" and args.repo_command == "add":
        initialize()
        print(
            f"Repository saved with ID "
            f"{add_repository(args.url)}"
        )

    elif args.command == "repo" and args.repo_command == "list":
        initialize()
        rows = list_repositories()

        if not rows:
            print("No repositories registered.")

        for r in rows:
            print(
                f"[{r['id']}] {r['owner']}/{r['name']} | "
                f"{r['language'] or 'unknown'} | "
                f"stars={r['stars'] if r['stars'] is not None else 'unknown'} | "
                f"{r['url']}"
            )

    elif args.command == "discover":
        initialize()
        try:
            results = search_github(args.query, args.limit)
            print(f"Saved {len(results)} repositories:")

            for r in results:
                print(
                    f"[{r['id']}] {r['full_name']} | "
                    f"{r['language'] or 'unknown'} | "
                    f"stars={r['stars']}"
                )

        except Exception as exc:
            logging.exception("GitHub discovery failed")
            parser.exit(1, f"Discovery failed: {exc}\n")

    elif args.command == "capability" and args.cap_command == "add":
        initialize()
        try:
            capability_id = add_capability(
                args.repository_id,
                args.name,
                args.description,
                args.evidence_level,
                args.evidence
            )
            print(f"Capability saved with ID {capability_id}")
        except ValueError as exc:
            parser.error(str(exc))

    elif args.command == "capability" and args.cap_command == "list":
        initialize()
        rows = list_capabilities()

        if not rows:
            print("No capabilities registered.")

        for r in rows:
            print(
                f"[{r['id']}] repo={r['repository_id']} "
                f"{r['owner']}/{r['repository']} | "
                f"{r['name']} | {r['evidence_level']} | "
                f"{r['evidence'] or 'no evidence recorded'}"
            )

    elif args.command == "graph" and args.graph_command == "build":
        initialize()
        try:
            result = build_graph(args.repository_id, args.path)
            print("Knowledge graph build complete.")
            print(f"Repository ID: {result['repository_id']}")
            print(f"Files considered: {result['files_considered']}")
            print(
                f"Relationships found: "
                f"{result['relationships_found']}"
            )
        except ValueError as exc:
            parser.error(str(exc))

    elif args.command == "graph" and args.graph_command == "show":
        initialize()
        try:
            rows = show_graph(args.repository_id)

            if not rows:
                print("No source relationships found.")

            for row in rows:
                print(
                    f"{row['source_path']} "
                    f"--[{row['relation_type']}]--> "
                    f"{row['target_path']} "
                    f"(line {row['line_number']}; "
                    f"{row['imported_name']})"
                )

        except ValueError as exc:
            parser.error(str(exc))

    elif args.command == "graph" and args.graph_command in (
        "dependencies",
        "dependents",
        "recursive-dependencies",
        "recursive-dependents",
        "cycles",
    ):
        initialize()
        try:
            if args.graph_command == "dependencies":
                rows = dependencies_for_file(
                    args.repository_id, args.path
                )
                label = "Dependencies"

            elif args.graph_command == "dependents":
                rows = dependents_for_file(
                    args.repository_id, args.path
                )
                label = "Dependents"

            elif args.graph_command == "recursive-dependencies":
                rows = recursive_dependencies_for_file(
                    args.repository_id,
                    args.path,
                    max_depth=args.max_depth,
                )
                label = "Recursive dependencies"

            elif args.graph_command == "recursive-dependents":
                rows = recursive_dependents_for_file(
                    args.repository_id,
                    args.path,
                    max_depth=args.max_depth,
                )
                label = "Recursive dependents"

            else:
                groups = circular_dependency_groups(args.repository_id)

                print("Circular dependency groups:")

                if not groups:
                    print("No circular dependencies found.")

                for index, group in enumerate(groups, start=1):
                    print(f"\nCycle group {index}:")
                    for file_path in group["files"]:
                        print(f"  {file_path}")

                    print("  Relationships:")
                    for row in group["relationships"]:
                        print(
                            f"    {row['source_path']} "
                            f"--[{row['relation_type']}]--> "
                            f"{row['target_path']} "
                            f"(line {row['line_number']}; "
                            f"{row['imported_name']})"
                        )

                return

            print(f"{label} for {args.path}:")

            if not rows:
                print("No relationships found.")

            for row in rows:
                depth_text = (
                    f"; depth {row['depth']}"
                    if "depth" in row.keys()
                    else ""
                )
                print(
                    f"{row['source_path']} "
                    f"--[{row['relation_type']}]--> "
                    f"{row['target_path']} "
                    f"(line {row['line_number']}; "
                    f"{row['imported_name']}{depth_text})"
                )

        except ValueError as exc:
            parser.error(str(exc))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
