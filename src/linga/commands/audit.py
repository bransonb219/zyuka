"""`linga audit …` — show and verify the hash-chained audit trail."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def show(
    log_path: Annotated[Path, typer.Argument(help="Audit JSONL file.")],
    last: Annotated[int, typer.Option("--last", help="Show last N entries.")] = 20,
) -> None:
    """Pretty-print the last ``--last`` audit entries."""

    from linga.security.audit import read_audit

    entries = read_audit(log_path)
    tail = entries[-last:]

    table = Table(title=f"Audit — {log_path.name}")
    table.add_column("Timestamp")
    table.add_column("Command")
    table.add_column("Rows", justify="right")
    for entry in tail:
        table.add_row(entry["timestamp"], entry["command"], str(entry.get("rows", "")))
    console.print(table)


def verify(
    log_path: Annotated[Path, typer.Argument(help="Audit JSONL file.")],
) -> None:
    """Verify the hash chain is intact."""

    from linga.security.audit import verify_audit

    ok, bad_index = verify_audit(log_path)
    if ok:
        console.print("[green]Audit chain verified.[/green]")
    else:
        console.print(f"[red]Audit tamper detected at entry {bad_index}.[/red]")
        raise typer.Exit(code=1)
