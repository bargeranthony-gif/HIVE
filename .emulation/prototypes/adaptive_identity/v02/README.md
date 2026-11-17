# HAIE v0.2 — Evidence-Based Personality Adaptation

Status: Experimental development. Not integrated into HIVE Core.

## Development strategy

- Preserve v0.1 unchanged as the rollback baseline.
- Develop v0.2 in this isolated directory.
- Use a separate SQLite database.
- Introduce explicit schema versioning.
- Keep personality revisions subject to explicit owner acceptance.
- Do not access or modify HIVE governance or authorization systems.
- Do not connect to live games, accounts, or external services.

## Planned capabilities

- Session-aware experience records.
- Separate observations and interpretations.
- Evidence provenance and confidence.
- Feedback classification.
- Evidence independence and contradiction evaluation.
- Controlled personality adaptation proposals.
- Explicit memory review and deletion.
