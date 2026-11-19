# HIVE Implementation Roadmap and Repository Reconciliation

**Status:** Proposed plan for review; not an implementation claim  
**Architecture baseline:** HIVE Core Architecture Specification (HCAS)  
**Planning branch:** docs/hive-edge-brain-roadmap  
**Prepared:** 2026-11-19

## 1. Objective

Translate the approved HIVE direction into an incremental implementation plan while preserving the existing repository work.

The target is one coordinated HIVE intelligence platform spanning many owner-controlled computers, devices, services, and capabilities. Each installation retains local control. The foundational runtime remains lightweight and portable; heavier reasoning, research, models, and coordination can run on a logical HIVE Intelligence Plane ("home brain") hosted by one or more authorized machines.

This document describes intended architecture and sequencing. It does not claim that planned components are implemented.

## 2. Architecture decisions

1. **Small portable core:** mandatory runtime responsibilities are identity, secure participation, local policy enforcement, communication, capability discovery, authorized task exchange, and reporting.
2. **Edge / Intelligence Plane separation:** phones and constrained devices can run a thin Edge Runtime; complex reasoning and compute can run on a home brain or distributed authorized nodes.
3. **Logical home brain:** the Intelligence Plane is a logical role and need not be one physical server. It may be local, remote, or hybrid.
4. **Local authority:** remote orchestration cannot override a node owner's local denial, resource limit, or revocation.
5. **Capability-based scheduling:** allocate tasks using verified capability, compatibility, availability, latency, data locality, cost, and policy—not fixed machine roles.
6. **Adapters, not monoliths:** operating-system, device, application, and domain integrations attach through versioned contracts.
7. **Learning is an extension:** Autonomous Environment Learning (AEL) is application-independent. It can learn desktop software, CAD, browsers, games, and other authorized interactive environments through observation, demonstration, controlled experiments, and verification.
8. **Engineering is a later extension:** Autonomous Engineering can research, design, simulate, test, and propose software/hardware improvements. Production changes, procurement, fabrication, and changes to security/governance require the appropriate owner authorization.
9. **Evidence and provenance:** distinguish observed, inferred, experimentally verified, stale/contextual, and benchmarked knowledge. Preserve environment/version and source context.
10. **No premature distribution:** begin with clear modular contracts and a local implementation. Split services or add distributed infrastructure only when requirements justify the complexity.

## 3. Deployment model

### HIVE Edge Runtime

Required on a participating endpoint:
- Installation/node identity and enrollment.
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
- AI model routing and specialist agents.
- Knowledge, research, provenance, and experience evaluation.
- Capability-aware scheduling and resource allocation.
- Cross-node coordination, monitoring, and recovery.
- Optional AEL and Autonomous Engineering services.

The scheduler must never equate resource visibility or idle capacity with permission to use it.

## 4. Proposed development stages

The stage labels are maturity gates, not automatic software version numbers. Current package metadata reports version 0.1.0; the stage of each capability must be assessed from code and tests.

| Stage | Focus | Exit criteria |
|---|---|---|
| 0.1 | Existing local foundation | Current modules, persistence, CLI, discovery, capability evidence, graph, planning, and governance inventory documented with implementation status |
| 0.2 | Architecture and core contracts | Module/database/test map; canonical identity, event, capability, task, result, and extension contracts agreed; duplicate abstractions identified |
| 0.3 | Edge Runtime prototype | Minimal portable process, node identity, enrollment states, adapter contract, local authorization, health reporting |
| 0.4 | Infrastructure awareness | Host inventory, node registry, hardware/software/resources, provenance, status history, capability evidence freshness |
| 0.5 | Secure communication | Authenticated/versioned messaging, task/result envelopes, revocation, reconnect and offline semantics |
| 0.6 | Multi-node coordination | Capability-aware scheduler, quotas/leases, durable tasks, idempotency, verification, failure recovery |
| 0.7 | Extension ecosystem | Versioned adapters, optional services, agents, model providers, extension lifecycle and compatibility |
| 0.8 | Operational hardening | Security review, compatibility matrix, observability, backup/restore, adversarial tests, installation and upgrade paths |
| 1.0 | Stable foundational platform | Stable contracts, tested local and multi-node behavior, owner controls, safe upgrades, recovery, documentation |
| 1.1+ | Capability growth | Backward-compatible improvements; AEL and Autonomous Engineering mature as separately versioned optional capabilities |

A stage is complete only when its acceptance criteria are demonstrated by tests, reviewable evidence, and documentation. A roadmap entry, specification, mock, or prototype is not production implementation.

## 5. Implementation sequence

### Workstream A — Repository reconciliation (next)
- Map every existing Python module, database table, CLI command, public interface, and test to HCAS.
- Record each item as implemented, partial, prototype, planned, or unknown.
- Review active pull requests and branch differences before changing overlapping files.
- Identify migrations and compatibility constraints.
- Correct outdated README claims.
- Produce a module-level gap matrix and a short architecture decision log.

### Workstream B — Core contracts
- Define stable installation, owner, node, service, agent, and extension identifiers.
- Define versioned event, capability manifest, task, authorization context, and result schemas.
- Define lifecycle states and state transitions.
- Define adapter and extension contracts.
- Keep existing SQLite data and migration history intact.

### Workstream C — Edge Runtime
- Separate mandatory runtime responsibilities from optional services.
- Establish minimal dependencies and supported platform strategy.
- Implement enrollment, local policy enforcement, secure messaging, health, and task reporting.
- Prove the runtime can operate without a local AI model.

### Workstream D — Infrastructure registry and capability catalog
- Discover/register hardware, operating systems, drivers, software, connectivity, and resources.
- Track ownership, provenance, status, health, permissions, and verification time.
- Distinguish discovered, enrolled, verified, authorized, available, degraded, offline, quarantined, revoked, and retired.
- Derive capabilities from evidence and dependencies.

### Workstream E — Intelligence Plane and coordination
- Host reasoning and models independently of edge endpoints.
- Add authenticated node messaging and task dispatch.
- Schedule by capability, policy, resources, compatibility, locality, cost, and availability.
- Implement leases, quotas, cancellation, idempotency, durable state, recovery, and result verification.
- Support a single-machine deployment first, then multi-node and federated topologies.

### Workstream F — General computer operation and AEL
- Add authorized screen observation and semantic UI/accessibility support where available.
- Capture human demonstrations and correlate input/action/outcome.
- Support mouse, keyboard, touch, and other supported input channels.
- Learn procedures from documentation and controlled experiments.
- Store environment/version-specific evidence and uncertainty.
- Request human assistance when stuck or outside authorization.

### Workstream G — Autonomous Engineering
- Add research, requirements analysis, CAD/electronics/mechanical/software design, simulation, and validation capabilities.
- Require measurable acceptance criteria and independent test evidence.
- Keep experiments isolated from production.
- Require owner approval for procurement, fabrication, deployment, and changes to governance/security boundaries.

## 6. Repository branch inventory

Snapshot from GitHub on 2026-11-19. Branch comparisons are against main. This is a navigation and review inventory, not an instruction to merge branches.

| Branch | Relationship to main | Observed purpose / disposition |
|---|---|---|
| main | Baseline | Current default branch |
| feature/core-architecture-spec | 1 commit ahead | Contains HCAS architecture specification; used as the base for this planning branch |
| docs/hive-edge-brain-roadmap | New planning branch | Adds Edge Runtime / Intelligence Plane, AEL, Autonomous Engineering, stage plan, and branch audit |
| feature/repository-security-baseline | 3 commits ahead | Security policy, Dependabot, CodeQL; associated with PR #8 |
| fix/cli-readonly-diagnostics | 24 commits ahead | Read-only CLI diagnostics, installer fixes, tests, CI; associated with PR #9; PR body says tests were added but had not yet been run |
| bargeranthony-gif-patch-1 | 1 commit ahead | Adds SECURITY.md; overlaps the broader security-baseline branch and should be compared before adoption |
| feature/knowledge-graph | 14 commits behind, no unique diff against current main | Historical/stale branch; inspect history only if needed, do not merge blindly |
| feature/source-inspection | 19 commits behind, no unique diff against current main | Historical/stale branch; inspect history only if needed, do not merge blindly |

### Open pull requests observed

- **PR #9 — Make informational CLI diagnostics strictly read-only:** review implementation and run its exact-head tests before merge.
- **PR #8 — Add repository security baseline:** review security policy and CI results before merge.
- **PR #7 — BROXSON global financial intelligence integration:** separate domain extension; do not fold into the core-runtime architecture work without a deliberate dependency and scope review.
- **PR #3 — Review: combined offline financial evidence research and S3 bridge:** separate review-only financial research integration; preserve its stated draft/review boundaries.

Do not merge or close unrelated pull requests as part of this architecture documentation change. Resolve branch overlap and PR ordering in a separate review.

## 7. Immediate next actions

1. Review and accept/revise this architecture addendum and staged roadmap.
2. Complete the repository module/database/test/PR gap matrix.
3. Reconcile the README and current implementation status.
4. Decide whether the HCAS specification branch should be merged into main.
5. Review PR #8 and PR #9 independently, including exact-head CI and local test evidence.
6. Agree the 0.2 contract milestone before implementation begins.

## 8. Release and change controls

- Do not merge this planning pull request automatically.
- Do not merge unrelated branches as part of the roadmap work.
- Before any implementation milestone is published: inspect the complete diff, run tests, review test results, scan for secrets/local artifacts, verify migration safety, and agree the target branch and commit.
- Keep prototypes and experiments isolated until reviewed and promoted.
- Preserve local user data and existing repository work.
