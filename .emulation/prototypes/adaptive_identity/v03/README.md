# HAIE v0.3 — Contradiction-Aware Evidence

Status: Experimental. Not integrated into HIVE Core.

## Isolation
- Separate prototype directory and SQLite database.
- v0.1 and v0.2 remain unchanged.
- No governance, authorization, live-account, or external-service access.
- Evaluation is read-only.

## Structured claims
Claims are attached to experiences and contain:
- claim_key and claim_value
- stance: supports, refutes, or uncertain
- context_key
- confidence

## Independence and contradiction
- A session contributes at most one stance to a proposition.
- Duplicate records within one session do not increase independent-session counts.
- A session with both supporting and refuting evidence is internally conflicted.
- Unscoped records are not treated as independent sessions.
- Different contexts are evaluated separately.

## Review
Contradictions require owner review. Sufficient non-conflicting evidence
may become eligible for owner review. No personality trait is changed.
