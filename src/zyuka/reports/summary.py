"""Auto-generate the executive summary from indicator results.

The summary is a short paragraph plus bullet counts, derived from the
longitudinal status of each indicator. If no targets are set we fall back to
a count-only description so the summary is never blank.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_summary(results: dict[str, Any]) -> dict[str, Any]:
    """Return ``{"paragraph": str, "counts": {"on_track": N, …}}``."""

    status_counter: Counter[str] = Counter()
    for ind in results.get("indicators", []):
        for point in ind.get("longitudinal", []):
            status = point.get("status")
            if status:
                status_counter[status] += 1

    total_rounds = len(results.get("rounds", []))
    total_indicators = len(results.get("indicators", []))

    if not status_counter:
        paragraph = (
            f"This report covers {total_indicators} indicator(s) across "
            f"{total_rounds} round(s). No targets were set, so status is "
            f"not reported."
        )
    else:
        on = status_counter.get("on_track", 0)
        at_risk = status_counter.get("at_risk", 0)
        off = status_counter.get("off_track", 0)
        paragraph = (
            f"Across {total_indicators} indicator(s) and {total_rounds} round(s): "
            f"{on} on track, {at_risk} at risk, {off} off track."
        )

    return {
        "paragraph": paragraph,
        "counts": dict(status_counter),
        "rounds": total_rounds,
        "indicators": total_indicators,
    }
