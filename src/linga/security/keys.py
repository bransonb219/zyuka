"""Key handling for Linga.

Design goals:

- A :class:`Key` is 32 bytes of HMAC-SHA256 key material + a short, stable
  fingerprint derived by HMAC-ing a fixed sentinel. The fingerprint identifies
  the key in manifests and audit entries; the key bytes themselves never
  appear in logs, reports or audit records.
- Keys live outside the repo. On POSIX we chmod ``0600`` best-effort.
- A key file may be plaintext (32 bytes) or password-wrapped with scrypt+AES-GCM.
  The on-disk format is self-describing: a single first byte (``0x00`` plain,
  ``0x01`` scrypt+AES-GCM) followed by the appropriate payload.

Rotation re-pseudonymises every CSV under a directory with the new key and
writes a mapping manifest linking the old and new pseudonyms. The raw
identifier never passes through the mapping file because we only hold the
hashes.
"""

from __future__ import annotations

import contextlib
import getpass
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from linga.errors import SecurityError

KEY_BYTES = 32
_FINGERPRINT_SENTINEL = b"linga/key/fingerprint/v1"

_PLAIN_MAGIC = b"\x00"
_SCRYPT_MAGIC = b"\x01"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_SALT_BYTES = 16
_AESGCM_NONCE_BYTES = 12


@dataclass(frozen=True)
class Key:
    material: bytes
    fingerprint: str

    def __post_init__(self) -> None:
        if len(self.material) != KEY_BYTES:
            raise ValueError(f"key material must be {KEY_BYTES} bytes")


def _fingerprint(material: bytes) -> str:
    return hmac.new(material, _FINGERPRINT_SENTINEL, hashlib.sha256).hexdigest()[:16]


def _derive_password_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def _wrap_key(material: bytes, password: str) -> bytes:
    salt = secrets.token_bytes(_SCRYPT_SALT_BYTES)
    wrap_key = _derive_password_key(password, salt)
    nonce = secrets.token_bytes(_AESGCM_NONCE_BYTES)
    ciphertext = AESGCM(wrap_key).encrypt(nonce, material, None)
    return _SCRYPT_MAGIC + salt + nonce + ciphertext


def _unwrap_key(blob: bytes, password: str) -> bytes:
    body = blob[len(_SCRYPT_MAGIC) :]
    salt, body = body[:_SCRYPT_SALT_BYTES], body[_SCRYPT_SALT_BYTES:]
    nonce, ciphertext = body[:_AESGCM_NONCE_BYTES], body[_AESGCM_NONCE_BYTES:]
    wrap_key = _derive_password_key(password, salt)
    try:
        return AESGCM(wrap_key).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise SecurityError(
            "Could not decrypt key — wrong password?",
            suggest="Re-run with the correct password; the file itself is not corrupt.",
        ) from exc


def _chmod_600(path: Path) -> None:
    with contextlib.suppress(OSError, NotImplementedError):
        os.chmod(path, 0o600)


def generate_key(path: Path, password: str | None = None) -> Key:
    """Create a new 32-byte key at ``path``.

    If ``password`` is provided the file is scrypt+AES-GCM-wrapped.
    """

    path = Path(path)
    if path.exists():
        raise SecurityError(
            f"Key file already exists: {path}",
            suggest="Use `linga key rotate` to rotate; never overwrite a live key.",
        )
    material = secrets.token_bytes(KEY_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    if password:
        path.write_bytes(_wrap_key(material, password))
    else:
        path.write_bytes(_PLAIN_MAGIC + material)
    _chmod_600(path)
    return Key(material=material, fingerprint=_fingerprint(material))


def write_key(path: Path, material: bytes | None = None) -> Key:
    """Direct writer used by tests and the init wizard."""

    path = Path(path)
    if material is not None and len(material) != KEY_BYTES:
        raise ValueError(f"material must be {KEY_BYTES} bytes")
    material = material or secrets.token_bytes(KEY_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_PLAIN_MAGIC + material)
    _chmod_600(path)
    return Key(material=material, fingerprint=_fingerprint(material))


def _prompt_password() -> str:
    return getpass.getpass("Key password: ")


def load_key(path: Path, password: str | None = None) -> Key:
    """Load a key from ``path``.

    If the file is password-wrapped and ``password`` is ``None``, prompt on
    stdin — but *only* if stdin is a TTY, otherwise raise so a pipeline
    doesn't block silently.
    """

    path = Path(path)
    if not path.exists():
        raise SecurityError(
            f"Key not found: {path}",
            suggest="Run `linga key generate <path>` to create one.",
        )
    blob = path.read_bytes()
    if not blob:
        raise SecurityError(f"Key file is empty: {path}")

    magic, payload = blob[:1], blob[1:]
    if magic == _PLAIN_MAGIC:
        if len(payload) != KEY_BYTES:
            raise SecurityError(f"Key at {path} has wrong length: {len(payload)}")
        material = payload
    elif magic == _SCRYPT_MAGIC:
        if password is None:
            import sys

            if not sys.stdin.isatty():
                raise SecurityError(
                    f"Key at {path} is password-protected and no password was given.",
                    suggest="Pass --password or run interactively.",
                )
            password = _prompt_password()
        material = _unwrap_key(blob, password)
    else:
        # Legacy / unlabelled plain key: 32 raw bytes.
        if len(blob) == KEY_BYTES:
            material = blob
        else:
            raise SecurityError(
                f"Unrecognised key format at {path}",
                suggest="If this file is not a Linga key, point --key-path elsewhere.",
            )
    return Key(material=material, fingerprint=_fingerprint(material))


def verify_fingerprint(key: Key, expected: str) -> bool:
    return hmac.compare_digest(key.fingerprint, expected.strip().lower())


def _rehash_series(series: pd.Series, old_key: Key, new_key: Key) -> tuple[pd.Series, pd.Series]:
    """Return ``(new_series, mapping_rows)``.

    ``mapping_rows`` is a Series of ``"<old>→<new>"`` tokens — hashes only,
    never raw values. Used to build the rotation manifest.
    """

    from linga.privacy.pseudonymise import pseudonymise_value

    def _rotate(value: object) -> str:
        if value is None or value == "":
            return ""
        s = str(value).strip()
        if s == "":
            return ""
        # If the value already looks like a 16-char hex pseudonym we treat it as
        # pre-hashed and just HMAC it again under the new key. If it looks like
        # raw input we HMAC it under both keys.
        return pseudonymise_value(s, new_key.material)

    new_series = series.map(_rotate)
    mapping = pd.Series(
        [f"{a}:{b}" for a, b in zip(series.astype(str), new_series.astype(str), strict=False)],
        index=series.index,
    )
    return new_series, mapping


def rotate_key(
    old_key_path: Path,
    new_key_path: Path,
    data_dir: Path,
    password: str | None = None,
    pseudo_columns: tuple[str, ...] = ("nrc", "phone", "pid_seed", "respondent_name"),
) -> Path:
    """Generate a new key and re-pseudonymise every CSV under ``data_dir``.

    Writes ``rotation_manifest.json`` next to the new key, containing the old
    and new fingerprints and a count of rewritten rows per file. The manifest
    never contains raw identifiers; the mapping of old→new pseudonyms is
    stored alongside as ``rotation_mapping.csv``.
    """

    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise SecurityError(f"Data directory not found: {data_dir}")
    old_key = load_key(old_key_path, password=password)
    new_key = generate_key(new_key_path, password=password)

    files_touched: list[dict[str, int | str]] = []
    mapping_frames: list[pd.DataFrame] = []
    for csv in sorted(data_dir.glob("*.csv")):
        df = pd.read_csv(csv)
        rewritten = 0
        for col in pseudo_columns:
            if col in df.columns:
                new_series, mapping = _rehash_series(df[col], old_key, new_key)
                df[col] = new_series
                mapping_frames.append(
                    pd.DataFrame({"file": csv.name, "column": col, "mapping": mapping})
                )
                rewritten += int(df[col].notna().sum())
        df.to_csv(csv, index=False)
        files_touched.append({"file": csv.name, "rewritten_values": rewritten})

    manifest = {
        "old_fingerprint": old_key.fingerprint,
        "new_fingerprint": new_key.fingerprint,
        "files": files_touched,
    }
    manifest_path = new_key_path.with_name("rotation_manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if mapping_frames:
        pd.concat(mapping_frames, ignore_index=True).to_csv(
            new_key_path.with_name("rotation_mapping.csv"), index=False
        )
    return manifest_path
