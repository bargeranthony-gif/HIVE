# HAIE v0.4 — Data Model

## 1. Identity

The identities table represents one continuous HIVE identity.

Existing identity IDs remain the primary identity references.

Personality, relationships, experiences, and expression all belong to
this identity. Situations and relationships never create new identities.

## 2. Personality profile

The personality profile represents the continuing character.

It contains:

- Stable foundational characteristics.
- Adaptive personality traits.
- Descriptive personality attributes.
- Communication tendencies.
- Interests and preferences.
- Revision history.

Numerical traits remain useful, but they are not the complete personality.

The profile must not contain person-specific preferences that belong in
relationship memory.

## 3. Experiences

Experiences represent meaningful events or interactions.

Each experience should preserve:

- Identity ID.
- Optional subject ID.
- Interaction type.
- Direct observation.
- Interpretation, if any.
- Outcome, if known.
- Session ID.
- Source type and source reference.
- Source correlation group.
- Timestamp and significance.

Observation and interpretation must remain distinct.

## 4. Evidence sources

Evidence provenance must distinguish an observation's source from the
number of sessions in which it appears.

A source correlation group identifies evidence that originates from the
same underlying source or repeated information chain.

Independent-session counts alone must not establish source independence.

Confidence is descriptive unless separately calibrated and validated.

## 5. Relationships

A relationship belongs to one HIVE identity and one subject.

It contains:

- Subject ID.
- Optional display name.
- Relationship history.
- Relevant familiarity information.
- Creation and update timestamps.

Do not use relationship familiarity as an authorization or permission signal.

Do not assume a numerical trust score accurately represents a relationship.

## 6. Social memories

Social memories are individually addressable records.

Memory categories may include:

- Explicit preference.
- Communication preference.
- Boundary.
- Shared experience.
- Recurring conversational reference.
- Relevant relationship fact.
- Owner correction.

Each memory should track:

- Subject and identity.
- Memory category.
- Content.
- Source experience, when applicable.
- Provenance.
- Confidence or certainty classification.
- Created and updated timestamps.
- Active, corrected, or invalidated state.

An explicitly stated preference must be distinguishable from an inferred
preference.

A memory about one person must not automatically become a global
personality trait.

## 7. Situational context

Situational context is initially transient.

It may contain:

- Activity.
- Environment.
- Current objective.
- People present.
- Interaction constraints.
- Relevant temporary conditions.

It does not create a new personality and does not automatically modify
persistent memory.

## 8. Unified expression

Expression is a computed result, not a separate identity.

Inputs:

- Current personality profile.
- Relevant relationship memories.
- Current situation.
- Interaction objective and constraints.

Output:

- Communication style guidance.
- Relevant familiarity level.
- Appropriate humor and conversational tendencies.
- Contextual behavior guidance.
- Memory references used.
- Uncertainty or conflict indicators.

Expression must not write to personality or memory as a side effect.

## 9. Personality proposals

A personality proposal must:

- Identify the proposed trait or characteristic change.
- Explain the rationale.
- Reference supporting evidence.
- Identify contradictory evidence.
- Include source-independence assessment.
- Preserve the previous personality state.
- Require explicit owner approval.

Evidence references must be relational records, not JSON-only references.

## 10. Deletion and correction

Forgetting a subject must remove or invalidate all dependent social memories,
experiences, and claims.

Pending personality proposals that depend on deleted evidence must become
invalidated and must not be accepted.

Accepted personality revisions require special treatment: deleting social
memories must not silently rewrite historical personality state. Any
reassessment or reversal must be a separate owner-reviewed operation.

## 11. Database isolation

v0.4 uses a new isolated database and schema.

Do not migrate or modify v0.3.1's database.

Do not modify HIVE Core.
