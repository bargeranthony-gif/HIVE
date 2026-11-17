# HAIE v0.4 — API Contract

This document defines intended behavior before implementation.

## IdentityStore

### create_identity(identity_id, display_name, ...)

Creates exactly one persistent identity.

Reject duplicate IDs and invalid input.

### get_identity(identity_id)

Returns the persistent identity and current personality profile.

### update_personality_profile(...)

Updates descriptive personality information only through an explicit,
validated operation.

### record_experience(...)

Records an experience with observation, interpretation, session, and
source provenance kept separate.

### record_relationship(...)

Creates or updates a relationship belonging to the existing identity.

### record_social_memory(...)

Records a subject-specific memory with category, provenance, and certainty.

### correct_social_memory(...)

Corrects a memory while preserving appropriate revision history.

### forget_subject(identity_id, subject_id)

Deletes or invalidates dependent subject information and invalidates
pending personality proposals that rely on deleted evidence.

### propose_personality_revision(...)

Creates a pending proposal with relational evidence references.

### accept_personality_revision(...)

Rechecks evidence validity, source independence, current personality
state, and change limits inside a transaction before applying a change.

### reject_personality_revision(...)

Rejects a pending proposal without changing personality.

## EvidenceEvaluator

Evaluates claims without modifying storage or personality.

It must distinguish:

- Different sessions.
- Different source records.
- Repeated or correlated sources.
- Supporting evidence.
- Refuting evidence.
- Uncertain evidence.
- Internally conflicted evidence.

It must not claim independence merely because session IDs differ.

## PersonalityExpression

A pure computation with no database writes.

### compose_expression(personality, relationship_memories, situation, objective)

Returns one context-aware expression of the same identity.

It must not:

- Create a new personality.
- Change personality traits.
- Create or modify memories.
- Grant permissions.
- Change governance decisions.
- Invent relationship history.
- Treat uncertain memories as established facts.

## Security boundary

HAIE cannot modify HIVE governance, authorization, owner controls, or
security policies.

No HAIE output grants technical authority or permissions.
