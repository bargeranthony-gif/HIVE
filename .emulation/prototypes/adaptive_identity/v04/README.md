# HAIE v0.4 — Unified Adaptive Identity

Status: Experimental implementation. Phases 1-4 implemented and reviewed. Phase 5, unified expression, is next. Not integrated into HIVE Core.

Verification: 119 HAIE v0.4 tests passed; 339 combined HIVE Core and HAIE tests passed.

## Purpose

Develop one persistent, recognizable HIVE identity that evolves through
curated experiences and expresses itself naturally across different people,
relationships, activities, and environments.

HIVE does not switch between separate personalities. It remains one
continuous identity whose expression adapts to circumstances.

## Unified identity model

The system combines four connected responsibilities:

1. Persistent Personality
   - Foundational character and temperament.
   - Evolving traits, preferences, humor, interests, and communication habits.
   - Gradual changes supported by evaluated experience.

2. Social and Relationship Memory
   - People and relationship history.
   - Shared experiences and recurring interactions.
   - Individual communication preferences and boundaries.
   - Familiarity and relationship context.

3. Situational Awareness
   - Current activity and environment.
   - Current conversational or operational context.
   - People present and relevant circumstances.
   - Temporary needs and behavioral constraints.

4. Unified Personality Expression
   - Combines personality, relevant social memory, and situational context.
   - Produces context-appropriate communication and behavior.
   - Preserves recognizable identity and continuity.
   - Does not create or select separate personalities.

## Core design rules

- One persistent identity across all contexts.
- Context changes expression, not identity.
- Relationship memory informs familiarity and interaction.
- Individual preferences must not be mistaken for global personality traits.
- Temporary situational behavior must not silently become a permanent trait.
- Experiences may inform gradual personality development.
- Personality changes require evidence evaluation and owner review.
- Memory must be selective, useful, traceable, and correctable.
- Conflicting or uncertain evidence must remain visible.
- Social familiarity must never grant technical permissions or authority.

## Separation from HIVE Core

HAIE remains an isolated subsystem.

It must never modify:
- Governance policies.
- Authorization decisions.
- Security boundaries.
- Owner controls.
- Capability permissions.
- Core reasoning or planning rules.

Personality and social memory influence expression, not authorization.

## Development phases

1. Foundation — identity, personality profile, validation, and persistence.
2. Social memory — relationships, categorized memories, provenance,
   certainty, correction, and deletion.
3. Evidence — experience and claim storage, source independence,
   contradiction-aware evaluation, and provenance.
4. Personality development — evidence-backed revision proposals,
   transactional approval and rejection, and proposal invalidation.
5. Unified expression — transient situational context and a pure
   expression composer using the canonical API:

   `compose_expression(personality, relationship_memories, situation, objective)`

6. Review — privacy, deletion, provenance, regression testing, and
   documentation of limitations.

Phases 1-4 are implemented and reviewed. Phase 5 is the next development
phase. Phase 6 follows implementation.

## Phase 4 authorization boundary

HAIE can validate proposals and record acceptance or rejection decisions.
Its acceptance method does not authenticate the owner. HIVE's control
layer must enforce owner authentication and authorization before invoking
that method.

HAIE cannot grant itself authority or modify HIVE governance, security
boundaries, or owner controls.

No production integration is authorized by this specification.
