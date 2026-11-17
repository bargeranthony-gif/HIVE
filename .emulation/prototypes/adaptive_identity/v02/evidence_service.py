"""Read-only bridge between HAIE storage and evidence evaluation."""

import importlib.util
from pathlib import Path

_evaluator_path = Path(__file__).with_name("evidence_evaluator.py")
_evaluator_spec = importlib.util.spec_from_file_location(
    "haie_v02_evidence_evaluator",
    _evaluator_path,
)

if _evaluator_spec is None or _evaluator_spec.loader is None:
    raise ImportError("Could not load HAIE evidence evaluator.")

_evaluator_module = importlib.util.module_from_spec(_evaluator_spec)
_evaluator_spec.loader.exec_module(_evaluator_module)

evaluate_evidence = _evaluator_module.evaluate_evidence


class EvidenceService:
    def __init__(self, identity_store):
        self.identity_store = identity_store

    def assess_identity(
        self,
        identity_id,
        minimum_independent_sessions=2,
    ):
        if not isinstance(identity_id, str) or not identity_id.strip():
            raise ValueError("Identity ID is required.")

        experiences = self.identity_store.list_experiences(identity_id)

        return evaluate_evidence(
            experiences,
            minimum_independent_sessions=minimum_independent_sessions,
        )

    def assess_subject(
        self,
        identity_id,
        subject_id,
        minimum_independent_sessions=2,
    ):
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ValueError("Subject ID is required.")

        result = self.assess_identity(
            identity_id,
            minimum_independent_sessions,
        )

        result["assessments"] = [
            item for item in result["assessments"]
            if item["subject_id"] == subject_id
        ]
        result["group_count"] = len(result["assessments"])

        return result
