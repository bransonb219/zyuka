"""Tests for linga.security.*."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from linga.errors import SecurityError
from linga.security.audit import read_audit, verify_audit, write_entry
from linga.security.crypto import decrypt_bytes, decrypt_file, encrypt_bytes, encrypt_file
from linga.security.keys import (
    Key,
    generate_key,
    load_key,
    rotate_key,
    verify_fingerprint,
    write_key,
)
from linga.security.sanitize import (
    DANGEROUS_PREFIXES,
    check_file_size,
    check_safe_extension,
    sanitise_cell,
    sanitise_dataframe,
)

# ---- keys -------------------------------------------------------------------


def test_write_and_load_plain_key(tmp_path: Path) -> None:
    path = tmp_path / "linga.key"
    key = write_key(path)
    loaded = load_key(path)
    assert loaded.material == key.material
    assert loaded.fingerprint == key.fingerprint


def test_generate_key_with_password_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "wrapped.key"
    key = generate_key(path, password="correct-horse-battery-staple")
    loaded = load_key(path, password="correct-horse-battery-staple")
    assert loaded.material == key.material


def test_generate_key_refuses_to_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "k.key"
    generate_key(path)
    with pytest.raises(SecurityError):
        generate_key(path)


def test_wrong_password_raises(tmp_path: Path) -> None:
    path = tmp_path / "w.key"
    generate_key(path, password="right")
    with pytest.raises(SecurityError):
        load_key(path, password="wrong")


def test_verify_fingerprint() -> None:
    key = Key(material=b"\x01" * 32, fingerprint="deadbeefdeadbeef")
    assert verify_fingerprint(key, "deadbeefdeadbeef")
    assert not verify_fingerprint(key, "0" * 16)


def test_rotate_key_rewrites_csv_and_writes_manifest(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    df = pd.DataFrame({"pid_seed": ["P0001", "P0002"], "phone": ["0977123456", "0966112233"]})
    df.to_csv(data_dir / "round1.csv", index=False)

    old = tmp_path / "old.key"
    new = tmp_path / "new.key"
    generate_key(old)
    manifest_path = rotate_key(old, new, data_dir)

    manifest = json.loads(manifest_path.read_text())
    assert manifest["old_fingerprint"] != manifest["new_fingerprint"]
    rewritten = pd.read_csv(data_dir / "round1.csv")
    assert set(rewritten["pid_seed"]) != {"P0001", "P0002"}


# ---- crypto -----------------------------------------------------------------


def test_encrypt_decrypt_round_trip(tmp_path: Path) -> None:
    key = write_key(tmp_path / "k.key")
    plain = b"something sensitive" * 100
    blob = encrypt_bytes(plain, key)
    assert blob[:6] == b"LINGA\x01"
    assert decrypt_bytes(blob, key) == plain


def test_decrypt_with_wrong_key_fails(tmp_path: Path) -> None:
    k1 = write_key(tmp_path / "k1.key")
    k2 = write_key(tmp_path / "k2.key")
    blob = encrypt_bytes(b"secret", k1)
    with pytest.raises(SecurityError):
        decrypt_bytes(blob, k2)


def test_decrypt_rejects_non_linga_blob(tmp_path: Path) -> None:
    key = write_key(tmp_path / "k.key")
    with pytest.raises(SecurityError):
        decrypt_bytes(b"not linga", key)


def test_encrypt_file_round_trip(tmp_path: Path) -> None:
    key = write_key(tmp_path / "k.key")
    src = tmp_path / "in.csv"
    enc = tmp_path / "out.enc"
    dec = tmp_path / "out.csv"
    src.write_text("a,b\n1,2\n")
    encrypt_file(src, enc, key)
    decrypt_file(enc, dec, key)
    assert dec.read_text() == "a,b\n1,2\n"


# ---- sanitize ---------------------------------------------------------------


def test_sanitise_cell_prefixes_formula_cells() -> None:
    for prefix in DANGEROUS_PREFIXES:
        assert sanitise_cell(prefix + "SUM(A1:A2)") == "'" + prefix + "SUM(A1:A2)"


def test_sanitise_cell_passes_safe_values() -> None:
    assert sanitise_cell("hello") == "hello"
    assert sanitise_cell("") == ""
    assert sanitise_cell(42) == 42
    assert sanitise_cell(None) is None


def test_sanitise_dataframe_applies_only_to_strings() -> None:
    df = pd.DataFrame({"a": ["=BAD()", "fine", "+1"], "b": [1, 2, 3]})
    out = sanitise_dataframe(df)
    assert out["a"].tolist() == ["'=BAD()", "fine", "'+1"]
    assert out["b"].tolist() == [1, 2, 3]


def test_check_file_size_rejects_oversize(tmp_path: Path) -> None:
    f = tmp_path / "big.csv"
    f.write_bytes(b"x" * 1024)
    with pytest.raises(SecurityError):
        check_file_size(f, max_bytes=512)


def test_check_safe_extension_rejects_macros(tmp_path: Path) -> None:
    with pytest.raises(SecurityError):
        check_safe_extension(tmp_path / "evil.xlsm")
    check_safe_extension(tmp_path / "safe.xlsx")


# ---- audit ------------------------------------------------------------------


def test_audit_chain_single_entry(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    write_entry(log, command="check", rows=10, columns=5)
    ok, bad = verify_audit(log)
    assert ok
    assert bad is None


def test_audit_chain_many_entries(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    for i in range(5):
        write_entry(log, command=f"cmd-{i}")
    entries = read_audit(log)
    assert len(entries) == 5
    assert entries[0]["prev"] == "0" * 64
    for i in range(1, 5):
        assert entries[i]["prev"] == entries[i - 1]["hash"]
    ok, _ = verify_audit(log)
    assert ok


def test_audit_detects_tampering(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    write_entry(log, command="a")
    write_entry(log, command="b")
    write_entry(log, command="c")
    text = log.read_text().splitlines()
    tampered = json.loads(text[1])
    tampered["command"] = "MODIFIED"
    text[1] = json.dumps(tampered)
    log.write_text("\n".join(text) + "\n")

    ok, bad_index = verify_audit(log)
    assert not ok
    assert bad_index == 1


def test_audit_hashes_referenced_files(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    entry = write_entry(log, command="scan", inputs=[f])
    assert entry["inputs"][0]["sha256"]
    assert entry["inputs"][0]["path"].endswith("data.csv")
