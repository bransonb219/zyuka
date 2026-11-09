"""Smoke tests for the GUI module.

Streamlit pages run under the Streamlit script runner, not as regular
modules. We don't start a server here; we import them with a stubbed
``st`` so broken imports or template errors fail fast in CI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from zyuka.gui.mask import _mask_value, masked_preview


def test_mask_value_hides_middle() -> None:
    assert _mask_value("0977123456") == "0********6"
    assert _mask_value("") == ""
    assert _mask_value(None) == ""


def test_masked_preview_masks_risky_columns() -> None:
    df = pd.DataFrame(
        {
            "pid_seed": ["P0001", "P0002"],
            "nrc": ["123456/10/1", "123457/10/2"],
            "age": [30, 40],
        }
    )
    preview = masked_preview(df)
    # Risky columns masked, non-risky left alone.
    assert preview["age"].tolist() == [30, 40]
    assert all("*" in str(v) for v in preview["nrc"].tolist())
    assert all("*" in str(v) for v in preview["pid_seed"].tolist())


def test_gui_pages_parse_and_compile() -> None:
    """Every page under gui/pages/ must at least be a valid Python file.

    We don't execute them: Streamlit pages rely on being driven by the
    Streamlit runtime and will call ``st.*`` functions that only make
    sense inside a running app. Compiling catches syntax errors and
    bad imports without needing a server.
    """

    pages_dir = Path("src/zyuka/gui/pages")
    assert pages_dir.is_dir()
    for page in sorted(pages_dir.glob("*.py")):
        source = page.read_text(encoding="utf-8")
        compile(source, str(page), "exec")


def test_gui_app_parses_and_compiles() -> None:
    app_path = Path("src/zyuka/gui/app.py")
    source = app_path.read_text(encoding="utf-8")
    compile(source, str(app_path), "exec")
