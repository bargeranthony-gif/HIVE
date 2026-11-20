# HIVE — Company Intelligence S1 synthetic review candidate

**Scope:** Public-safe, additive, research-only candidate. **Not merged, deployed, licensed for commercial use, or integrated with Tony's unpublished build.**

## Provenance boundary

- Upstream: `bargeranthony-gif/HIVE` (public); current fork: `LogiKeyEnterprises/GLOBAL-FINANCE-BROXSON-OS-INTEGRATION`.
- Fork base inspected for this review: `main` at `923c339902b23ae015ef1e42b9fbab957ffd0d86`.
- The previously described 18-test *standalone* prototype source archive was discoverable as a file record, but its original bytes were **not available for byte-for-byte comparison** in this task. This is an independently reconstructed additive candidate based on the prior acceptance report and example brief. It is not represented as the original archive.
- Added `hive/company_intel.py`, `fixtures/cedar_arc.json`, and `tests/test_company_intel.py`. Existing HIVE code, CLI, SQLite schema, and tests remain unchanged.
- No actual ImportYeti, ZoomInfo, DataForB2B, Global Database, Company Dossier, Legal Data Hunter or CourtListener transport is implemented. Provider states are synthetic fixture labels only.

## Local test receipt (not remote CI)

Environment: Python 3.13.5, pytest 9.0.2, no third-party pytest plugins, no network used.

Run from project root:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_core.py tests/test_inspector.py tests/test_company_intel.py --disable-warnings
PYTHONPATH=. python3 -m hive.company_intel --fixture fixtures/cedar_arc.json --output reports
```

Observed on 2026-11-15: **26 passed** (8 existing HIVE tests + 18 new S1 synthetic tests). The eight original HIVE tests and six required original HIVE modules were checked against their Git blob SHA-1 values before running. The original suite was executed from an isolated workspace containing the exact tested source files and original test modules; this does **not** represent a full production checkout or CI verification.

Acceptance boundaries: fictional registered ID and tenant scope; revenue versus vendor estimate; shipment counts versus sales; customs values; case allegation versus dismissal; proposed versus effective law; publication-time exclusion; source-root de-duplication; no source-driven maturity promotion; injected text nonexecution; unknown rights/paid-cost blocking; simulated provider failures; deterministic receipt and no live-provider calls.

## Review gates

| Gate | Status |
| --- | --- |
| Original HIVE regression tests | LOCAL TESTED (8/8) |
| New synthetic acceptance tests | LOCAL TESTED (18/18) |
| Actual previously packaged S1 source archive reconciliation | BLOCKED (raw archive unavailable) |
| Tony's latest unpublished HIVE build compatibility | UNKNOWN |
| Existing private analyzer PR integration | NOT ATTEMPTED; intentionally isolated |
| Real provider entitlements and terms | UNKNOWN |
| Independent third-party review | PENDING |
| Commercial derivative license or asset-specific IP agreement | **NOT EXECUTED / BLOCKED** |
| Predictive value or real financial accuracy | NOT TESTED |
| Live provider calls, paid credits, trades, deployment | **ZERO** |

**Promotion rule:** No merge, distribution as a proprietary product, paid data ingestion, production activation, or automated external action until rights, source comparison, full regression and human acceptance gates have independent evidence.

## Rights and collaboration decision

The public upstream declares `license = {text = "Proprietary"}` in `pyproject.toml`; no grant of commercial derivative rights was verified. A GitHub fork is not a standalone commercial license. This evaluation branch does not assign Tony's prior work or the user's background IP. Obtain an asset-specific, signed arrangement from verified rights holders before commercial exploitation or proprietary re-licensing. Keep confidential source and collaboration details outside this public fork.

## Minimal follow-up

1. Obtain the actual standalone source ZIP through a directly accessible attachment or authorized source location, then compare it to this reconstructed candidate before claiming a source integration.
2. Ask the applicable rights holder(s) to define written rights for review, modification, commercialization, distribution, and improvements. Obtain appropriate legal review. Do not presume consent from GitHub visibility.
3. When access and rights are established, test against Tony's *actual* current working tree and the existing evidence-analyzer changes, preserving his local work.
4. Do not proceed to live data, prediction, subscriptions, or infrastructure expansion from this fixture test.

## S2 follow-on (2026-11-15)

The later S2 additive candidate is documented in `docs/COMPANY_INTELLIGENCE_S2_REVIEW.md` and uses `python3 -m hive.temporal_graph`. The original S1 first-of-kind reader now explicitly rejects temporal/revision packets, and its JSON parser and display labels reject ambiguous or injectable input. These are bounded review-code hardening changes only; inherited Tony HIVE modules remain unchanged. The 26-pass historical S1 result remains a distinct earlier milestone; see S2 for the combined 85-test local receipt and additional blockers. No commercial permission is implied.
