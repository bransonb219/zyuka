"""Reusable Streamlit components for the Zyuka GUI."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from importlib import resources
from pathlib import Path

import streamlit as st

from zyuka import __version__
from zyuka.gui.state import ProjectPaths, ensure_state, set_project_dir
from zyuka.gui.theme import apply_theme


def _brand_asset(name: str) -> Path:
    """Return the absolute path to a packaged brand asset.

    The ``brand/`` folder ships inside the ``zyuka`` wheel so the GUI works
    identically whether launched from a clone of the repo or from a pipx
    install.
    """

    files = resources.files("zyuka.gui").joinpath("brand", name)
    return Path(str(files))


def init_page(title: str, icon: str = "") -> ProjectPaths:
    """Standard page prelude: theme + logo + sidebar + resolved project paths."""

    apply_theme()
    paths = ensure_state()
    st.logo(
        image=str(_brand_asset("logo.svg")),
        icon_image=str(_brand_asset("mark.svg")),
        size="large",
    )
    render_sidebar(paths)
    heading = f"{icon} {title}".strip() if icon else title
    st.title(heading)
    return paths


def render_sidebar(paths: ProjectPaths) -> None:
    """Shared sidebar: brand plate, project switcher, status, round, actions, help."""

    sb = st.sidebar

    sb.caption(f"Zyuka v{__version__} · local only · no telemetry")

    sb.markdown("#### Project")
    current = st.session_state.get("project_dir", str(Path.cwd()))
    new_value = sb.text_input(
        "Folder",
        value=current,
        key="sidebar_project_input",
        help="Directory containing zyuka.yml. All pages read from here.",
        label_visibility="collapsed",
    )
    if new_value != current:
        set_project_dir(new_value)
        st.rerun()

    _render_project_status(sb, paths)

    sb.markdown("#### Round")
    rounds = ["baseline", "midline", "endline"]
    default_idx = rounds.index(st.session_state.get("round_name", "baseline"))
    picked = sb.selectbox(
        "Current round",
        options=rounds,
        index=default_idx,
        key="sidebar_round",
        help="Label applied to uploads and shown in reports.",
        label_visibility="collapsed",
    )
    st.session_state["round_name"] = picked

    _render_sidebar_actions(sb, paths)

    with sb.expander("Help", expanded=False):
        st.markdown(
            "- **Quickstart** — `docs/quickstart.md`\n"
            "- **Logframe guide** — `docs/logframe-guide.md`\n"
            "- **Data protection** — `docs/data-protection.md`\n"
            "- **Report a bug** — open an issue on GitHub."
        )

    sb.info(
        "Runs on your machine. Nothing is uploaded. "
        "Previews are masked — raw personal data never appears here."
    )


def _render_project_status(sb: st.delta_generator.DeltaGenerator, paths: ProjectPaths) -> None:
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
            f'padding:2px 0;color:{colour};font-size:0.85rem">'
            f"<span>{icon} {label}</span>"
            f'<span style="opacity:0.7">{"ready" if ok else "missing"}</span>'
            "</div>",
            unsafe_allow_html=True,
        )


def _render_sidebar_actions(sb: st.delta_generator.DeltaGenerator, paths: ProjectPaths) -> None:
    """Quick actions row — avoids forcing the user back to the terminal for small moves."""

    sb.markdown("#### Actions")
    outputs = paths.outputs_dir
    if sb.button(
        "Open outputs folder",
        use_container_width=True,
        disabled=not outputs.exists(),
        help=f"{outputs}",
    ):
        _open_in_file_manager(outputs)
    if sb.button(
        "Open project folder",
        use_container_width=True,
        help=f"{paths.root}",
    ):
        _open_in_file_manager(paths.root)


def _open_in_file_manager(path: Path) -> None:
    """Cross-platform: show the given folder in the OS file manager."""

    try:
        if sys.platform.startswith("win") or platform.system() == "Windows":
            startfile = getattr(os, "startfile", None)
            if startfile is not None:
                startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError as exc:
        st.toast(f"Could not open folder: {exc}", icon="⚠️")


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
    """Show a warning and return False when zyuka.yml is missing."""

    if paths.config.exists():
        return True
    empty_state(
        "This folder isn't a Zyuka project yet.",
        f"No <code>zyuka.yml</code> in <code>{paths.root}</code>. "
        "Change the project directory in the sidebar, or run "
        "<code>zyuka init</code> in a terminal to set one up.",
    )
    return False


def mearl_coverage_card() -> None:
    """Honest MEARL scope card. Shows which pillars are shipped vs planned."""

    pillars = [
        ("Monitoring", "shipped", "Quality checks, rounds, enumerator tracking, duration flags."),
        ("Evaluation", "shipped", "Indicators engine, longitudinal change, IPTT, HTML report."),
        ("Accountability", "planned", "Complaints & feedback mechanism, response tracking."),
        ("Research", "partial", "Synthetic data, outlier detection; study-design helpers planned."),
        ("Learning", "planned", "Learning briefs, after-action review, reflection prompts."),
    ]
    st.markdown("### MEARL coverage")
    st.caption(
        "What Zyuka does today, and what is on the roadmap. "
        "See `docs/mearl-coverage.md` for the plan."
    )
    for name, status, detail in pillars:
        badge_class = {"shipped": "mearl-shipped", "partial": "mearl-partial"}.get(
            status, "mearl-planned"
        )
        st.markdown(
            f'<div class="mearl-row">'
            f'<span class="mearl-pillar">{name}</span>'
            f'<span class="mearl-badge {badge_class}">{status}</span>'
            f'<span class="mearl-detail">{detail}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
