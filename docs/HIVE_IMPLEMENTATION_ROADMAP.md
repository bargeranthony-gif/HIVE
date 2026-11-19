# HIVE Implementation Roadmap and Repository Reconciliation

**Status:** Architecture and integration-boundary proposal for review; not an implementation claim  
**Architecture baseline:** HIVE Core Architecture Specification (HCAS) and HIVE Core Integration Boundaries  
**Planning branch:** `docs/hive-edge-brain-roadmap`  
**Prepared:** 2026-11-19

## 1. Objective

Translate the approved HIVE direction into an incremental implementation plan while preserving existing repository work and the user's separate local development.

The target is one coordinated HIVE intelligence platform spanning many owner-controlled computers, devices, services, interfaces, agents, and capabilities. Each installation retains local authority. A lightweight portable edge runtime participates in a logical HIVE Intelligence Plane ("home brain"), which may be local, remote, or hybrid.

This document describes intended architecture and sequencing. It does not claim planned components are implemented.

## 2. Architecture decisions

1. **Small portable Core:** identity, trust, policy enforcement, communication, resource/capability discovery, event/activity state, authorized task exchange, and reliable reporting.
2. **Chosen interface, shared HIVE authority:** ChatGPT, Claude, Grok, local models, HIVE UI, voice, CLI, and other clients are adapters. HIVE owns authoritative permissions, shared context, activity, task state, and orchestration.
3. **User-configurable agents:** the owner may attach specialist or generalist agents, models, tools, and services. Core manages identity, capability manifests, permissions, task assignment, result collection, and audit; it does not hard-code a mandatory profession roster.
4. **Edge / Intelligence Plane separation:** constrained phones and devices can run a thin Edge Runtime; heavier reasoning and compute can run on authorized hosts.
5. **Local authority:** remote orchestration cannot override a node owner's local denial, resource limit, or revocation.
6. **Capability-based scheduling:** allocate tasks using verified capability, compatibility, availability, latency, data locality, cost, and policy—not fixed machine roles.
7. **Adapters, not monoliths:** operating-system, device, application, model, messaging, data-source, and domain integrations attach through versioned contracts.
8. **Evidence and provenance:** distinguish claims, observations, test receipts, benchmarks, independent corroboration, stale evidence, and contradictions. Preserve source identity, revision, environment, and time.
9. **Financial governance in Core, finance logic in an extension:** Core supplies identity, authorization, generic budgets/limits, approval, audit, and revocation. Treasury, bank/broker adapters, accounting, investment research, and trading logic remain optional domain extensions.
10. **Revenue services as an extension:** Core supplies task/agent orchestration and authorization. Paid-service discovery, proposals, client work, quality checks, invoicing, and collections are business-domain workflows.
11. **Adaptive personality is not authorization:** HAIE may use Core identity, memory, evidence, and approval contracts, but its personality logic remains optional and cannot change governance or owner control.
12. **No premature distribution:** begin with clear modular contracts and a local implementation. Split services only when scale, reliability, or security evidence justifies it.

## 3. Deployment model

### HIVE Edge Runtime

Required on a participating endpoint:
- Installation/node identity and enrollment lifecycle.
- Authenticated, versioned communication.
- Local policy and permission enforcement.
- Local inventory and adapter registration.
- Authorized local task execution.
- Health, result, and lifecycle reporting.
- Safe offline behavior and recovery.

Not mandatory on every endpoint:
- Large language models.
- Research and long-term knowledge services.
- Specialist agents.
- CAD, simulation, robotics, or engineering packages.
- Autonomous learning or engineering engines.

### HIVE Intelligence Plane ("home brain")

May host:
- Reasoning, planning, task decomposition, and orchestration.
- AI model routing and specialist/generalist agent coordination.
- Knowledge, research, provenance, and experience evaluation.
- Capability-aware scheduling and resource allocation.
- Cross-node coordination, monitoring, and recovery.
- Optional business, financial, media, learning, and engineering extensions.

The scheduler must never equate resource visibility or idle capacity with permission to use it.

## 4. Proposed development stages

The stage labels are maturity gates, not automatic software version numbers. Current package metadata reports version 0.1.0; the stage of each capability must be assessed from code and tests.

| Stage | Focus | Exit criteria |
|---|---|---|
| 0.1 | Existing local foundation | Current modules, persistence, CLI, discovery, capability evidence, graph, planning, and governance inventory documented with actual status |
| 0.2 | Reconciled Core contracts | Module/database/test map; canonical identity, authorization, connector/resource, event/activity, capability/evidence, conversation, task, agent, result, and extension contracts agreed |
| 0.3 | Edge Runtime prototype | Minimal portable process, node identity, enrollment states, adapter contract, local authorization, health reporting |
| 0.4 | Infrastructure awareness | Host inventory, node registry, hardware/software/resources, provenance, status history, capability evidence freshness |
| 0.5 | Secure communication | Authenticated/versioned messaging, request/task/result envelopes, revocation, reconnect and offline semantics |
| 0.6 | Coordinated execution | Capability-aware scheduler, quotas/leases, durable tasks, idempotency, verification, failure recovery |
| 0.7 | Extension ecosystem | Versioned adapters, optional services, user-selected agents, model providers, extension lifecycle and compatibility |
| 0.8 | Operational hardening | Security review, compatibility matrix, observability, backup/restore, adversarial tests, installation and upgrade paths |
| 1.0 | Stable foundational platform | Stable contracts, tested local and multi-node behavior, owner controls, safe upgrades, recovery, documentation |
| 1.1+ | Capability growth | Backward-compatible improvements; Treasury, Revenue Engine, HAIE, AEL, Autonomous Engineering, and other optional capabilities mature behind their own gates |

A stage is complete only when acceptance criteria are demonstrated by tests, reviewable evidence, and documentation. A roadmap entry, architecture document, mock, or prototype is not production implementation.

## 5. Implementation sequence

### Workstream A — Repository reconciliation

- Map every existing Python module, database table, CLI command, public interface, and test to HCAS.
- Record each item as implemented, partial, prototype, planned, or unknown.
- Review active pull requests and branch differences before changing overlapping files.
- Identify migrations and compatibility constraints.
- Correct outdated README and implementation-status claims.
- Produce a module-level gap matrix and architecture decision log.

### Workstream B — Core contracts

- Define canonical principals and stable installation, owner, node, interface, service, agent, connector, resource, and extension identifiers.
- Define versioned authorization context, event/activity, resource/connector, capability/evidence, conversation/context, task, agent, and result schemas.
- Define lifecycle states, approval requirements, policy evaluation, audit, revocation, retention, and data-sharing semantics.
- Define adapter and extension contracts.
- Reuse existing SQLite data and migration history; do not create duplicate sources of truth.

### Workstream C — Edge Runtime

- Separate mandatory runtime responsibilities from optional services.
- Establish minimal dependencies and supported platform strategy.
- Implement enrollment, local policy enforcement, secure messaging, health, and task reporting.
- Prove the runtime can operate without a local AI model.
- Use native platform adapters where required: Android/Kotlin, iOS/Swift, browser/TypeScript, and optional compiled node components where justified. Keep the existing Python Core; do not rewrite it solely to pursue language uniformity.

### Workstream D — Infrastructure, resource registry, and capability catalog

- Discover/register hardware, operating systems, drivers, software, connectivity, files/media providers, and resources.
- Track owner, provenance, status, health, permissions, scopes, synchronization, and verification time.
- Distinguish discovered, installed, enrolled, verified, authorized, connected, available, degraded, offline, quarantined, revoked, and retired.
- Derive capabilities from evidence and dependencies.
- Start with read-only filesystem and Photos/media metadata/ingestion, then add supported email/cloud/document/device connectors.

### Workstream E — Shared context, activity, and task orchestration

- Ingest only authorized conversations and resources.
- Build permission-filtered shared context and source-linked activity history.
- Extract requests, commitments, decisions, deadlines, and follow-ups into proposed tasks.
- Assign work to owner-selected agents by verified capability, permissions, availability, cost, and compatibility.
- Track dependencies, approvals, progress, results, validation, and completion across authorized interfaces.
- Keep the initiating conversational interface in the loop with progress and consolidated results.
- Enforce per-owner, per-node, per-user, per-interface, per-agent, per-resource, and per-conversation scopes.

### Workstream F — Intelligence Plane and distributed coordination

- Host reasoning and models independently of edge endpoints.
- Add authenticated node messaging and task dispatch.
- Schedule by capability, policy, resource limits, compatibility, locality, cost, and availability.
- Implement leases, quotas, cancellation, idempotency, durable state, recovery, and result verification.
- Support single-machine deployment first, then multi-node and federated topologies.

### Workstream G — Optional domain extensions

- Mature HAIE adaptive personality/social memory as an isolated subsystem using Core identity, provenance, memory, and approval contracts.
- Add Treasury/banking/brokerage and financial analysis through a domain extension with protected operating reserves, scoped account permissions, trade limits, approvals, reconciliation, and audit.
- Add the Autonomous Revenue Engine as a business extension for paid technical work, proposals, agent execution, QA, delivery, invoicing, and collections.
- Add legal, accounting, engineering, research, coding, media, and other agents as user-selected replaceable capabilities.
- Keep BROXSON financial research, AEL, Autonomous Engineering, CAD, robotics, and browser operation optional and separately validated.

## 6. Repository and branch inventory

Snapshot from GitHub on 2026-11-19. The default branch now includes the two reviewed foundational pull requests below.

| Branch / PR | Current status | Disposition |
|---|---|---|
| `main` | Head `3c81421` | Includes PR #8 repository security baseline and PR #9 read-only CLI/installer fixes. |
| PR #8 — Repository security baseline | **Merged** | `SECURITY.md`, Dependabot configuration, and CodeQL workflow. CodeQL exact-head run #2 succeeded. GitHub repository security settings still require separate owner configuration. |
| PR #9 — Read-only CLI diagnostics | **Merged** | SQLite read-only mode, no state/log creation for supported informational commands, installer model alias, documentation and tests. Exact-head GitHub Actions run #19 passed Python 3.10, 3.11, and 3.12. |
| `docs/hive-edge-brain-roadmap` / PR #11 | Open documentation proposal | HCAS, staged roadmap, and this Core integration-boundary classification. No runtime implementation. |
| PR #13 — Isolated HAIE Phase 4 prototype | **Merged** | Squash merge `bd61d9b` publishes Phase 4 under `.emulation/prototypes/adaptive_identity/v04`. It remains isolated and is not mandatory Core logic. Owner-reported local run: 119 HAIE v0.4 tests / 339 combined tests; hosted combined regression and CodeQL passed on Python 3.10–3.12. |
| PR #7 — BROXSON global financial intelligence integration | Open domain proposal | Financial research extension, not a mandatory Core dependency. Preserve its offline/research-only boundaries. |
| PR #3 — Combined offline financial evidence research and S3 bridge | Open review proposal | Separate financial research integration; preserve its review-only and data-access constraints. |
| Issue #2 — HIVE evidence-layer analyzer | Open, review-only | Compare source/test-receipt evidence needs against current inspector and HAIE. Do not duplicate either or import private third-party implementation. |
| Issue #10 — Permission-governed machine resources and shared context | Open implementation backlog | Core resource/connector permissions, authorized conversations, shared activity/context, task extraction, agent routing, and revocation. |

A local test receipt is scoped to the exact working tree and command the owner ran. It is not a hosted CI result or production claim. A proposal branch or issue is not an implementation.

## 7. Immediate next actions

1. Adopt the HCAS and Core integration-boundary documentation as the reviewed architecture baseline.
2. Complete the 0.2 repository module/database/migration/test/PR gap matrix.
3. Record existing read-only diagnostics and repository security baseline as integrated.
4. Keep HAIE Phase 4 isolated; add hosted CI for its exact branch before considering repository merge. Do not integrate the personality engine into the mandatory Core runtime.
5. Define the canonical Core contracts before building broad connectors or multi-node execution.
6. Implement the shared authorization/resource/activity/context/task foundation before provider-specific connectors.
7. Add optional Treasury and Revenue Engine implementations only after Core authorization, audit, task, and budget contracts are available.

## 8. Release and change controls

- Architecture documentation does not prove runtime implementation.
- Do not merge a prototype into production Core merely because its local tests pass.
- Before any implementation milestone is published: inspect the complete diff, run the relevant test scopes, inspect exact CI results, scan for secrets/local artifacts, verify migration safety, and agree the target branch and commit.
- Keep prototypes and experiments isolated until reviewed and promoted through explicit gates.
- Preserve local user data, untracked backups, and existing repository work.
