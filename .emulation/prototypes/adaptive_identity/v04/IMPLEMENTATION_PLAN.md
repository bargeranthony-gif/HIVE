# HAIE v0.4 — Implementation Plan

## Current implementation status

- Phases 1-3 implemented in the isolated prototype.
- Phase 3 includes evidence source groups, source provenance,
  experience and claim storage, and read-only evidence evaluation.
- HAIE v0.4 tests: 77 passed.
- Full HIVE regression: 297 passed.
- No production Core integration has occurred.
- Next development phase: Phase 4, personality development.

## Phase 1: Foundation

1. Create an isolated v0.4 engine and SQLite database.
2. Add schema versioning.
3. Implement identity and personality profile storage.
4. Validate input types and constraints.
5. Test persistence and identity continuity.

## Phase 2: Social memory

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
8. Verified 77 v0.4 tests and 297 tests across the full HIVE regression suite.

## Phase 4: Personality development

1. Implement personality proposals.
2. Add relational evidence references.
3. Add source-independence requirements.
4. Implement transactional owner approval.
5. Invalidate proposals when dependent evidence is deleted.
6. Test rejection, acceptance, stale proposals, and deletion.

## Phase 5: Unified expression

1. Implement transient situational context.
2. Implement a pure expression composer.
3. Combine one personality with relevant social memories and context.
4. Verify identity continuity across different situations.
5. Verify expression has no persistent side effects.

## Phase 6: Review

1. Run all v0.4 tests.
2. Run the complete HIVE regression suite; the current verified baseline
   is 297 passing tests.
3. Review privacy, deletion, and provenance behavior.
4. Record limitations and unresolved risks.
5. Do not integrate into HIVE Core without explicit approval.
