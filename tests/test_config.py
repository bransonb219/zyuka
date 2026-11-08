"""Tests for linga.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from linga.config import load_linga_config, load_logframe
from linga.errors import ConfigError


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_load_linga_config_happy_path(tmp_path: Path) -> None:
    yml = _write(
        tmp_path / "linga.yml",
        """
organisation: Example NGO
programme: Test
data_controller_contact: dpo@example.org
retention_days: 365
key_path: /tmp/example.key
""".strip(),
    )
    cfg = load_linga_config(yml)
    assert cfg.organisation == "Example NGO"
    assert cfg.retention_days == 365
    assert cfg.protection.small_cell_threshold == 5


def test_load_linga_config_blank_field_rejected(tmp_path: Path) -> None:
    yml = _write(
        tmp_path / "linga.yml",
        """
organisation: ""
programme: Test
data_controller_contact: dpo@example.org
key_path: /tmp/example.key
""".strip(),
    )
    with pytest.raises(ConfigError):
        load_linga_config(yml)


def test_load_linga_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_linga_config(tmp_path / "nope.yml")
    assert "not found" in exc.value.message
    assert exc.value.suggest  # has a plain-language suggestion


def test_load_logframe_happy_path(tmp_path: Path) -> None:
    yml = _write(
        tmp_path / "logframe.yml",
        """
goal: "Test goal"
outcomes:
  - code: OC1
    name: Outcome 1
    indicators:
      - code: OC1.1
        name: "Example"
        type: proportion
        numerator: "a == 'yes'"
        denominator: "a != ''"
        disaggregations: [sex]
""".strip(),
    )
    lf = load_logframe(yml)
    assert lf.goal == "Test goal"
    assert len(lf.all_indicators()) == 1
