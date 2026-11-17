# HAIE v0.4 — Evidence and Provenance Design

## 1. Purpose

Provide a structured, read-only evidence system that distinguishes
observations, information sources, and claims.

Evidence evaluation must not directly modify personality, relationships,
social memories, governance, or authorization.

## 2. Evidence records

### Evidence source groups

A source group represents one underlying information origin or a set of
correlated origins.

Fields:
- group_id
- identity_id
- independence_status
- created_at
- updated_at

Allowed independence statuses:
- independent
- correlated
- unverified

Only explicitly classified independent groups qualify toward the
independent-source threshold.

A correlated group represents one shared information origin. Repeated
observations within it must not be counted as independent confirmations.

An unverified group provides provenance context but no independent
evidence credit.

### Evidence sources

A source identifies the origin of an observation.

Fields:
- source_id
- identity_id
- source_type
- source_reference
- optional group_id
- created_at
- updated_at

A source without a verified group cannot qualify toward the
independent-source threshold.

### Experiences

An experience records an interaction or observation.

Fields:
- experience_id
- identity_id
- optional subject_id
- interaction_type
- summary
- observation
- interpretation
- outcome
- session_id
- optional source_id
- observed_at
- confidence
- created_at

Observation and interpretation must remain separate.

A session identifies when an interaction occurred. It does not establish
source independence.

### Claims

A claim represents a proposition associated with an experience.

Fields:
- claim_id
- experience_id
- claim_key
- claim_value
- stance
- context_key
- confidence
- created_at

Allowed stances:
- supports
- refutes
- uncertain

## 3. Independence rules

1. Distinct session IDs do not establish independent sources.
2. Multiple observations in one correlation group count as one origin.
3. Only explicitly independent source groups qualify toward the
   independent-source threshold.
4. Correlated and unverified groups remain visible in assessments but
   receive no independent-source credit.
5. Missing source provenance never implies independence.
6. Confidence is descriptive, not a calibrated probability.
7. Repeated observations must not inflate evidence counts.

## 4. Contradiction handling

The evaluator compares propositions using:
- identity
- subject
- interaction type
- normalized claim key
- normalized context

Different normalized claim values under the same proposition key
represent competing values and must be assessed together.

For example, "preferred beverage = tea" and
"preferred beverage = coffee" are competing propositions.

Evidence from the same source group must not create independent
contradiction counts.

Opposing evidence from distinct groups explicitly classified as
independent produces a contradiction requiring owner review.

Conflicting claims within one source group are reported as a
source-level conflict and do not create independent directional support.

Correlated and unverified sources remain visible but cannot establish
independent contradiction or satisfy the independent-source threshold.

Uncertain evidence remains visible but does not count as directional
support or refutation.

## 5.1 Source classification integrity

An independence classification is an explicit provenance assertion,
not proof that a source is authentic or genuinely independent.

The evaluator reports the stored classification and must not describe
it as independently verified authenticity.

Once a source group is referenced by an evidence source, its
independence classification and identity must not be silently changed.

Any owner-authorized reclassification must preserve an audit record
containing the previous classification, new classification, reason,
and timestamp.

Reclassification must cause subsequent assessments to use the current
classification while preserving the ability to reconstruct the prior
classification history.

## 5. Normalization

Claim keys, values, and contexts are trimmed, whitespace-collapsed,
and case-folded for comparison.

The whitespace normalization must use the correct regular expression:
r"\s+"

Original stored claim text remains unchanged.

## 6. Storage and migration

Schema version 3 adds evidence source groups, evidence sources,
experiences, and claims.

Migration from version 2 must preserve:
- identities
- personality profiles
- relationships
- social memories
- social memory revision history

The migration must be transactional.

The v0.3 and v0.3.1 databases and source files remain unchanged.

## 7. Evaluator contract

The evaluator is read-only.

It returns:
- claim identity and context
- observation count
- distinct session count
- distinct source-group count
- independently verified source-group count
- supporting and refuting independent-source counts
- uncertain evidence count
- correlated and unverified evidence counts
- source-level conflicts
- contradiction status
- review eligibility
- descriptive confidence range

The evaluator must not propose or apply personality changes.

## 8. Required tests

- Version 2 database migrates to version 3 without losing existing data.
- Multiple sessions from one source group count as one origin.
- Repeated observations do not inflate independent-source counts.
- Two explicitly independent groups can satisfy the threshold.
- Correlated groups do not satisfy the threshold.
- Unverified groups do not satisfy the threshold.
- Missing provenance receives no independent credit.
- Contradictory evidence from independent groups requires review.
- Conflicting claims within one group do not create independent
  contradiction counts.
- Uncertain claims remain visible but do not count directionally.
- Normalization handles tabs, newlines, repeated spaces, and case.
- Evaluation does not modify storage or personality.
- Subject and identity boundaries are preserved.

## 9. Isolation

All implementation and tests remain under .emulation/.

No HIVE Core integration or production database changes are permitted
without a separate review and explicit approval.
