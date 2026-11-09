"""Tests for zyuka.errors."""

from __future__ import annotations

from zyuka.errors import ConfigError, ZyukaError


def test_render_with_suggest() -> None:
    e = ConfigError("Bad file", suggest="Try `zyuka init`.")
    rendered = e.render()
    assert "Bad file" in rendered
    assert "Try `zyuka init`." in rendered


def test_render_without_suggest() -> None:
    e = ZyukaError("Plain message")
    assert e.render() == "Plain message"
