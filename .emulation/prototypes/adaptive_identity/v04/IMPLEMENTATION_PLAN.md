# HAIE v0.4 — Implementation Plan

## Current implementation status

- Phases 1-4 implemented in the isolated prototype.
- Phase 4 implementation and code review completed with no blocking
  defects identified in the reviewed code paths.
- HAIE v0.4 tests: 119 passed.
- Combined HIVE Core and HAIE regression: 339 passed.
- No production Core integration has occurred.
- Next development phase: Phase 5, unified expression.

## Phase 1: Foundation — COMPLETE

1. Create an isolated v0.4 engine and SQLite database.
2. Add schema versioning.
3. Implement identity and personality profile storage.
4. Validate input types and constraints.
5. Test persistence and identity continuity.

## Phase 2: Social memory — COMPLETE

1. Implement relationship records.
2. Implement categorized social memories.
3. Add provenance and certainty classifications.
4. Implement correction and deletion.
5. Test subject isolation and memory lifecycle.

## Phase 3: Evidence — COMPLETE

1. Implemented the contradiction-aware, read-only evaluator.
2. Corrected whitespace normalization.
3. Added source correlation groups and audited reclassification.
4. Distinguished sessions from independent source groups.
5. Tested repeated, correlated, uncertain, and contradictory evidence.
6. Added protection against internally conflicted groups creating false
   independent contradictions.
7. Added subject-specific evaluation and separate descriptive confidence
   ranges for claims and experiences.
8. Verified the original 77-test v0.4 suite and 297-test combined
   regression suite.

## Phase 4: Personality development — IMPLEMENTED AND REVIEWED

1. Implement personality revision proposals.
2. Add relational evidence references.
3. Add source-independence requirements.
4. Implement transactional proposal acceptance and rejection.
5. Invalidate proposals when dependent evidence is deleted, reclassified,
   or otherwise becomes unsuitable.
6. Test rejection, acceptance, stale proposals, migration, and deletion.
7. Verify schema migration rollback and unsupported-version handling.
8. Verify that approval revalidates the supporting evidence and current
   personality state before applying a revision.

### Phase 4 authorization boundary

The HAIE acceptance method records an approval decision but does not
authenticate the owner. HIVE's control layer must enforce owner
authentication and authorization before invoking the acceptance method.
HAIE does not independently grant itself or another component authority.

### Phase 4 verification

- HAIE v0.4 tests: 119 passed.
- Combined HIVE Core and HAIE regression: 339 passed.
- Reviewed implementation and migration paths: no blocking defects
  identified.
- `git diff --check`: clean at the time of review.

## Phase 5: Unified expression — NEXT

1. Implement transient situational context.
2. Implement a pure expression composer.
3. Combine one personality with relevant social memories and context.
4. Verify identity continuity across different situations.
5. Verify expression has no persistent side effects.

### Canonical expression API

`compose_expression(personality, relationship_memories, situation, objective)`

The composer must produce one context-aware expression of the same
persistent identity.

It must not:
- Create a new personality.
- Change personality traits.
- Create or modify memories.
- Grant permissions.
- Change governance decisions.
- Invent relationship history.
- Treat uncertain memories as established facts.

The composer must be a pure computation with no database writes.

## Phase 6: Review

1. Run all HAIE v0.4 tests.
2. Run the complete combined regression suite using:
   `pytest -q tests .emulation/tests`
3. Review privacy, deletion, and provenance behavior.
4. Record limitations and unresolved risks.
5. Do not integrate into HIVE Core without explicit approval.
