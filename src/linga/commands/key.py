"""`linga key …` — key lifecycle commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def generate(
    key_path: Annotated[Path, typer.Argument(help="Where to write the new key.")],
    password: Annotated[
        str | None,
        typer.Option(
            "--password",
            prompt=False,
            hide_input=True,
            help="Optional password (wraps the key with scrypt).",
        ),
    ] = None,
) -> None:
    """Generate a new 32-byte key."""

    from linga.security.keys import generate_key

    generate_key(key_path, password=password)
    console.print(f"[green]Key written:[/green] {key_path}")
    console.print("[yellow]Back this file up out of band. Never commit it.[/yellow]")


def rotate(
    old_key_path: Annotated[Path, typer.Argument(help="Current key.")],
    new_key_path: Annotated[Path, typer.Argument(help="New key to generate.")],
    data_dir: Annotated[Path, typer.Option("--data", help="Dir of pseudonymised CSVs.")],
    password: Annotated[str | None, typer.Option("--password")] = None,
) -> None:
    """Rotate: generate a new key and re-pseudonymise ``data_dir``."""

    from linga.security.keys import rotate_key

    manifest = rotate_key(old_key_path, new_key_path, data_dir, password=password)
    console.print(f"[green]Rotated.[/green] Mapping manifest: {manifest}")


def verify(
    key_path: Annotated[Path, typer.Argument(help="Key file to verify.")],
    fingerprint: Annotated[str, typer.Argument(help="Expected fingerprint.")],
    password: Annotated[str | None, typer.Option("--password")] = None,
) -> None:
    """Verify that ``key_path`` matches a previously-recorded fingerprint."""

    from linga.security.keys import load_key, verify_fingerprint

    key = load_key(key_path, password=password)
    ok = verify_fingerprint(key, fingerprint)
    if ok:
        console.print("[green]Key matches.[/green]")
    else:
        console.print("[red]Key does NOT match.[/red]")
        raise typer.Exit(code=1)
