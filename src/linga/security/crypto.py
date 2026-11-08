"""AES-GCM file encryption for Linga outputs.

File layout (one file = one GCM stream):

    magic     : 6 bytes  ``LINGA\\x01``
    nonce     : 12 bytes random
    ciphertext: n bytes
    tag       : 16 bytes (appended by AESGCM)

A key is a 32-byte value sourced from :mod:`linga.security.keys`. We use the
same key for both HMAC pseudonymisation and AES-GCM encryption — this is safe
because they derive different cryptographic properties from the same secret,
and operationally it means one key file per project rather than two the user
has to look after.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from linga.errors import SecurityError
from linga.security.keys import Key

MAGIC = b"LINGA\x01"
NONCE_BYTES = 12
MAX_PLAINTEXT_BYTES = 200 * 1024 * 1024  # 200 MB safety cap on in-memory encrypts


def encrypt_bytes(plaintext: bytes, key: Key) -> bytes:
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise SecurityError(
            f"File too large to encrypt in memory: {len(plaintext):,} bytes",
            suggest=f"Keep inputs under {MAX_PLAINTEXT_BYTES // (1024 * 1024)} MB.",
        )
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(key.material).encrypt(nonce, plaintext, None)
    return MAGIC + nonce + ciphertext


def decrypt_bytes(blob: bytes, key: Key) -> bytes:
    if not blob.startswith(MAGIC):
        raise SecurityError(
            "Not a Linga-encrypted file (missing magic header).",
            suggest="Confirm the file was produced by `linga` and not another tool.",
        )
    body = blob[len(MAGIC) :]
    nonce, ciphertext = body[:NONCE_BYTES], body[NONCE_BYTES:]
    try:
        return AESGCM(key.material).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise SecurityError(
            "Could not decrypt — the file is corrupt or the key is wrong.",
            suggest="Verify the key fingerprint matches the one in the manifest.",
        ) from exc


def encrypt_file(in_path: Path, out_path: Path, key: Key) -> Path:
    data = Path(in_path).read_bytes()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(encrypt_bytes(data, key))
    return out_path


def decrypt_file(in_path: Path, out_path: Path, key: Key) -> Path:
    data = Path(in_path).read_bytes()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(decrypt_bytes(data, key))
    return out_path
