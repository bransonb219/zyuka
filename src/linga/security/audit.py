"""Hash-chained, append-only audit log.

Each entry is one JSON object per line (``JSONL``) with these fields:

- ``timestamp`` — ISO 8601 UTC with ``Z`` suffix.
- ``os_user`` — best-effort OS username (``getpass.getuser``).
- ``command`` — the Linga subcommand that produced the entry.
- ``inputs`` / ``outputs`` — list of ``{"path": str, "sha256": str}`` dicts.
- ``rows`` / ``columns`` — counts for visibility; never includes values.
- ``settings`` — dict of command-level options (never includes raw keys).
- ``version`` — Linga's package version.
- ``prev`` — SHA-256 of the previous entry's canonical JSON, or 64 zeros for
  the first entry.
- ``hash`` — SHA-256 of this entry's payload (every field above except
  ``hash`` itself), computed with sorted keys.

Tampering with any entry breaks the chain: :func:`verify_audit` returns the
index of the first entry whose stored ``hash`` or ``prev`` does not match a
freshly recomputed value.
"""

from __future__ import annotations

import getpass
import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from linga import __version__

GENESIS_PREV = "0" * 64


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file on disk."""

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical(entry: dict[str, Any]) -> bytes:
    return json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _entry_hash(payload: dict[str, Any]) -> str:
    return _sha256(_canonical(payload))


def read_audit(log_path: Path) -> list[dict[str, Any]]:
    """Return every entry in the audit log, or ``[]`` if the file is missing."""

    path = Path(log_path)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _last_hash(log_path: Path) -> str:
    entries = read_audit(log_path)
    if not entries:
        return GENESIS_PREV
    last = entries[-1]
    stored = last.get("hash")
    return str(stored) if stored else GENESIS_PREV


def write_entry(
    log_path: Path,
    command: str,
    inputs: Iterable[Path] = (),
    outputs: Iterable[Path] = (),
    rows: int | None = None,
    columns: int | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a new entry and return the persisted dict (including ``hash``)."""

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "os_user": _safe_user(),
        "command": command,
        "inputs": [{"path": str(p), "sha256": hash_file(p)} for p in inputs if Path(p).exists()],
        "outputs": [{"path": str(p), "sha256": hash_file(p)} for p in outputs if Path(p).exists()],
        "rows": rows,
        "columns": columns,
        "settings": settings or {},
        "version": __version__,
        "prev": _last_hash(log_path),
    }
    payload["hash"] = _entry_hash(payload)

    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")
    return payload


def verify_audit(log_path: Path) -> tuple[bool, int | None]:
    """Return ``(ok, bad_index)``. ``bad_index`` is 0-based or ``None``."""

    entries = read_audit(log_path)
    prev = GENESIS_PREV
    for i, entry in enumerate(entries):
        stored_hash = entry.get("hash")
        stored_prev = entry.get("prev")
        if stored_prev != prev:
            return False, i
        recomputed = _entry_hash({k: v for k, v in entry.items() if k != "hash"})
        if stored_hash != recomputed:
            return False, i
        prev = str(stored_hash)
    return True, None


def _safe_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"
