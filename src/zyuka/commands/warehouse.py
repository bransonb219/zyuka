"""`zyuka warehouse` — inspect per-round snapshots.

Three sub-commands:

* ``zyuka warehouse list`` — show which rounds are stored
* ``zyuka warehouse show <round>`` — dump a single snapshot
* ``zyuka warehouse compare`` — print the cross-round drift tables

Snapshots live under ``<project>/outputs/warehouse/`` and are written by
the main pipeline (``zyuka run``). No raw data leaves the warehouse —
only counts, column-level moments and hashes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from zyuka.warehouse.snapshot import compare_snapshots, load_snapshots

console = Console()
warehouse_app = typer.Typer(help="Browse the local round-by-round snapshot warehouse.")


def _warehouse_dir(project: Path) -> Path:
    return project / "outputs" / "warehouse"


@warehouse_app.command("list")
def warehouse_list(
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
) -> None:
    """Show stored snapshots in generation order."""

    snaps = load_snapshots(_warehouse_dir(project))
    if not snaps:
        console.print("[yellow]No snapshots stored yet.[/yellow] Run `zyuka run` first.")
        return
    table = Table(title="Warehouse snapshots")
    table.add_column("Round")
    table.add_column("Generated", justify="right")
    table.add_column("Rows", justify="right")
    table.add_column("Cols", justify="right")
    table.add_column("Zyuka", justify="right")
    for snap in snaps:
        table.add_row(
            snap.round_name,
            snap.generated_at,
            f"{snap.n_rows:,}",
            str(snap.n_cols),
            snap.zyuka_version,
        )
    console.print(table)


@warehouse_app.command("show")
def warehouse_show(
    round_name: Annotated[str, typer.Argument(help="Round name to show.")],
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
) -> None:
    """Print the raw JSON snapshot for a round."""

    snaps = {s.round_name: s for s in load_snapshots(_warehouse_dir(project))}
    snap = snaps.get(round_name)
    if snap is None:
        console.print(f"[red]No snapshot stored for round[/red] {round_name!r}.")
        raise typer.Exit(code=1)
    console.print_json(data=snap.to_dict())


@warehouse_app.command("compare")
def warehouse_compare(
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Also write the comparison JSON to this path."),
    ] = None,
) -> None:
    """Diff stored snapshots and print the top drift rows."""

    snaps = load_snapshots(_warehouse_dir(project))
    if len(snaps) < 2:
        console.print("[yellow]Need at least 2 snapshots to compare.[/yellow]")
        return
    comparison = compare_snapshots(snaps)
    payload = comparison.to_dict()
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"[green]Wrote[/green] {out}")

    header = f"Rounds: {' → '.join(comparison.rounds)}"
    console.print(f"\n[bold]{header}[/bold]")

    if comparison.missingness_drift:
        table = Table(title="Missingness drift (top)")
        table.add_column("Column")
        for r in comparison.rounds:
            table.add_column(r, justify="right")
        table.add_column("Δ (pp)", justify="right")
        for row in comparison.missingness_drift:
            table.add_row(
                row["column"],
                *[
                    f"{row['missing_pct'].get(r, '—'):.1f}%"
                    if isinstance(row["missing_pct"].get(r), float)
                    else "—"
                    for r in comparison.rounds
                ],
                f"{row['delta_pct']:.1f}",
            )
        console.print(table)

    if comparison.numeric_mean_drift:
        table = Table(title="Numeric mean drift (top)")
        table.add_column("Column")
        for r in comparison.rounds:
            table.add_column(r, justify="right")
        table.add_column("Δ (mean)", justify="right")
        for row in comparison.numeric_mean_drift:
            table.add_row(
                row["column"],
                *[
                    f"{row['mean'].get(r, '—'):.2f}"
                    if isinstance(row["mean"].get(r), float)
                    else "—"
                    for r in comparison.rounds
                ],
                f"{row['delta']:+.2f}",
            )
        console.print(table)
