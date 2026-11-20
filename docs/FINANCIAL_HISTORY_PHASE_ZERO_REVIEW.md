# Financial history admissibility gate — Phase Zero (review candidate)

Date: 2026-11-15. Scope: **offline, synthetic, read-only**. This is a bounded adjunct to the existing HIVE Python package, not a forecasting model, provider integration, trading engine or alternative governance authority.


## November 15, 2026 implementation extension — HIVE revision-aware replay

**Status:** IMPLEMENTED AS A GITHUB DRAFT REVIEW CANDIDATE; SYNTHETIC TESTED LOCALLY; NOT PRODUCTION VERIFIED. The implementation is in **this fork's existing draft PR #2** (not merged). It adds two new files without modifying existing HIVE source: `hive/financial_replay.py` and `tests/test_financial_replay.py`. The earlier `assess()` and `validate_snapshot()` functions remain unchanged for compatibility. **Do not use `validate_snapshot()` as a leakage-safe feature-selection or revision-aggregation engine:** it reports separate eligible rows, including several historical revisions of one record, without reconstructing which single revision was available at a prediction cutoff.

### Exact, additive interface

```python
from hive.financial_replay import replay_as_of
result = replay_as_of(fictional_records, "2026-01-07T00:00:00Z", tenant_id="SYNTHETIC")
# result["selected_observations"] is at most one revision per source event
# result["production_accepted"] is ALWAYS False
```

`replay_as_of()` uses Python standard library and the pre-existing `hive.financial_history` validator. It does **not** read or write HIVE SQLite, use API credentials, send network requests, spend credits, invoke models, generate forecasts or place orders. This is a fixture admission checker for the intended future data contract, not a legally authoritative evidence or identity verifier.

### Non-compensatory replay gates

1. **Scope first:** disallowed tenant, restricted visibility and non-synthetic records are rejected *before* source fields are inspected; their identifiers and text are omitted from returned receipts. Out-of-scope rows cannot poison an in-scope record with the same apparent identifiers.
2. **Exact identity:** require a 10-digit string issuer CIK, legal importer ID, matching fields in a synthetic mapping evidence record, and a fictional evidence ID; names alone are never sufficient.
3. **Four clocks:** distinguish measured event/period, initial public release, **specific revision publication**, and evidence capture. Require timezone-aware timestamps, a consistent ordering and an as-of cutoff. Retrieval after cutoff may be permitted only because fictional independent historical publication evidence is asserted.
4. **Revisions:** group by provider/source/event, require a complete ordered parent chain, prohibit identity or measurement-period reassignment, ignore revisions not yet published at the cutoff, and select the single latest admissible revision. Missing/duplicated/reordered lineage quarantines the event.
5. **Independent roots:** if two selected provider records cite the same original document root, quarantine both rather than double-counting an aggregator copy as independent economic activity.
6. **Measurement safety:** permit only nonnegative integer `shipment_count` in a bounded range. A shipment count is never silently converted to revenue, inventory, customs value, margin, or earnings.
7. **Source integrity:** SHA-256 checks the exact UTF-8 bytes of the provided **fixture excerpt**; it is **not** a hash of a complete external source document or a proof that its asserted publication date is genuine. The raw excerpt is not emitted into receipts.
8. **Rights and authority:** a declared fictional research-rights receipt and historical-availability receipt are required. These labels are untrusted fixture data, not real legal grants or independently authenticated releases. No text inside an input record becomes instructions or authorization.
9. **Determinism and limits:** input-order-invariant, stable JSON-style output and SHA-256 receipt digest; at most 1,000 rows. Invalid source text and pathological count values fail closed. Returned output explicitly fixes `real_data_rights_verified=False`, `production_accepted=False` and `predictive_improvement='UNKNOWN'`.

### Current local test receipt and exact files

Current local isolated test run: `PYTHONPATH=. python3 -m pytest -q tests/test_financial_history.py tests/test_financial_replay.py` produced **56 passed**, including the prior local validator fixture tests and new adversarial replay tests. New files are Git-blob-verified after GitHub publication:

- `hive/financial_replay.py`: blob SHA-1 `99bdc5e88b88ec2d6508d7ca390f5e607e780af8`.
- `tests/test_financial_replay.py`: blob SHA-1 `bd63b73d3a08ce138ffc0dc7c26d0c84f59cce4b`.

**Limit:** the local previous-validator copies were equivalent implementations, not verified as byte-identical GitHub blobs; the original HIVE eight tests and GitHub-hosted CI were **not** rerun in this session because the local container could not resolve github.com. This is **isolated synthetic proof**, not repository-wide regression proof, acceptance by BROXSON, a working HIVE financial service, or market backtesting.

### Minimal cross-system integration seam, not parallel architecture

| Existing system | Future role | Current adapter state |
| --- | --- | --- |
| HIVE | Importable synthetic replay gate in this fork; optional reviewed company brief | New local module added to PR #2; PR #1 separate |
| BROXSON OS | Existing permission/evidence/authority and acceptance floor | NOT INVOKED by this module; no governance registry created |
| ARKHIVE | Preserve original data bytes, release/vintage lineage, corrections and negative forecasts where authorized | Interface requirement only; runtime access UNKNOWN |
| LogiKey | Source-linked contradiction explanations; hypothesis and falsifier narration | NOT CONNECTED |
| AI Network OS | Bounded task/approval coordination under issue #13 | Tracker exists; execution adapter NOT CONNECTED |

**Promotion rule:** no proposed source observation can be accepted for real research solely because the JSON says "VERIFIED". A future live adapter must independently authenticate provenance, public historical release, exact issuer mapping, provider terms, rights scope, completeness and actual raw-source hash. Until then all selected rows are **FICTIONAL**, and the live-data gate remains **BLOCKED**. Do not conflate technical fixture validity with legal access or predictor performance.

### Primary-source research, current policy boundary

- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): public issuer filings/XBRL can support inventory targets and lagged fundamentals; retain issuer CIK, accession, accepted/filed times, units, period, amendments and exact concept. The current Company Facts API is not a frozen historical snapshot. Follow the [SEC fair-access policy](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data); **no SEC calls in this implementation**.
- [FRED/ALFRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html): historical data vintages distinguish figures knowable then from revised figures known now. They do **not** give importer-specific shipments. [Vintage dates reference](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html).
- [ImportYeti Purchased Data scope](https://www.importyeti.com/policies/data-use) and [Terms](https://www.importyeti.com/policies/terms): their broad purchased-data covenant expressly does **not** cover the free version; automated scraping and circumvention are restricted. The previously tested connected detailed-history request was credit-blocked. No budget, subscription or entitlement is assumed.
- [UN Comtrade](https://comtradeplus.un.org/en/api-docs) reports product/country aggregates; cannot substitute for importer-level bills of lading.

### Hold gate: exact first statistical experiment

Only after lawful, genuinely historical issuer-linked shipment data is available: pre-register next-quarter **reported inventory growth** as the target; pin a seasonal + lagged-filing baseline; compare the **same** chronology and eligible issuers after adding shipment features; reserve the latest 20% of chronological outcomes untouched; report sample count, missingness, false issuer links, multiple-hypothesis trials, prediction intervals, error difference, null result and any sensitivity to corrections. Avoid cross-sectional leakage and changes in vendor coverage. **Three issuers can prove engineering feasibility, not a general stock-market edge.**

This extension does not change Tony's unpublished HIVE, the original proprietary license, the approval boundary, or the no-spend/no-trade decision. Review only; no automatic merge, commercial derivative release, deployment or external sharing is authorized.


## Governing experiment

The authoritative research tracker is [AI Network OS issue #13](https://github.com/LogiKeyEnterprises/ai-network-os/issues/13): test whether historically available importer shipments incrementally improve next-quarter **reported inventory growth** versus lagged disclosed fundamentals and seasonality. Current status: **BLOCKED** because required historical issuer-level shipment records, verified identifier mappings, historical publication timestamps and usage rights have not been established. Predictive benefit: **UNKNOWN**.

Existing [HIVE S1 draft PR #1](https://github.com/LogiKeyEnterprises/GLOBAL-FINANCE-BROXSON-OS-INTEGRATION/pull/1) is a separate fictional-company brief. This validator is deliberately independent of that draft. No changes to existing HIVE files, no inferred compatibility with Tony's unpublished build, no merge into his upstream.

## What has been implemented

- `hive/financial_history.py`: pure functions `assess(record, cutoff)` and `validate_snapshot(records, cutoff)` with structured eligibility and reject reasons.
- `tests/test_financial_history.py`: 12 synthetic checks for late publication, unsupported look-alike identity, distinct revisions, duplicate revisions, missing/naive timestamps, inconsistent availability, unconfirmed rights, invalid issuer ID and inert adversarial text.
- No imports beyond the Python standard library; no calls, file writes, SQLite schema, subprocesses, executable source text, credentials, paid data, external provider calls or transaction permissions.

## Proposed observation fields

`source_id`, `record_id`, `issuer_cik`, `legal_importer_id`, `event_date`, `first_publication_time`, `retrieved_at`, `available_as_of`, `usage_rights`, `units`, `value`, `mapping_proof`, `revision_id`.

All synthetic fixtures explicitly designate `usage_rights=APPROVED_RESEARCH` and `mapping_proof.status=VERIFIED`. **These are fictional fixture labels; the validator does not issue legal permissions or independently authenticate that evidence**. For live observations, caller must verify provider terms, original source receipts, authoritative identities and actual historical availability before assigning such labels. An ISO date supplied by a vendor alone is not proof of public availability at that date.

The observation's measured period is not its publication time. The record's retrieval date does not establish it was public at an earlier cutoff. This implementation checks supplied evidence assertions only; later production interfaces would need authoritative verifiers and immutable source receipts.

## Local test receipt

Independent minimal-module local run on November 15, 2026: `python -m pytest -q tests/test_financial_history.py` -> **12 passed**. The local runner used the module and equivalent test logic before connector publication. Full original HIVE suite was **not run in this session** because direct GitHub cloning from this container failed on DNS resolution; the original suite is therefore **NOT VERIFIED HERE**. Historical 8 original tests and the separate S1 PR's reported 26 passing tests are prior receipts, not current execution evidence.

The connector GitHub branch commits and post-publication file reads are separate evidence; a successful GitHub API write does not prove GitHub CI ran.

## Phase Zero research-source priority and constraints

1. **SEC EDGAR**: candidate official issuer filings and reported inventory facts, keeping accession number, filing timestamp, period, units, taxonomy and subsequent amendment/revision. Corporate facts fetched today are not automatically point-in-time.
2. **ImportYeti**: importer/supplier discovery candidate. Prior connected company queries returned records but detailed historical access exhausted/blocked on credits. No entitlement, legal replay rights or first-publication timestamps verified. No automated scraping or limit bypass.
3. **ALFRED**: public historical macro vintages are useful to exercise an as-of join as a *different* experiment, not a replacement for issuer-level import shipments. Confirm API access and provider terms.
4. **UN Comtrade**: country/product-level aggregates; not issuer-specific bills of lading. Do not substitute this dataset for a company-level shipment signal.
5. **Market prices**: historical securities identifiers, corporate actions, timestamps, entitlement and adjustments remain unselected; not needed for the inventory-growth Phase Zero test.

James Washington's published grocery-tracker, event-radar, causal-study, eBay, wdot and artifacts examples provide *methods to evaluate*—periodic capture, source matching, candidate ranking, baseline comparisons, observed versus quoted outcomes and transparent review packages—not imported financial code or validated investment signals. No third-party source copied.

## Acceptance and promotion boundaries

| Concern | Current finding | Promotion gate |
| --- | --- | --- |
| Offline historical eligibility | IMPLEMENTED, locally tested in synthetic fixtures | Review tests in GitHub CI / authorized runner and confirm integration |
| Real importer historical access | BLOCKED | Obtain lawful dataset and permitted reuse |
| Historical first-publication evidence | UNKNOWN | Independent records / vintage receipts |
| Issuer-importer link | UNKNOWN | Registered identity and issuer evidence |
| Next-quarter inventory outcome | NOT INGESTED | Timestamp-correct SEC filings and target definition |
| Predictive advantage | UNKNOWN | Pre-registered A vs B walk-forward test, untouched holdout |
| Commercial derivative rights | UNKNOWN | Obtain rights-holder agreement/legal review |
| Tony's latest local HIVE build | UNKNOWN | Compare exact authorized commit/worktree |

Preserve original HIVE source, upstream attribution and proprietary license. Do not merge, deploy, purchase, schedule, publish client data, authorize transfers or trade. Chancellor retains business decisions; Tony is a proposed reviewer, not an assigned implementer.

## Next proof, once authorization and data gate permit

Record original source URL/receipt/hash and provider permission; verify up to three issuer/importer mappings; obtain lawful point-in-time shipment records; pre-register *next-quarter reported inventory growth* and baseline; produce a reproducible chronological comparison. **Stop with BLOCKED/UNKNOWN** when any required rights or historical timing evidence is missing.
