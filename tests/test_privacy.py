"""Tests for linga.privacy.*.

Covers the four invariants that matter for M4:

1. The scanner never leaks raw PII — it only emits column names, signal tags
   and a terminal-friendly risk string.
2. Pseudonymisation is deterministic given a key, and different values with
   the same key never collide for short inputs.
3. The generalisation helpers do not raise on null/garbage input; they return
   empty strings or ``None``.
4. Small-cell suppression handles the zero-vs-small case and applies secondary
   suppression as intended.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from linga.pipeline_support import protect_dataframe
from linga.privacy.generalise import (
    age_to_band,
    drop_free_text,
    generalise_date_to_month,
    generalise_dob,
    generalise_gps,
    lookup_admin_area,
)
from linga.privacy.minimise import extract_referenced_columns, minimise_columns
from linga.privacy.patterns import (
    EMAIL_RE,
    NRC_RE,
    mask_generic,
    mask_phone,
    matches_phone,
    normalise_phone,
)
from linga.privacy.pseudonymise import pseudonymise_series, pseudonymise_value
from linga.privacy.scanner import scan_dataframe
from linga.privacy.suppression import suppress_series, suppress_table
from linga.security.keys import write_key
from linga.synthetic import SyntheticOptions, generate_round

# ---- patterns ---------------------------------------------------------------


def test_nrc_regex_matches_zambian_shape() -> None:
    assert NRC_RE.search("123456/78/1")
    assert not NRC_RE.search("12345/78/1")
    assert not NRC_RE.search("not an id")


def test_phone_regex_accepts_common_zambian_formats() -> None:
    assert matches_phone("0977123456")
    assert matches_phone("+260977123456")
    assert matches_phone("0977 123 456")
    assert matches_phone("0977-123-456")
    assert not matches_phone("0811234567")  # wrong prefix
    assert not matches_phone("123")


def test_mask_phone_hides_middle() -> None:
    assert mask_phone("0977123456") == "0977****56"
    assert mask_phone("+260977123456") == "2609****56"


def test_mask_generic_keeps_tail() -> None:
    assert mask_generic("abcdef", keep=2) == "****ef"
    assert mask_generic("ab", keep=2) == "**"


# ---- scanner ----------------------------------------------------------------


def test_scanner_flags_nrc_and_phone_and_email() -> None:
    df = pd.DataFrame(
        {
            "nrc": ["123456/78/1", "234567/89/2"],
            "phone": ["0977123456", "0966112233"],
            "contact_email": ["a@b.co", "c@d.co"],
            "favourite_colour": ["red", "blue"],
        }
    )
    report = scan_dataframe(df)
    by_col = {c.name: c for c in report.columns}
    assert by_col["nrc"].risk == "high"
    assert by_col["phone"].risk == "high"
    assert by_col["contact_email"].risk == "high"
    assert by_col["favourite_colour"].risk == "low"


def test_scanner_never_contains_raw_values_from_the_frame() -> None:
    df = pd.DataFrame(
        {
            "nrc": ["123456/78/1", "234567/89/2"],
            "phone": ["0977123456", "0966112233"],
            "comments": ["Met Alice at 0977555000", "Email bob@example.com"],
        }
    )
    report = scan_dataframe(df)
    blob = json.dumps(report.to_dict())
    for raw in [
        "123456/78/1",
        "234567/89/2",
        "0977123456",
        "0966112233",
        "Alice",
        "bob@example.com",
    ]:
        assert raw not in blob, f"raw value {raw!r} leaked into scan output"


@given(st.integers(min_value=100000, max_value=999999), st.integers(min_value=1, max_value=99))
def test_scanner_never_leaks_arbitrary_nrcs(serial: int, region: int) -> None:
    nrc = f"{serial:06d}/{region:02d}/1"
    df = pd.DataFrame({"national_id": [nrc, nrc, nrc, nrc]})
    report = scan_dataframe(df)
    blob = json.dumps(report.to_dict())
    assert nrc not in blob


# ---- pseudonymise -----------------------------------------------------------


def test_pseudonymise_value_is_deterministic() -> None:
    key = b"\x01" * 32
    a = pseudonymise_value("P0001", key)
    b = pseudonymise_value("P0001", key)
    assert a == b
    assert len(a) == 16


def test_pseudonymise_value_changes_with_key() -> None:
    k1 = b"\x01" * 32
    k2 = b"\x02" * 32
    assert pseudonymise_value("P0001", k1) != pseudonymise_value("P0001", k2)


@given(
    st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), min_size=8, max_size=50)
)
def test_pseudonyms_do_not_leak_inputs(value: str) -> None:
    """Any input of reasonable length never appears inside its own HMAC digest."""

    key = b"\x03" * 32
    hashed = pseudonymise_value(value, key)
    assert value not in hashed


def test_pseudonymise_series_preserves_missing() -> None:
    key = b"\x04" * 32
    s = pd.Series(["x", "", None, "y"])
    out = pseudonymise_series(s, key)
    assert out.iloc[1] == ""
    assert out.iloc[2] == ""
    assert out.iloc[0] != ""
    assert out.iloc[0] != out.iloc[3]


# ---- minimise ---------------------------------------------------------------


def test_extract_referenced_columns_handles_tokens() -> None:
    exprs = ["${age} > 18 and sex == 'female'", "selected(., 'wash')"]
    found = extract_referenced_columns(exprs)
    assert "age" in found
    assert "sex" in found
    assert "and" not in found
    assert "selected" not in found


def test_minimise_drops_unlisted_columns_and_keeps_order() -> None:
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    out = minimise_columns(df, keep=["a", "c"], always_keep=["b"])
    assert list(out.columns) == ["a", "b", "c"]
    missing = minimise_columns(df, keep=["zzz"])
    assert missing.empty or list(missing.columns) == []


# ---- generalise -------------------------------------------------------------


def test_age_bands() -> None:
    assert age_to_band(7) == "5-9"
    assert age_to_band(30) == "25-34"
    assert age_to_band(90) == "65+"
    assert age_to_band(-1) == ""
    assert age_to_band(None) == ""


def test_generalise_dob_returns_age_bands() -> None:
    s = pd.Series(["1990-01-01", "", None, "2010-06-01"])
    out = generalise_dob(s, reference_year=2026)
    assert out.iloc[0] in {"25-34", "35-49"}
    assert out.iloc[1] == ""
    assert out.iloc[2] == ""


def test_generalise_gps_rounds() -> None:
    s = pd.Series([-15.123456, 28.987654])
    out = generalise_gps(s, decimals=2)
    assert out.iloc[0] == round(-15.123456, 2)


def test_generalise_date_to_month() -> None:
    s = pd.Series(["2026-03-15", "bad"])
    out = generalise_date_to_month(s)
    assert out.iloc[0] == "2026-03"
    assert out.iloc[1] == ""


def test_drop_free_text_clears() -> None:
    s = pd.Series(["something sensitive", "another"])
    out = drop_free_text(s)
    assert (out == "").all()


def test_admin_lookup_resolves_district_to_province() -> None:
    assert lookup_admin_area("Kabwe") == "Central"
    assert lookup_admin_area("Lusaka") == "Lusaka"
    assert lookup_admin_area("Nowhere") == ""


# ---- suppression ------------------------------------------------------------


def test_suppress_series_preserves_zero_and_large() -> None:
    s = pd.Series([0, 1, 4, 5, 20])
    out = suppress_series(s, threshold=5)
    assert out.iloc[0] == 0
    assert out.iloc[1] == "<5"
    assert out.iloc[2] == "<5"
    assert out.iloc[3] == 5
    assert out.iloc[4] == 20


def test_suppress_table_applies_secondary() -> None:
    df = pd.DataFrame(
        {
            "province": ["Central", "Lusaka"],
            "female": [3, 20],
            "male": [20, 30],
        }
    )
    result = suppress_table(df, count_cols=["female", "male"], threshold=5)
    row0 = result.table.iloc[0]
    assert row0["female"] == "<5"
    # Secondary suppression masks the next smallest cell (male=20).
    assert row0["male"] == "<5"
    assert result.suppressed_cells >= 2


# ---- protect_dataframe end-to-end ------------------------------------------


def test_protect_dataframe_pseudonymises_and_generalises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    key = write_key(tmp_path / "linga.key")
    df = generate_round("baseline", SyntheticOptions(rows_per_round=30, seed=11))
    protected, manifest_json = protect_dataframe(df, key=key)
    manifest = json.loads(manifest_json)
    treatments = {col["name"]: col["treatment"] for col in manifest["columns"]}

    # NRC / phone / name columns must have been pseudonymised.
    assert "pseudonymised" in treatments.get("nrc", "")
    assert "pseudonymised" in treatments.get("phone", "")
    # GPS lat/lon rounded.
    assert "GPS" in treatments.get("gps_lat", "")
    # DOB generalised.
    assert "age band" in treatments.get("dob", "")
    # Address text dropped.
    assert "cleared" in treatments.get("address_text", "")
    # No raw NRC should survive in the protected frame.
    for value in protected["nrc"].astype(str):
        assert value.count("/") != 2 or not value.replace("/", "").isdigit()


def test_protect_manifest_never_contains_raw_values(tmp_path) -> None:  # type: ignore[no-untyped-def]
    key = write_key(tmp_path / "linga.key")
    df = pd.DataFrame(
        {
            "nrc": ["123456/78/1", "234567/89/2"],
            "phone": ["0977123456", "0966112233"],
            "respondent_name": ["Alice Mwale", "Bob Banda"],
            "notes": ["sensitive note", "another"],
        }
    )
    _, manifest_json = protect_dataframe(df, key=key)
    for raw in ["123456/78/1", "0977123456", "Alice Mwale", "sensitive note"]:
        assert raw not in manifest_json


def test_email_regex_sanity() -> None:
    assert EMAIL_RE.search("contact alice@example.com today")
    assert not EMAIL_RE.search("nope")


def test_normalise_phone_strips_punctuation() -> None:
    assert normalise_phone("(097) 712-3456") == "0977123456"


def test_patterns_do_not_crash_on_non_strings() -> None:
    assert not matches_phone("")
    with pytest.raises(TypeError):
        normalise_phone(None)  # type: ignore[arg-type]
