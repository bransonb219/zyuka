"""`zyuka compute` — indicator engine."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def compute(
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    rounds_dir: Annotated[
        Path,
        typer.Option("--rounds-dir", help="Directory with one protected CSV per round."),
    ] = Path("outputs/protected"),
    out: Annotated[
        Path | None, typer.Option("--out", help="Write indicator results JSON here.")
    ] = None,
) -> None:
    """Compute indicators across every round present under ``--rounds-dir``."""

    from zyuka.indicators.pipeline import compute_project_indicators

    results = compute_project_indicators(project_dir=project, rounds_dir=rounds_dir)

    out = out or (project / "outputs" / "indicator_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(results.to_json(), encoding="utf-8")
    console.print(f"[green]Wrote[/green] {out}")
