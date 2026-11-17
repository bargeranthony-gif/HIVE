# HAIE v0.1 — HIVE Adaptive Identity Engine

Status: Experimental prototype. Not integrated into HIVE Core.

## Purpose

Provide isolated, persistent storage for:
- A stable foundational identity.
- Curated interaction experiences.
- Social contact context.
- Proposed adaptive personality changes.

## Design boundaries

- Uses its own SQLite database.
- Does not access or modify the HIVE production database.
- Does not execute actions or interact with games.
- Does not modify governance, authorization, or security policies.
- Does not automatically learn from raw conversations.
- Personality revisions require at least three distinct stored experiences.
- Each accepted revision is limited to a maximum 0.10 change per trait.
- Revisions require explicit acceptance.
- Social memory can be removed using `forget_subject`.

## Current trait model

Traits are experimental numeric values from 0.0 to 1.0:
- sociability
- humor
- competitiveness
- formality
- patience
- playfulness

These are behavioral tendencies, not measures of intelligence or moral worth.

## Database

The prototype database should be created under this workspace, for example:

`.emulation/prototypes/adaptive_identity/identity.sqlite3`

Do not point this prototype at `hive.db`.
