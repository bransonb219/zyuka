"""Phase 4 — local data warehouse for per-round snapshots.

Each :func:`save_snapshot` call appends a compact JSON record describing
the shape of a cleaned round: counts, per-column profile, correlations
and (if available) indicator values. :func:`compare_snapshots` reads
back the stored snapshots and surfaces drift between rounds so the HTML
report can show *what changed* in the data between baseline, midline
and endline — not only at the indicator level.
"""

from __future__ import annotations

from zyuka.warehouse.snapshot import (
    Snapshot,
    SnapshotComparison,
    build_snapshot,
    compare_snapshots,
    load_snapshots,
    save_snapshot,
)

__all__ = [
    "Snapshot",
    "SnapshotComparison",
    "build_snapshot",
    "compare_snapshots",
    "load_snapshots",
    "save_snapshot",
]
