"""Command-line entry point.

This module stays thin: every real action is defined in a dedicated module and
the CLI just wires it up. Errors inherit from :class:`linga.errors.LingaError`
and are rendered as plain language without a stack trace unless ``--debug``.
"""

from __future__ import annotations

import functools
import sys
from collections.abc import Callable
from typing import Annotated, Any, TypeVar

import typer
from rich.console import Console

from linga import __version__
from linga.errors import LingaError

F = TypeVar("F", bound=Callable[..., Any])

app = typer.Typer(
    name="linga",
    help="Privacy-first, local M&E toolkit.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"linga {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Show full tracebacks on error.")] = False,
) -> None:
    """Linga — local-first M&E toolkit."""

    if debug:
        import os

        os.environ["LINGA_DEBUG"] = "1"


def _bail(exc: LingaError) -> typer.Exit:
    err_console.print(f"[red]Error:[/red] {exc.message}")
    if exc.suggest:
        err_console.print(f"[yellow]Suggested fix:[/yellow] {exc.suggest}")
    return typer.Exit(code=1)


def _handle(func: F) -> F:
    """Decorator: render ``LingaError`` nicely and exit non-zero.

    Uses :func:`functools.wraps` so Typer's signature introspection still
    sees the original parameters when it generates the CLI options.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except LingaError as exc:
            import os

            if os.environ.get("LINGA_DEBUG"):
                raise
            raise _bail(exc) from None

    return wrapper  # type: ignore[return-value]


# Subcommands are registered from their respective modules below so each
# milestone can plug in without touching this file.
def _register_subcommands() -> None:
    # Imported lazily: avoids pulling heavy deps for `linga --version`.
    from linga.cli_commands import register

    register(app)


_register_subcommands()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
