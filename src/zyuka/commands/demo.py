"""`zyuka demo` — synthetic end-to-end run."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def demo(
    out_dir: Annotated[Path, typer.Option("--out", help="Output directory.")] = Path("zyuka-demo"),
    open_report: Annotated[bool, typer.Option("--open", help="Open the HTML report.")] = False,
) -> None:
    """Generate synthetic data and run the full pipeline into ``--out``."""

    from zyuka.demo import run_demo

    report_path = run_demo(out_dir=out_dir, open_report=open_report)
    console.print(f"[green]Demo complete.[/green] Report: {report_path}")
