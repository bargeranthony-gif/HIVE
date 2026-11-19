# HAIE v0.4 — Architecture Decisions

## Decision 1: One persistent personality

Accepted.

HIVE has one continuous identity. There are no separate friend, business,
gaming, or engineering personalities.

## Decision 2: Internal separation is organizational

Accepted.

Personality, social memory, and situational awareness remain distinct
internal data structures because they represent different kinds of
information. They cooperate to express one identity.

They must not become independent identity or personality systems.

## Decision 3: Context affects expression

Accepted.

Context can influence communication style, humor, detail, pacing, and
behavior. Context alone cannot permanently change personality.

## Decision 4: Relationships inform expression

Accepted.

Relationship memory can influence familiarity, references, communication
preferences, and boundaries. It does not grant permissions or authority.

## Decision 5: Personality evolves through reviewed experience

Accepted.

Evidence can support proposed personality changes. Changes require
evaluation and explicit owner approval.

## Decision 6: Governance remains independent

Accepted.

HAIE cannot modify HIVE authorization, governance, security boundaries,
or owner controls.

## Decision 7: Prototype isolation

Accepted.

v0.4 begins as a design specification. Implementation must remain isolated
until the design and test plan are reviewed.

## Decision 8: Owner authorization is enforced outside HAIE

Accepted.

HAIE can validate a personality revision proposal, revalidate its
supporting evidence, and record an acceptance or rejection decision.

The HAIE acceptance method does not authenticate the owner. HIVE's
control layer must authenticate and authorize the owner before invoking
that method.

HAIE cannot grant itself authorization or modify HIVE governance,
security boundaries, or owner controls.

## Decision 9: Unified expression is a pure computation

Accepted.

The canonical expression API is:

`compose_expression(personality, relationship_memories, situation, objective)`

The composer produces one context-aware expression of the same
persistent identity.

It does not create or modify persistent personalities or memories,
change governance, grant permissions, or invent relationship history.

Situational context and relationship memories influence expression;
they do not create separate identities or personalities.

## Decision 10: Prototype isolation remains in force

Accepted.

Completion of an HAIE development phase does not authorize production
integration.

HIVE Core integration requires separate explicit owner approval.
