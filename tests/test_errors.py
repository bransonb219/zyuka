"""Tests for linga.errors."""

from __future__ import annotations

from linga.errors import ConfigError, LingaError


def test_render_with_suggest() -> None:
    e = ConfigError("Bad file", suggest="Try `linga init`.")
    rendered = e.render()
    assert "Bad file" in rendered
    assert "Try `linga init`." in rendered


def test_render_without_suggest() -> None:
    e = LingaError("Plain message")
    assert e.render() == "Plain message"
