"""Entry point for ``python -m zyuka``."""

from __future__ import annotations

from zyuka.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
