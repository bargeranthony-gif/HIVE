# HIVE S2 - Point-in-Time Evidence & Relationship Intelligence (Fictional Review)

**Status: additive review code; opt-in, no merge or deployment.**

Repository: `LogiKeyEnterprises/GLOBAL-FINANCE-BROXSON-OS-INTEGRATION` (the fork of `bargeranthony-gif/HIVE`). The public draft PR is for evaluation of a **synthetic-only**, research-only extension. This is NOT an implementation of proprietary algorithms, licensed external data, real-world company surveillance, investment signals, trade execution, or a commercial derivative.

## 1. What changed, and what did not

The S2 upgrade extends the existing S1 review module without changing any of Tony's inherited HIVE CLI, registry, repository discovery, or SQLite schema code. The new module `hive/temporal_graph.py` imports only S1's offline fixture parser and timestamp/boundary error functions. Run it from the fork checkout using `python3 -m hive.temporal_graph`. No `hive` CLI command, schema migration, background worker, agent, connector, or new governing constitution is introduced.

S1 hardening modifies **only the new S1 candidate**, not inherited HIVE: strict JSON duplicate-key/nonfinite rejection, bounded labels and monetary values, and explicit rejection of S2 timestamp/revision packets by S1's first-of-kind reader. This prevents accidentally presenting a first-arrival filed revenue value when later revisions or competing claims exist.

### Files in this upgrade

- `hive/temporal_graph.py` - pure offline point-in-time queries, root-aware conflict adjudication, deterministic provenance, bounded directed paths, historical snapshot deltas, CLI report.
- `fixtures/cedar_arc_temporal.json` - synthetic S1-extension fixture with a fictional supplier/port/region graph, timestamped revisions, conflicting financial sources, and malicious/excluded records.
- `tests/test_temporal_graph.py` - adversarial and metamorphic acceptance tests.
- `tests/test_company_intel_hardening.py` - security and S1-backward-compatibility tests.
- `scripts/verify_offline_review.sh` - one-command original HIVE + S1 + temporal-graph regression runner, an isolated HIVE_HOME, and report-receipt validation. It additionally runs `tests/test_financial_replay.py` if that separate review suite is present in the checkout; the isolated local 85-test receipt did not include it.
- This review document, a scoped note in the S1 review record, and a confined S1 parser/validator edit.

## 2. What becomes computable

### 2.1 Historically valid availability

Each admissible record requires both an offset-aware `published_at` and an explicit `first_available_at`. Its usable time is `max(published_at, first_available_at)`. An as-of snapshot cannot use any record whose usable time is after the requested cutoff, even if an observation or report refers to an earlier fiscal period. If `first_available_at` is UNKNOWN, the record is **excluded**, not guessed into availability. This is necessary but not sufficient for real historical backtesting: timestamps supplied by synthetic fixtures are not independently authenticated.

### 2.2 Original-root and revision-sensitive evidence

Source IDs identify a record. Root IDs identify its claimed original origin. Repeated republications with the same root cannot manufacture multiple independent supports. A newer record may supersede another only through an explicit `revision_of` edge where the older and newer records share exact legal entity, record kind, original root, and measurement period, and where the newer version became usable later. Orphan, cross-root, cross-entity, cross-period, cyclic, and non-increasing revisions fail closed.

When two different original roots disagree about the same metric and period, the candidate emits `INDEPENDENT_ORIGINAL_ROOT_DISAGREEMENT`, both original observations, and an unresolved decision state. It never averages or silently chooses a winner. Without an explicit valid revision, incompatible values attributed to one root are marked `SAME_ORIGINAL_ROOT_CONTRADICTION`.

Root identity is fixture-supplied, **not externally verified independence**. Different root labels can still hide common ownership or shared upstream sources. Independent verification remains required in real data.

### 2.3 Truth-class separation

`FILED_REVENUE_USD` and `VENDOR_REVENUE_ESTIMATE_USD` remain separate claim classes. Shipment counts and declared customs values are separate unit-bearing facts and cannot be converted into sales, margin, or profits. An observed supplier link is not proof of material dependence, ownership, or causation. Docket outcomes are scoped to a named fictitious case; a missing judgment field yields `UNKNOWN`, never false. Legislative effectiveness is scoped to a named fictitious bill; unrecognized status yields `UNKNOWN`.

For the November 2026 fictional snapshot, the prior filing of USD 40M is superseded *within its source root* by a later USD 41M revision; a different original root asserts USD 42M. The vendor estimate remains USD 52M. S2 retains the contradiction and shows the participating sources. For March 10, 2026, only the earlier USD 40M filing is available. These are generated fictional numbers, not audited corporate or financial facts.

### 2.4 Graph navigation without fabricated causal conclusions

Relationships are directed and require explicit exact fake-entity identifiers. The only supported relationship predicates are `SUPPLIES_OBSERVED`, `SHIPS_THROUGH_OBSERVED`, and `OPERATES_IN_CLAIMED`. Bounded traversal emits source-linked paths of at most three hops, up to 128 paths; it rejects cycles and never infers ownership, supplier exclusivity, global coverage, risk magnitude, or predicted price movements from graph connectivity. Any reported qualification is *fixture-attested* rather than independently verified.

### 2.5 Historical change intelligence

`compare_temporal_graph` computes two bounded as-of snapshots from the same permitted synthetic packet and returns newly eligible source IDs, newly present or superseded source-linked claims, newly visible contradictions, and newly reachable non-causal graph paths. This is a **temporal evidence diff**, not a quantified economic event, causal model, trading signal, or proof of external publisher timestamps. No database, agent workflow or new storage service is introduced.

### 2.6 Confidentiality and execution boundary

Before accepted record fields are interpreted or hashed, the evaluator checks tenant identity, visibility, exact entity and jurisdiction, rights, cost, kind, and point-in-time availability. Restricted and cross-tenant payloads do not appear in JSON, Markdown, source trace, or report content. Source prose is not executed or promoted into authority. Tokens, provider credentials, external requests, paid credits, live trading, and the HIVE SQLite registry are not touched. A local report directory is written only when explicitly supplied.

**Critical limit:** Setting `synthetic: true` does not prove that real information has been anonymized. Never load real customer, company, or licensed provider data into these *public* fixture files. The synthetic-only parser is not a general purpose privacy system.

## 3. How to run the review in the existing fork

From the review branch's checkout, with Python 3.10+ and pytest already installed:

```bash
bash scripts/verify_offline_review.sh
```

The runner uses a disposable local `HIVE_HOME`, performs no installation or network request, runs the full existing HIVE regression tests together with S1 and S2 tests, and confirms the S2 synthetic receipt. If pytest is absent, it exits BLOCKED without trying to install it.

Generate a historical report without modifying HIVE's SQLite database:

```bash
python3 -m hive.temporal_graph --fixture fixtures/cedar_arc_temporal.json --as-of 2026-03-10T00:00:00Z
```

Compare two historical synthetic snapshots and reveal what became newly usable between them:

```bash
python3 -m hive.temporal_graph --fixture fixtures/cedar_arc_temporal.json --compare-from 2026-03-10T00:00:00Z --as-of 2026-11-01T00:00:00Z
```

Generate current synthetic fixture report to an explicitly chosen local folder:

```bash
python3 -m hive.temporal_graph --fixture fixtures/cedar_arc_temporal.json --output /tmp/hive-s2-review
```

`--online` does not exist and is rejected. The module is deliberately not wired to HIVE's existing database or runtime feature flags, avoiding accidental production activation.

## 4. Acceptance and maturity record

- Original HIVE test suite: **8 passing locally**. Original inherited source/test components were compared to the fork's Git blob hashes in the preceding S1 review.
- S1 original synthetic acceptance suite: **18 passing locally**.
- New S1 hardening tests: **11 passing locally**.
- New S2 temporal graph test cases (including parameterized variants): **48 passing locally**.
- Combined local regression: **85 passing**. This is **TESTED IN ISOLATION** only, not production verified or verified recurring.
- Metamorphic controls: shuffled record order cannot change the report; equivalent timezone cutoffs generate identical snapshots; repeated runs yield deterministic source fingerprints; later discoveries cannot leak into an earlier as-of snapshot.
- Adversarial controls: invalid JSON, duplicate keys, NaN/Infinity, malicious Markdown labels, tenant-scope poisoning, restricted records, fictitious approval claims, incorrect identity, rights/cost rejection, and revision manipulation.
- Test environment: CPython 3.13.5 / pytest 9.0.2 in local evaluation. No GitHub Actions run is claimed until independently observed.

The 85-pass number only proves the listed test assertions on the inspected source code. It is not a blanket security, accuracy, fairness, legal or performance certification.

## 5. Concurrent fictional financial-replay candidate (preservation note)

During this review, the same fork review branch advanced independently to commit `5d50b83d7d2f7a7c9f200021bb2968cd796e5034`, which **added** four separate public-safe files including `hive/financial_replay.py`, `tests/test_financial_replay.py`, `fixtures/economic_replay_synthetic.json`, and `docs/FINANCIAL_REPLAY_S2_REVIEW.md`. These files describe a distinct frozen-holdout/placebo financial-replay laboratory. Its documentation reports 44 synthetic tests; these were not available in this local isolated source workspace and were **not independently rerun** in our 85-test receipt. S2 temporal graph does not import or override that module and has no authority to promote its results into real financial evidence. The optional test runner includes its test suite when present in the checkout. A complete combined checkout regression and review remain a post-publication validation gate.

## 6. Relationship to BROXSON OS, LogiKey, ARKHIVE, and AI Network OS

- **HIVE (this fork):** candidate, read-only discovery/evidence-research surface, with isolated synthetic review implementation only.
- **BROXSON OS:** existing governing authority, evidence and execution policies remain outside this module and are *not* bypassed or re-created. No operational BROXSON policy adapter has been implemented in this PR.
- **LogiKey:** source-backed memory, corrections and institutional truth remain independently authoritative. No live LogiKey source ingestion or write-back has been implemented.
- **ARKHIVE:** potential origin-preservation and archival provenance integration; actual running archive interface is UNKNOWN, not simulated as functional.
- **AI Network OS:** potential read-only projection/adapter boundary; live contract and integration tests have not been completed against this branch.
- **External economic data:** no permitted historical shipment feed, real entity matching, licensed provider rights, backtesting series or predictive uplift has been established.

Do not build a replacement governance engine, duplicate source-of-truth database, or source-harvesting system around this synthetic example. The next integration, if authorized, should adapt *existing* governance and evidence contracts with a read-only adapter and explicit deny-by-default permissions.

## 7. Intellectual property and release gates

Published upstream `bargeranthony-gif/HIVE` declares `Proprietary` in `pyproject.toml`. No executed commercial or proprietary derivative rights license was located. GitHub access, a fork, this test record, or a pull request do not grant a proprietary commercial license. Tony's current unpublished local HIVE code, source ownership, contributions, permissions and asset-specific licenses remain UNKNOWN. Public code in this branch is a fictional review example only; no confidential algorithms, proprietary implementation details, private data, API keys or IP transfer terms belong in a public repo.

**Never merge, deploy, transfer rights, enable paid providers, publish commercial derivatives or trade on these examples until** (1) authorized rights holders and written scope are verified, (2) Tony's latest source is available for a permitted compatibility review, (3) actual source ZIP and prior S1 candidate are compared, (4) original/new tests pass on the *real* target tree with an independent review, and (5) BROXSON authority and execution contracts are demonstrably enforced where applicable. Preserve `UNKNOWN` on all missing gates.

**Decision:** keep PR draft, fork-only, isolated, fictional, and zero-spend. Do not interpret a test pass as signed authority, economic predictive value, or permission to commercialize.
