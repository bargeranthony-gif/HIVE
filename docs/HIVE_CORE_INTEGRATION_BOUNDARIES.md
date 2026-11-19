# HIVE Core Classification and Integration Boundaries

**Status:** Architecture decision for staged implementation  
**Companion specification:** [HIVE Core Architecture Specification](HIVE_CORE_ARCHITECTURE_SPEC.md)  
**Purpose:** Define what must be universal HIVE Core infrastructure and what remains a replaceable capability, connector, or specialist subsystem.

## 1. Governing rule

HIVE Core is the stable authority and coordination layer shared by every authorized interface, node, connector, model, agent, and domain extension. Core owns identity, permissions, shared contracts, state, provenance, audit, and orchestration.

Core does **not** absorb every feature's internal business logic. A capability belongs in Core only when every HIVE installation or extension needs that responsibility to participate safely and consistently. Domain-specific algorithms and provider-specific behavior remain replaceable extensions.

The implementation should remain modular and local-first. Logical Core responsibilities do not require separate microservices or distributed infrastructure until scale, reliability, or security evidence justifies that deployment.

## 2. What belongs in HIVE Core

| Core responsibility | Required shared behavior |
|---|---|
| Identity and trust | Stable identities for owner, HIVE installation, node, user, interface, agent, connector, service, and federated participant. |
| Authorization and governance | One policy decision/enforcement model for read, write, execute, send, delete, share, resource use, spending, and trading actions. Support scoped permissions, standing owner policies, approval gates, expiry, revocation, and local-owner veto. |
| Resource and integration registry | Inventory connectors, filesystems, media libraries, email/calendar providers, devices, model providers, chat interfaces, services, and nodes. Track discovered, installed, authorized, enrolled, connected, degraded, disconnected, unavailable, revoked, and retired states separately. |
| Agent and capability catalog | Register user-attached agents, models, tools, and capabilities. Record provider, version, dependencies, input/output contract, evidence, availability, permission needs, cost, and health. Agents may be specialist or generalist; no fixed mandatory roster. |
| Communication gateway | Versioned, authenticated, auditable request/response and event contracts between interfaces, HIVE Core, agents, nodes, and extensions. Support progress events and result delivery to the initiating interface. |
| Shared context and memory contracts | Permission-filtered retrieval and contribution across authorized interfaces. Separate private, shared, operational, task, research, and personality/social-memory records. Preserve source references, classification, retention, correction, deletion, and revocation behavior. |
| Activity and audit ledger | Record authorization decisions, resource access, conversation-derived events, task state changes, agent actions, external side effects, approvals, results, failures, and financial actions with actor, timestamp, correlation ID, policy version, and provenance. Critical audit records must be append-only or tamper-evident. |
| Task and orchestration contracts | Durable task envelopes, dependencies, capability matching, assignment, lifecycle state, progress, cancellation, retries, result collection, verification, and owner reporting. |
| Evidence and provenance contract | Common evidence identity and lineage: source/owner, URI or local reference, content hash or revision where applicable, collection time, environment/version, classification, evidence type, status/freshness, confidence, and invalidation reason. Preserve the difference between a claim, static observation, test receipt, benchmark, and independent corroboration. |
| Resource and budget enforcement | Generic quotas, leases, cost ceilings, spending limits, time windows, risk boundaries, and approval thresholds applied consistently to agents and nodes. Domain extensions may define more specific financial or operational rules. |
| Runtime lifecycle and operations | Health, structured diagnostics, safe read-only inspection, backups, migration discipline, update/recovery controls, compatibility negotiation, and graceful offline/reconnect behavior. |

Core must enforce permissions at every boundary: initial request, retrieval, context assembly, agent handoff, task execution, external service call, result storage, sharing, and response delivery. A successful connection, installed application, registered capability, or agent claim is not itself permission.

## 3. Interface-to-HIVE operating model

ChatGPT, Claude, Grok, a local model interface, a HIVE-native UI, voice, CLI, or another compatible client is an interchangeable **interface adapter**. An interface is not the owner of HIVE's authoritative memory, policy, or task state.

The intended flow is:

1. The user submits an objective through an authorized interface.
2. The interface adapter forwards the request, actor identity, conversation context that is actually available, and correlation metadata to HIVE.
3. HIVE resolves permissions and relevant shared context, decomposes the objective, and creates or updates durable tasks.
4. HIVE selects from the agents, models, tools, nodes, and services the owner has attached and authorized. Agents may be specialist or generalist, may use different models, and may be written in different languages.
5. HIVE dispatches bounded work, monitors progress, reconciles results, and records provenance and activity.
6. HIVE returns the consolidated result and relevant progress to the initiating interface. The interface remains in the loop to explain, challenge, synthesize, or contribute its own authorized work.
7. The same permission-filtered state is available to other authorized HIVE interfaces, without granting them broader access than their identity and policy permit.

A user may ask an interface to review all accessible messages, extract requests and commitments, create prioritized source-linked tasks, and route those tasks to suitable agents. The task records should retain source-message references, ambiguity/confidence, deadline, dependencies, owner, required capabilities, approval state, and outcome.

**Access limitation:** HIVE cannot infer or obtain private conversations from an installed ChatGPT, Claude, Grok, Messenger, Signal, or other application unless a legitimate supported connector, explicit import/export, or other owner-authorized access path exposes them. Provider-specific access remains an adapter responsibility. Never bypass application sandboxes, encryption, access controls, or service rules.

## 4. Agent model: user-configurable, not hard-coded

The owner chooses which agents, models, tools, and services attach to an installation and what each may access or do.

- An agent can specialize in one duty or cover several domains.
- A generalist agent is valid; separate legal, accounting, engineering, research, coding, or other agents are optional choices.
- Agents are replaceable and can run locally, remotely, or through external providers.
- A claimed role or skill is not proof of competence, professional licensure, or actual capability. Capability declarations must be supported by evidence appropriate to the task.
- HIVE owns assignment, authorization, task state, audit, and result reconciliation. Agents do not own global HIVE policy or shared authoritative state.
- Agents cannot expand their own permissions, approve their own privileged actions, or bypass the HIVE policy enforcement boundary.

The minimum Core contract is an agent identity, capability manifest, permission context, versioned task/result envelope, health/availability status, and auditable execution record—not a built-in collection of named profession agents.

## 5. Core versus extension classification

| Capability or workstream | Classification | Boundary |
|---|---|---|
| Node/resource registry and lifecycle | **Core** | Common identity, status, provenance, capability and permission contracts are universal. |
| Connector framework and authorization | **Core** | Provider adapters are extensions; Core controls scopes, credentials, audit, revocation, and shared-context access. |
| Chat/model/interface adapters | **Extensions** | ChatGPT, Claude, Grok, local model, and HIVE UI adapters connect through the Core gateway. |
| Task extraction, assignment, orchestration, and shared status | **Core** | Domain-specific agents perform assigned work; Core maintains task authority and lifecycle. |
| Generic evidence/provenance and verification records | **Core** | Repository analyzer, legal evidence research, finance evidence analysis, and HAIE evaluation are consumers/specialists. |
| Files, Photos, videos, email, calendars, contacts, Dropbox, Messenger, Signal, and other service connectors | **Extensions** | Core provides the resource, scope, ingestion, provenance, and context contracts. Each provider adapter uses supported authorized access. |
| Vision, OCR, media classification, and document-specific analysis | **Extensions** | Shared ingestion, access control, indexing contracts, and provenance are Core responsibilities. |
| Adaptive personality and social-memory engine (HAIE) | **Isolated subsystem / optional extension** | It may use Core memory, evidence, identity, and approval interfaces. Its personality algorithms and relationship-specific model do not become mandatory Core logic and can never govern permissions. |
| Repository/source inspector and evidence-layer analyzer | **Specialist developer capability** | It consumes Core evidence/provenance contracts; it must not execute untrusted source code merely to inspect it. |
| Legal, accounting, engineering, research, coding, and other specialist agents | **User-selected agents/extensions** | Core supplies task, capability, evidence, and authorization contracts. Agents provide domain reasoning and deliverables. |
| Treasury and financial operations | **Domain extension on Core governance** | Core enforces identity, action scopes, budget limits, approval, audit, and revocation. Banking/brokerage adapters, bookkeeping, financial analysis, and investment/trading logic remain separate modules. |
| Autonomous revenue engine / remote technical services | **Business extension** | Core supplies agent orchestration, task state, approvals, audit, and permitted payment boundaries. Marketplace discovery, proposals, delivery workflows, client management, and service-specific QA remain extension logic. |
| Financial intelligence/BROXSON research, backtesting, and investment strategies | **Domain extension** | Not a mandatory Core dependency. No strategy or projected return is assumed to be reliable operating income. |
| Browser automation, Autonomous Environment Learning, Autonomous Engineering, CAD, robotics, wireless/energy systems | **Optional capabilities/extensions** | They use Core identity, capability, execution, evidence, and policy contracts. They do not become mandatory runtime dependencies. |

## 6. Adaptive Identity (HAIE) promotion boundary

HAIE is valuable because it explores persistent identity, social memory, evidence-backed personality revisions, and owner-reviewed adaptation. It is not the same thing as HIVE's generic identity/authentication service or the repository source-evidence analyzer.

Current promotion decision:

- Keep HAIE under the isolated `.emulation/prototypes/adaptive_identity/v04` boundary while it remains experimental.
- Phase 4 implements evidence-backed personality revision proposals, relational evidence links, source-independence checks, proposal invalidation, transactional acceptance/rejection, and schema migration tests.
- The latest local combined regression reported by the owner is **339 passed** using `pytest -q tests .emulation/tests`; the HAIE v0.4 subset reported **119 passed**. These are local test receipts for the reviewed working state, not proof of production deployment or hosted CI for the Phase 4 branch.
- The acceptance method explicitly does not authenticate the owner. HIVE's Core authorization layer must authenticate/authorize the actor before invoking it.
- HAIE must not modify governance, permissions, safety rules, security boundaries, node ownership, or financial authority.
- Core integration requires a separately reviewed adapter/API contract, privacy and retention review, cross-subsystem tests, and explicit owner approval. Phase 5 unified expression and later privacy/deletion review remain separate work.

The reusable Core contribution is the evidence/provenance and approval contract, not the personality engine itself.

## 7. Treasury, operating continuity, and revenue boundaries

HIVE must support financial continuity, but financial domain logic must not be required for every HIVE installation.

**Core provides:** actor identity, scoped delegated authority, account/resource references, action authorization, generic budgets and limits, approval thresholds, immutable audit events, revocation, and result/reconciliation envelopes.

**Treasury extension provides:** account and brokerage connectors, cash-flow forecasts, reserve policy, operating runway calculations, bookkeeping, payment workflows, investment research, and any broker order-management logic.

**Owner-defined treasury policies must be able to:**
- Protect essential operating reserves before discretionary spending or investment.
- Forecast infrastructure and business operating costs and alert before runway becomes unsafe.
- Restrict authorized accounts, instruments, action types, transaction sizes, exposure, losses, leverage, transfers, withdrawals, time windows, and approval thresholds.
- Allow standing authorization within explicit limits while requiring fresh approval outside those limits.
- Stop or require reapproval when authorization expires, account state changes, limits are reached, or critical data becomes stale.
- Treat speculative trading as risk capital only; never assume investment profits will pay essential bills.

The Autonomous Revenue Engine is a separate business extension. It may find paid technical work, qualify projects, estimate costs, prepare proposals, coordinate agents, quality-check deliverables, and track invoices/payments. Client contracts, pricing, account identity, delivery, confidentiality, platform rules, and legally consequential commitments remain governed by owner policies and approval requirements.

## 8. Cross-platform and language boundaries

The current HIVE Core is Python-centered, with local SQLite persistence and native/runtime integrations such as llama.cpp. Do not rewrite the existing Core solely to claim language universality.

Use language-neutral, versioned contracts so:
- Python can remain the initial coordinating Core.
- Rust or another compiled runtime may later handle resource-sensitive edge/node functions where justified.
- Android can use Kotlin/Java platform services; iOS can use Swift; browser interfaces can use TypeScript.
- External agents and services may use any language if they implement the supported authenticated protocol and capability/task contracts.

Android's Linux kernel lineage does not make an ordinary Android app equivalent to a Linux server process. Mobile adapters must respect OS sandboxing, lifecycle, permission, battery, and background-execution rules.

## 9. Promotion gates

A capability moves toward Core only when all of the following are true:

1. It is a shared cross-domain responsibility, not one agent's business logic.
2. A stable interface and data contract are defined.
3. Identity, authorization, isolation, provenance, audit, failure, and revocation behavior are specified.
4. The change reuses existing modules and migrations where practical and does not create duplicate sources of truth.
5. Unit, integration, regression, and relevant adversarial tests cover the boundary.
6. Its operational cost, platform compatibility, privacy, and recovery behavior are understood.
7. The owner approves promotion into the mandatory Core runtime.

A subsystem can be published in the repository as an isolated prototype without being promoted into Core. Repository presence, passing prototype tests, or an architecture document is not equivalent to production integration.

## 10. Current status snapshot (2026-11-19)

| Area | Current evidence/status |
|---|---|
| Python CLI, SQLite registry, repository/source inspection, graph functions, capability records | Existing repository implementation; verify each feature against exact tests and version before claiming broader production readiness. |
| Read-only CLI diagnostics and llama.cpp model-alias compatibility | Merged to `main` in PR #9; exact-head GitHub Actions Python 3.10/3.11/3.12 matrix passed. |
| Repository security policy, Dependabot configuration, CodeQL workflow | Merged to `main` in PR #8; exact-head CodeQL run passed. Repository-level security settings still require separate owner configuration. |
| HIVE Core architecture and staged Edge Runtime / Intelligence Plane roadmap | Architecture documentation proposal; not runtime implementation. |
| HAIE Phase 4 personality-revision prototype | Merged to `main` in PR #13 under `.emulation/prototypes/adaptive_identity/v04`; isolated, not integrated into Core. Owner-reported local tests: 119 HAIE v0.4 / 339 combined; hosted combined regression and CodeQL passed on Python 3.10–3.12. |
| Cross-interface shared resource/conversation context and task extraction | Planned in Issue #10; not implemented as a complete feature. |
| Node registry, cross-platform Edge Runtime, authenticated multi-node coordination | Planned architecture; not a complete implemented runtime. |
| Treasury, brokerage trading, autonomous revenue engine | Planned domain extensions; not implemented. |
| Repository evidence-layer analyzer in Issue #2 | Review-only comparison request; do not duplicate existing inspector or confuse it with HAIE personality evidence. |

Update this snapshot when exact code, tests, or CI receipts change. Never convert a plan, prototype, user-reported test, or provider listing into a production claim.

## 11. Immediate sequencing

1. Merge the independently reviewed read-only CLI and repository security foundations (PRs #9 and #8).
2. Adopt HCAS and this integration-boundary document as the architecture baseline.
3. Complete the 0.2 repository reconciliation: map modules, tables, migrations, interfaces, tests, PRs, and prototype boundaries.
4. Define canonical Core schemas for principal/authorization context, resource/connector, node lifecycle, capability/evidence, event/activity, conversation context, task, agent, and result.
5. Build the minimal local permission/registry/event/task contracts before adding broad connectors or distributed services.
6. Start the resource layer with read-only filesystem and Photos/media metadata/ingestion, then supported conversation and cloud connectors.
7. Add task extraction, agent assignment, and cross-interface status on top of the shared permission and provenance layer.
8. Mature HAIE, Treasury, Revenue Engine, AEL, Autonomous Engineering, and other domains behind their extension boundaries and promotion gates.

No Phase 4 prototype, finance integration, autonomous trading, or external-service access is promoted to production by adopting this document.
