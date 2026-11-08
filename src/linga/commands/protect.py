"""`linga protect` — pseudonymise, minimise, generalise, and write manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def protect(
    data: Annotated[Path, typer.Argument(help="Input CSV / XLSX.")],
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    out: Annotated[Path | None, typer.Option("--out", help="Output CSV path.")] = None,
) -> None:
    """Apply protection rules and write a protected dataset + manifest."""

    from linga.ingest.rounds import read_table
    from linga.pipeline_support import protect_dataframe

    df = read_table(data)
    protected, manifest = protect_dataframe(df, project_dir=project)

    out = out or (data.parent / f"protected_{data.stem}.csv")
    protected.to_csv(out, index=False)
    (out.with_suffix(".manifest.json")).write_text(manifest, encoding="utf-8")
    console.print(f"[green]Wrote[/green] {out}")
