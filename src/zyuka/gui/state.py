"""Shared session-state helpers for the Streamlit GUI.

Every page imports ``ensure_state`` at the top so there is one source of
truth for the project directory, the currently uploaded dataset and the
selected round. This fixes the UX bug where each page prompted for a
project directory independently and defaulted to ``Path.cwd()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import streamlit as st


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved paths derived from a project directory."""

    root: Path
    config: Path
    logframe: Path
    audit_log: Path
    data_dir: Path
    outputs_dir: Path
    protected_dir: Path
    report_html: Path
    report_excel: Path

    @classmethod
    def from_root(cls, root: Path) -> ProjectPaths:
        outputs = root / "outputs"
        return cls(
            root=root,
            config=root / "zyuka.yml",
            logframe=root / "logframe.yml",
            audit_log=root / ".zyuka" / "audit.jsonl",
            data_dir=root / "data",
            outputs_dir=outputs,
            protected_dir=outputs / "protected",
            report_html=outputs / "report" / "report.html",
            report_excel=outputs / "report" / "iptt.xlsx",
        )


def _find_zyuka_project(start: Path) -> Path | None:
    """Walk upward from ``start`` looking for a directory with ``zyuka.yml``.

    Also looks one level down so launching the GUI from a parent folder (as
    the dogfood script does) still finds the demo or init-test subproject.
    Returns the first match or ``None``.
    """

    start = start.expanduser().resolve()

    for ancestor in [start, *start.parents]:
        if (ancestor / "zyuka.yml").exists():
            return ancestor

    if start.is_dir():
        for child in sorted(start.iterdir()):
            if child.is_dir() and (child / "zyuka.yml").exists():
                return child.resolve()

    return None


def ensure_state() -> ProjectPaths:
    """Initialise session state once and return the current :class:`ProjectPaths`.

    Idempotent — safe to call at the top of every page. The project directory
    is auto-detected on first load from the launch cwd; the user can override
    it from the sidebar at any time.
    """

    if "project_dir" not in st.session_state:
        detected = _find_zyuka_project(Path.cwd())
        st.session_state["project_dir"] = str(detected) if detected else str(Path.cwd())

    if "round_name" not in st.session_state:
        st.session_state["round_name"] = "baseline"

    if "uploaded_df" not in st.session_state:
        st.session_state["uploaded_df"] = None

    if "uploaded_name" not in st.session_state:
        st.session_state["uploaded_name"] = None

    return ProjectPaths.from_root(Path(st.session_state["project_dir"]).expanduser())


def set_project_dir(path: str | Path) -> None:
    """Update the shared project directory and clear cached uploads."""

    new_root = str(Path(path).expanduser())
    if st.session_state.get("project_dir") != new_root:
        st.session_state["project_dir"] = new_root
        st.session_state["uploaded_df"] = None
        st.session_state["uploaded_name"] = None
