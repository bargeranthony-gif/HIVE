"""Read-only bridge between HAIE v0.3 storage and evaluation."""

import importlib.util
from pathlib import Path

_path = Path(__file__).with_name("evidence_evaluator.py")
_spec = importlib.util.spec_from_file_location("haie_v03_evaluator", _path)

if _spec is None or _spec.loader is None:
    raise ImportError("Could not load HAIE v0.3 evaluator.")

_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

evaluate_claims = _module.evaluate_claims


class EvidenceService:
    def __init__(self, identity_store):
        self.identity_store = identity_store

    def assess_identity(self, identity_id, minimum_independent_sessions=2):
        if not isinstance(identity_id, str) or not identity_id.strip():
            raise ValueError("Identity ID is required.")

        self.identity_store.get_identity(identity_id)
        claims = self.identity_store.list_claims(identity_id)

        return evaluate_claims(
            claims,
            minimum_independent_sessions=minimum_independent_sessions,
        )

    def assess_subject(
        self, identity_id, subject_id, minimum_independent_sessions=2
    ):
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ValueError("Subject ID is required.")

        result = self.assess_identity(
            identity_id, minimum_independent_sessions
        )
        result["assessments"] = [
            item for item in result["assessments"]
            if item["subject_id"] == subject_id
        ]
        result["group_count"] = len(result["assessments"])
        return result
