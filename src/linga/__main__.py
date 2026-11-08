"""Entry point for ``python -m linga``."""

from __future__ import annotations

from linga.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
