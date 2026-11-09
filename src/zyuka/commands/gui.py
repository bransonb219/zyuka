"""`zyuka gui` — launch the local Streamlit app."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def gui(
    port: Annotated[int, typer.Option("--port", help="localhost port.")] = 8501,
) -> None:
    """Start the Streamlit GUI on localhost only."""

    from streamlit.web import cli as stcli

    app_path = Path(__file__).resolve().parent.parent / "gui" / "app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    console.print(f"[green]Starting GUI on http://127.0.0.1:{port}[/green]")
    sys.exit(stcli.main())
