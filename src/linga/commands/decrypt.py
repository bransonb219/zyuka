"""`linga decrypt` — decrypt a .enc file."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def decrypt(
    data: Annotated[Path, typer.Argument(help="Encrypted .enc file.")],
    key_path: Annotated[Path, typer.Option("--key", help="Key file.")],
    out: Annotated[Path | None, typer.Option("--out", help="Output path.")] = None,
) -> None:
    """Decrypt ``data`` using the key at ``--key``."""

    from linga.security.crypto import decrypt_file
    from linga.security.keys import load_key

    key = load_key(key_path)
    out = out or data.with_suffix("")
    decrypt_file(data, out, key)
    console.print(f"[green]Wrote[/green] {out}")
