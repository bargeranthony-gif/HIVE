# HIVE Engine v0.1

A lightweight foundation for HIVE: configuration, a SQLite knowledge registry,
GitHub repository discovery, capability records, and evidence tracking.

## Design constraints
- Python 3.10+
- Standard library at runtime; no AI model or database server required
- SQLite database stored locally
- Network access is used only when `hive discover` is explicitly run
- GitHub token is optional; set `GITHUB_TOKEN` to improve API rate limits

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
hive init
hive status
pytest
```

## Commands
```bash
hive init
hive status
hive repo add https://github.com/owner/project
hive repo list
hive discover "tree-sitter language parser"
hive capability add <repo_id> "source parsing" --evidence "README states parser support"
hive capability list
```

Discovery is opt-in. It searches GitHub's public repository API and stores basic
metadata; it does not clone or execute downloaded code.

## Evidence discipline
- `claimed`: stated by a project or its documentation
- `inferred`: inferred from metadata or static inspection
- `build_verified`: a build completed in a controlled environment
- `test_verified`: relevant automated tests passed
- `benchmarked`: performance was measured under recorded conditions

HIVE must not promote a claim to a verified level without recorded evidence.

## Data location
Default: `~/.hive/hive.db`. Set `HIVE_HOME` to move HIVE state, for example:
`export HIVE_HOME="/path/to/external-ssd/HIVE"`

## Current limitations
This is a foundation, not yet a source-code analyzer or agent runtime.
No repository is cloned, parsed, built, sandboxed, or executed in this version.


## Browser Automation

HIVE runs browser automation through an isolated Python environment.
This keeps Playwright and its browser runtime separate from the main HIVE
environment.

The browser extra is pinned to Playwright 1.25.2, which is the version
verified with the legacy browser runtime used on macOS Catalina.

Create the browser environment from the HIVE project directory:

```bash
python3.10 -m venv .venv-browser-legacy
.venv-browser-legacy/bin/python -m pip install --upgrade pip
.venv-browser-legacy/bin/python -m pip install -e '.[browser]'
```

Install Chromium through HIVE:

```bash
.venv/bin/hive browser install
```

Check the browser installation:

```bash
.venv/bin/hive browser status
```

Inspect a webpage and save its evidence:

```bash
.venv/bin/hive browser inspect https://example.com
```

The browser worker selects `.venv-browser-legacy` automatically when it
exists. `HIVE_BROWSER_PYTHON` can be set to override that interpreter.
Do not install the browser extra into the main HIVE environment when using
this isolated browser configuration.
