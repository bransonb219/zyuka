"""Reusable Streamlit components for the Zyuka GUI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from zyuka import __version__
from zyuka.gui.state import ProjectPaths, ensure_state, set_project_dir
from zyuka.gui.theme import apply_theme


def init_page(title: str, icon: str = "") -> ProjectPaths:
    """Standard page prelude: theme + sidebar + resolved project paths.

    Pages call this exactly once before rendering their own body. Returns
    the :class:`ProjectPaths` for the currently selected project so page
    code does not have to repeat path arithmetic.
    """

    apply_theme()
    paths = ensure_state()
    render_sidebar(paths)
    heading = f"{icon} {title}".strip() if icon else title
    st.title(heading)
    return paths


def render_sidebar(paths: ProjectPaths) -> None:
    """Shared sidebar: brand, project picker, status, trust reminder."""

    sb = st.sidebar
    sb.markdown(
        '<div class="zyuka-brand">'
        '<span class="mark">◐</span>'
        '<span class="wordmark">zyuka</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    sb.caption(f"v{__version__} · local only · no telemetry")

    sb.markdown("### Project")
    current = st.session_state.get("project_dir", str(Path.cwd()))
    new_value = sb.text_input(
        "Directory",
        value=current,
        key="sidebar_project_input",
        help="Folder containing zyuka.yml. All pages read from here.",
    )
    if new_value != current:
        set_project_dir(new_value)
        st.rerun()

    _render_project_status(sb, paths)

    sb.markdown("### Round")
    rounds = ["baseline", "midline", "endline"]
    default_idx = rounds.index(st.session_state.get("round_name", "baseline"))
    picked = sb.selectbox(
        "Current round",
        options=rounds,
        index=default_idx,
        key="sidebar_round",
        help="Round label applied to uploads and shown in reports.",
    )
    st.session_state["round_name"] = picked

    sb.info(
        "Zyuka runs on your machine. Nothing is uploaded. "
        "Previews are masked — raw personal data never appears here."
    )


def _render_project_status(sb: "st.delta_generator.DeltaGenerator", paths: ProjectPaths) -> None:
    """One-glance health badges for the sidebar."""

    checks = [
        ("zyuka.yml", paths.config.exists()),
        ("logframe.yml", paths.logframe.exists()),
        ("audit log", paths.audit_log.exists()),
    ]
    for label, ok in checks:
        icon = "✓" if ok else "·"
        colour = "#0F766E" if ok else "#94A3B8"
        sb.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:2px 0;color:{colour};">'
            f"<span>{icon} {label}</span>"
            f'<span style="font-size:0.8rem">{"ready" if ok else "missing"}</span>'
            "</div>",
            unsafe_allow_html=True,
        )


def workflow_step(label: str, done: bool, hint: str) -> None:
    """Render a single workflow step card on the home dashboard."""

    state_class = "done" if done else "pending"
    status_text = "complete" if done else "not yet"
    st.markdown(
        f'<div class="zyuka-step {state_class}">'
        f'<span class="dot"></span>'
        f'<span class="label">{label}</span>'
        f'<span class="hint">{hint} · {status_text}</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str, cta: str | None = None) -> None:
    """Friendly, uniform empty-state block (Nielsen: help users recover)."""

    st.markdown(
        f'<div class="zyuka-callout"><strong>{title}</strong><br>{body}'
        f"{'<br><em>' + cta + '</em>' if cta else ''}</div>",
        unsafe_allow_html=True,
    )


def project_guard(paths: ProjectPaths) -> bool:
    """Show a warning and return False when zyuka.yml is missing.

    Pages that need a configured project call this first and short-circuit
    if it returns False.
    """

    if paths.config.exists():
        return True
    empty_state(
        "This folder isn't a Zyuka project yet.",
        f"No <code>zyuka.yml</code> in <code>{paths.root}</code>. "
        "Change the project directory in the sidebar, or run "
        "<code>zyuka init</code> in a terminal to set one up.",
    )
    return False
