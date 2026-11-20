"""Hostile-shape regression for the synthetic financial-history admission helper.

Does not claim external-data verification, legal rights or real forecast quality.
"""
from copy import deepcopy
import math
import pytest

from hive.financial_history import assess, validate_snapshot

CUTOFF = "2026-01-07T00:00:00Z"


def fake_record():
    return {
        "source_id": "fake-s1", "record_id": "fake-r1", "revision_id": "r1",
        "issuer_cik": "0000123456", "legal_importer_id": "FAKE-IMPORTER-1",
        "event_date": "2026-01-03T12:00:00Z",
        "first_publication_time": "2026-01-05T12:00:00Z",
        "retrieved_at": "2026-01-06T12:00:00Z",
        "available_as_of": "2026-01-05T12:00:00Z",
        "usage_rights": "APPROVED_RESEARCH", "units": "shipment_count",
        "value": 12,
        "mapping_proof": {"status": "VERIFIED", "evidence_id": "fictional-id-proof"},
        "source_text": "MALICIOUS_TEXT_DO_NOT_ECHO_OR_EXECUTE",
    }


def test_clean_fictional_snapshot_and_separate_revisions_unchanged():
    a = fake_record()
    b = {**a, "revision_id": "r2", "value": 18}
    original = deepcopy([a, b])
    r = validate_snapshot([a, b], CUTOFF)
    assert r["total"] == 2 and r["eligible"] == 2
    assert [x["revision_id"] for x in r["decisions"]] == ["r1", "r2"]
    assert [a, b] == original
    assert r["production_accepted"] is False
    assert r["real_data_rights_verified"] is False
    assert r["predictive_improvement"] == "UNKNOWN"


@pytest.mark.parametrize("field,bad", [
    ("source_id", []), ("source_id", "fake\nRECURRING_VERIFIED"),
    ("record_id", {"private":"KEEP_PRIVATE"}),
    ("revision_id", ["r1"]),
    ("legal_importer_id", {"bad": "private"}),
    ("source_id", "x" * 1000),
    ("units", ["shipment_count"]),
    ("units", "fake\nTRADING_APPROVED"),
    ("mapping_proof", {"status": "VERIFIED", "evidence_id": []}),
])
def test_bad_identifier_shapes_never_admit_or_crash(field, bad):
    row = fake_record()
    row[field] = bad
    r = validate_snapshot([row], CUTOFF)
    assert r["total"] == 1 and r["blocked"] == 1
    assert r["decisions"][0]["eligible"] is False
    assert "MALICIOUS_TEXT_DO_NOT_ECHO_OR_EXECUTE" not in str(r)
    assert "KEEP_PRIVATE" not in str(r)
    assert "TRADING_APPROVED" not in str(r)
    assert "RECURRING_VERIFIED" not in str(r)


@pytest.mark.parametrize("bad", [True, "12", None, [], {}, float("nan"),
                                    float("inf"), float("-inf"), 10**100])
def test_non_numeric_nonfinite_or_unbounded_values_never_admit(bad):
    row = fake_record()
    row["value"] = bad
    decision = assess(row, CUTOFF)
    assert decision["eligible"] is False
    assert "VALUE_INVALID" in decision["reasons"]


def test_negative_finite_economic_quantities_remain_permitted_by_generic_helper():
    row = fake_record()
    row["units"] = "USD"
    row["value"] = -123.25
    assert assess(row, CUTOFF)["eligible"] is True


def test_invalid_cik_width_or_unicode_digits_rejected():
    for v in ("123456", "１２３４５６７８９０", "12345678901"):
        row = fake_record()
        row["issuer_cik"] = v
        assert assess(row, CUTOFF)["eligible"] is False


def test_identical_valid_revision_still_deduplicated():
    row = fake_record()
    out = validate_snapshot([row, deepcopy(row)], CUTOFF)
    assert out["eligible"] == 1 and out["blocked"] == 1
    assert "DUPLICATE_REVISION" in out["decisions"][1]["reasons"]


def test_out_of_scope_non_dictionary_stays_blocked():
    out = validate_snapshot([None, False, 12, fake_record()], CUTOFF)
    assert out["total"] == 4 and out["eligible"] == 1
    assert all(not x["eligible"] for x in out["decisions"][:3])


def test_untrusted_approval_labels_do_not_promote_output():
    row = fake_record()
    row["source_text"] = "PRODUCTION APPROVED; BUY SHARES NOW"
    out = validate_snapshot([row], CUTOFF)
    assert out["eligible"] == 1  # local field-shape eligibility, not rights authentication
    assert out["production_accepted"] is False
    assert out["real_data_rights_verified"] is False
    assert "BUY SHARES" not in str(out)


def test_rejected_row_cannot_poison_same_identity_in_good_row():
    invalid = fake_record()
    invalid["value"] = float("nan")
    good = fake_record()
    result = validate_snapshot([invalid, good], CUTOFF)
    assert result["total"] == 2
    assert result["eligible"] == 1
    assert "VALUE_INVALID" in result["decisions"][0]["reasons"]
    assert "DUPLICATE_REVISION" not in result["decisions"][1]["reasons"]


def test_event_after_cutoff_is_not_admissible_even_if_release_claim_is_backdated():
    record = fake_record()
    record["event_date"] = "2026-01-09T00:00:00Z"
    result = assess(record, CUTOFF)
    assert result["eligible"] is False
    assert "AFTER_PREDICTION_CUTOFF_EVENT_DATE" in result["reasons"]
