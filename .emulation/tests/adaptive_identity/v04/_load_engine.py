"""Test loader for the isolated HAIE v0.4 prototype."""

import importlib.util
from pathlib import Path


def _load_engine():
    path = (
        Path(__file__).parents[3]
        / "prototypes"
        / "adaptive_identity"
        / "v04"
        / "identity_engine.py"
    )

    spec = importlib.util.spec_from_file_location(
        "haie_v04_identity_engine",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
