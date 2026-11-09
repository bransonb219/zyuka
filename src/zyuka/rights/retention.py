"""Retention policy: list and purge files older than the configured window.

The retention window lives in ``zyuka.yml`` (``retention_days``). "Older
than" is measured against each file's modification time, not its contents,
because the toolkit never reads PII just to age it.

:func:`purge_expired` only unlinks files inside the project's ``outputs``
and ``data`` directories as a defensive guard against a mistaken path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from zyuka.config import load_zyuka_config
from zyuka.errors import ZyukaError
from zyuka.security.audit import write_entry


@dataclass
class ExpiredFile:
    path: Path
    age_days: int


def _retention_days(project_dir: Path) -> int:
    cfg_path = Path(project_dir) / "zyuka.yml"
    if not cfg_path.exists():
        raise ZyukaError(
            "No zyuka.yml found in the project directory.",
            suggest="Run `zyuka init` first.",
        )
    return load_zyuka_config(cfg_path).retention_days


def list_expired(project_dir: Path, data_dir: Path) -> list[ExpiredFile]:
    """Return every regular file under ``data_dir`` older than retention."""

    days = _retention_days(project_dir)
    cutoff = datetime.now(UTC) - timedelta(days=days)
    out: list[ExpiredFile] = []
    for path in sorted(Path(data_dir).rglob("*")):
        if not path.is_file():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if mtime < cutoff:
            age = (datetime.now(UTC) - mtime).days
            out.append(ExpiredFile(path=path, age_days=age))
    return out


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def purge_expired(project_dir: Path, files: list[Path]) -> list[Path]:
    """Delete ``files`` after confirming each lives inside the project."""

    project_dir = Path(project_dir).resolve()
    audit_log = project_dir / ".zyuka" / "audit.jsonl"
    removed: list[Path] = []
    for path in files:
        if not _is_inside(path, project_dir):
            raise ZyukaError(
                f"Refusing to delete file outside the project: {path}",
                suggest="Move the project directory or narrow --data.",
            )
        if path.exists():
            path.unlink()
            removed.append(path)
    if removed:
        write_entry(
            audit_log,
            command="retention.purge",
            inputs=removed,
            outputs=[],
            rows=None,
            columns=None,
            settings={"count": len(removed)},
        )
    return removed
