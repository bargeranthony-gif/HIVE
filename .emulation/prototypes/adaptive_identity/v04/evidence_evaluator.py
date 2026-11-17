"""Read-only evidence assessment for HAIE v0.4."""

import re
import sqlite3
from pathlib import Path
from urllib.parse import quote


def _normalize(value):
    return re.sub(r"\s+", " ", value.strip()).casefold()


class EvidenceEvaluator:
    """Assess evidence without modifying the HAIE database."""

    def __init__(self, database_path, minimum_independent_groups=2):
        if (
            isinstance(minimum_independent_groups, bool)
            or not isinstance(minimum_independent_groups, int)
            or minimum_independent_groups < 2
        ):
            raise ValueError(
                "minimum_independent_groups must be an integer >= 2."
            )

        self.database_path = Path(database_path).expanduser().resolve()
        self.minimum_independent_groups = minimum_independent_groups

    def _connect_read_only(self):
        if not self.database_path.is_file():
            raise FileNotFoundError(self.database_path)

        uri = "file:" + quote(str(self.database_path)) + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        return conn

    def evaluate(self, identity_id, subject_id=None):
        if not isinstance(identity_id, str) or not identity_id.strip():
            raise ValueError("identity_id must be non-empty text.")

        if subject_id is not None and (
            not isinstance(subject_id, str) or not subject_id.strip()
        ):
            raise ValueError("subject_id must be non-empty text or None.")

        with self._connect_read_only() as conn:
            identity = conn.execute(
                "SELECT identity_id FROM identities WHERE identity_id = ?",
                (identity_id,),
            ).fetchone()

            if identity is None:
                raise KeyError(f"Unknown identity: {identity_id}")

            query = """
                SELECT
                    c.claim_id,
                    c.claim_key,
                    c.claim_value,
                    c.stance,
                    c.context_key,
                    c.confidence AS claim_confidence,
                    e.experience_id,
                    e.subject_id,
                    e.interaction_type,
                    e.session_id,
                    e.confidence AS experience_confidence,
                    s.source_id,
                    s.group_id,
                    g.independence_status
                FROM claims AS c
                JOIN experiences AS e
                    ON e.experience_id = c.experience_id
                LEFT JOIN evidence_sources AS s
                    ON s.identity_id = e.identity_id
                   AND s.source_id = e.source_id
                LEFT JOIN evidence_source_groups AS g
                    ON g.identity_id = s.identity_id
                   AND g.group_id = s.group_id
                WHERE e.identity_id = ?
            """
            params = [identity_id]

            if subject_id is not None:
                query += " AND e.subject_id = ?"
                params.append(subject_id)

            query += """
                ORDER BY
                    e.observed_at,
                    e.experience_id,
                    c.claim_id
            """

            rows = [dict(row) for row in conn.execute(query, params)]

        propositions = {}

        for row in rows:
            key = (
                row["subject_id"],
                _normalize(row["interaction_type"]),
                _normalize(row["claim_key"]),
                _normalize(row["context_key"]),
            )
            propositions.setdefault(key, []).append(row)

        assessments = [
            self._assess_proposition(key, records)
            for key, records in sorted(
                propositions.items(),
                key=lambda item: tuple(
                    value or "" for value in item[0]
                ),
            )
        ]

        return {
            "identity_id": identity_id,
            "subject_id": subject_id,
            "minimum_independent_groups": (
                self.minimum_independent_groups
            ),
            "proposition_count": len(assessments),
            "assessments": assessments,
        }

    def _assess_proposition(self, proposition_key, records):
        subject_id, interaction_type, claim_key, context_key = (
            proposition_key
        )

        experience_ids = {row["experience_id"] for row in records}
        sessions = {
            row["session_id"]
            for row in records
            if row["session_id"] is not None
            and row["session_id"].strip()
        }

        all_groups = {}
        group_records = {}
        missing_provenance = 0
        uncertain_count = sum(
            row["stance"] == "uncertain" for row in records
        )

        for row in records:
            group_id = row["group_id"]
            status = row["independence_status"]

            if group_id is None or status is None:
                missing_provenance += 1
                continue

            all_groups[group_id] = status
            group_records.setdefault(group_id, []).append(row)

        # Identify internally inconsistent source groups before counting
        # any directional evidence from them.
        source_level_conflicts = []
        conflicted_groups = set()

        for group_id, group_status in sorted(all_groups.items()):
            directional_records = [
                row for row in group_records[group_id]
                if row["stance"] != "uncertain"
            ]

            group_supports = {
                _normalize(row["claim_value"])
                for row in directional_records
                if row["stance"] == "supports"
            }
            group_refutes = {
                _normalize(row["claim_value"])
                for row in directional_records
                if row["stance"] == "refutes"
            }

            conflict = (
                len(group_supports) > 1
                or bool(group_supports & group_refutes)
            )

            if conflict:
                conflicted_groups.add(group_id)
                source_level_conflicts.append({
                    "group_id": group_id,
                    "independence_status": group_status,
                    "supporting_values": sorted(group_supports),
                    "refuting_values": sorted(group_refutes),
                })

        values = {}

        for row in records:
            group_id = row["group_id"]
            status = row["independence_status"]

            if (
                group_id is None
                or status is None
                or row["stance"] == "uncertain"
            ):
                continue

            normalized_value = _normalize(row["claim_value"])
            entry = values.setdefault(
                normalized_value,
                {
                    "normalized_value": normalized_value,
                    "original_values": set(),
                    "support_groups": set(),
                    "refute_groups": set(),
                },
            )
            entry["original_values"].add(row["claim_value"])

            # Conflicted groups remain visible above, but cannot contribute
            # directional evidence or independent contradiction pairs.
            if (
                status != "independent"
                or group_id in conflicted_groups
            ):
                continue

            if row["stance"] == "supports":
                entry["support_groups"].add(group_id)
            elif row["stance"] == "refutes":
                entry["refute_groups"].add(group_id)

        independent_conflicts = []

        supported_values = {
            value: sorted(entry["support_groups"])
            for value, entry in values.items()
            if entry["support_groups"]
        }

        supported_value_names = sorted(supported_values)

        for index, first_value in enumerate(supported_value_names):
            for second_value in supported_value_names[index + 1:]:
                first_groups = set(supported_values[first_value])
                second_groups = set(supported_values[second_value])

                opposing_groups = [
                    (first_group, second_group)
                    for first_group in sorted(first_groups)
                    for second_group in sorted(second_groups)
                    if first_group != second_group
                ]

                if opposing_groups:
                    independent_conflicts.append({
                        "type": "competing_supported_values",
                        "values": [first_value, second_value],
                        "source_group_pairs": opposing_groups,
                    })

        for value, entry in sorted(values.items()):
            opposing_groups = [
                (support_group, refute_group)
                for support_group in sorted(entry["support_groups"])
                for refute_group in sorted(entry["refute_groups"])
                if support_group != refute_group
            ]

            if opposing_groups:
                independent_conflicts.append({
                    "type": "opposing_stances",
                    "value": value,
                    "source_group_pairs": opposing_groups,
                })

        supporting_groups = set()
        refuting_groups = set()

        for entry in values.values():
            supporting_groups.update(entry["support_groups"])
            refuting_groups.update(entry["refute_groups"])

        directional_groups = supporting_groups | refuting_groups
        contradiction = bool(independent_conflicts)

        claim_confidences = [
            row["claim_confidence"] for row in records
        ]
        experience_confidences = [
            row["experience_confidence"] for row in records
        ]

        value_assessments = []
        for value in sorted(values):
            entry = values[value]
            value_assessments.append({
                "normalized_value": value,
                "original_values": sorted(entry["original_values"]),
                "supporting_independent_groups": sorted(
                    entry["support_groups"]
                ),
                "refuting_independent_groups": sorted(
                    entry["refute_groups"]
                ),
                "supporting_group_count": len(entry["support_groups"]),
                "refuting_group_count": len(entry["refute_groups"]),
            })

        return {
            "subject_id": subject_id,
            "interaction_type": interaction_type,
            "claim_key": claim_key,
            "context_key": context_key,
            "experience_count": len(experience_ids),
            "claim_record_count": len(records),
            "distinct_session_count": len(sessions),
            "distinct_source_group_count": len(all_groups),
            "independent_source_group_count": sum(
                status == "independent"
                for status in all_groups.values()
            ),
            "supporting_independent_source_count": len(
                supporting_groups
            ),
            "refuting_independent_source_count": len(
                refuting_groups
            ),
            "uncertain_evidence_count": uncertain_count,
            "correlated_source_group_count": sum(
                status == "correlated"
                for status in all_groups.values()
            ),
            "unverified_source_group_count": sum(
                status == "unverified"
                for status in all_groups.values()
            ),
            "missing_provenance_record_count": missing_provenance,
            "source_level_conflicts": source_level_conflicts,
            "independent_conflicts": independent_conflicts,
            "contradiction_detected": contradiction,
            "review_eligible": (
                len(directional_groups)
                >= self.minimum_independent_groups
                or contradiction
            ),
            "descriptive_claim_confidence_range": {
                "minimum": min(claim_confidences),
                "maximum": max(claim_confidences),
            },
            "descriptive_experience_confidence_range": {
                "minimum": min(experience_confidences),
                "maximum": max(experience_confidences),
            },
            "values": value_assessments,
        }
