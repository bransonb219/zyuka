"""Inline-chart rendering for the HTML report.

Reports must be self-contained HTML — no CDN, no external images. We draw
each chart with matplotlib, write it to an in-memory SVG buffer and base64-
encode it so it can be embedded directly in an ``<img src="data:image/svg...">``
tag.

Every chart function returns the base64 data URI as a string. If matplotlib
is unavailable (e.g. headless install without a backend), the functions
return an empty string so the Jinja template can degrade gracefully.
"""

from __future__ import annotations

import base64
import io
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


def _svg_data_uri(fig: plt.Figure) -> str:  # type: ignore[name-defined]
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def trend_chart(
    indicator_name: str,
    rounds: list[str],
    values: list[float | int | None],
    targets: list[float | None] | None = None,
) -> str:
    """Trend line of indicator values across rounds."""

    fig, ax = plt.subplots(figsize=(6, 3.2))
    y = [v if v is not None else 0 for v in values]
    ax.plot(rounds, y, marker="o", label="Actual")
    if targets:
        y_t = [t if t is not None else 0 for t in targets]
        ax.plot(rounds, y_t, marker="x", linestyle="--", label="Target")
    ax.set_title(indicator_name)
    ax.set_ylabel("Value")
    ax.set_xlabel("Round")
    ax.legend(loc="best")
    ax.grid(True, linestyle=":", alpha=0.4)
    return _svg_data_uri(fig)


def disaggregation_chart(
    indicator_name: str,
    column: str,
    mapping: dict[str, Any],
) -> str:
    """Horizontal bar chart for one disaggregation column."""

    labels = list(mapping.keys())
    numeric: list[float] = []
    for value in mapping.values():
        v = value.get("value") if isinstance(value, dict) else None
        numeric.append(float(v) if v is not None else 0.0)

    fig, ax = plt.subplots(figsize=(6, max(2.0, 0.4 * len(labels))))
    ax.barh(labels, numeric)
    ax.set_title(f"{indicator_name} by {column}")
    ax.set_xlabel("Value")
    ax.invert_yaxis()
    return _svg_data_uri(fig)
