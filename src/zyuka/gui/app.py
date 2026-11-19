"""Streamlit entry point for ``zyuka gui``.

The home page is a workflow dashboard: it reads the current project's
outputs directory and shows which pipeline stages have completed, which
are next, and what the user should click. All heavy work still lives in
``zyuka.pipeline``; this file only orchestrates state and navigation.
"""

from __future__ import annotations

import contextlib
from importlib import resources
from pathlib import Path

import streamlit as st

from zyuka.gui.components import (
    empty_state,
    init_page,
    mearl_coverage_card,
    project_guard,
    workflow_step,
)

with contextlib.suppress(Exception):
    st.set_option("browser.gatherUsageStats", False)

_FAVICON = Path(str(resources.files("zyuka.gui").joinpath("brand", "favicon.svg")))

st.set_page_config(
    page_title="Zyuka · MEARL toolkit",
    page_icon=str(_FAVICON) if _FAVICON.exists() else "◐",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    paths = init_page("Zyuka")
    st.caption(
        "Privacy-first Monitoring, Evaluation, Accountability, Research & Learning — local only."
    )

    if not project_guard(paths):
        st.markdown(
            "Pick a folder containing `zyuka.yml` in the sidebar, or create one with "
            "`zyuka init` in a terminal, then reload this page."
        )
        return

    left, right = st.columns([2, 1], gap="large")

    with left:
        st.subheader("Workflow")
        st.caption("Each step writes to `outputs/`. Tick marks appear as files are produced.")

        data_present = paths.data_dir.exists() and any(paths.data_dir.glob("*.csv"))
        quality_present = (paths.outputs_dir / "quality").exists() and any(
            (paths.outputs_dir / "quality").glob("quality_flags_*.csv")
        )
        scan_present = (paths.outputs_dir / "scan").exists() and any(
            (paths.outputs_dir / "scan").glob("scan_*.json")
        )
        protected_present = paths.protected_dir.exists() and any(
            paths.protected_dir.glob("protected_*.csv")
        )
        indicators_present = (paths.outputs_dir / "indicator_results.json").exists()
        report_present = paths.report_html.exists()
        audit_present = paths.audit_log.exists()

        workflow_step("1 · Upload & quality", quality_present, "page: Upload & Quality")
        workflow_step("2 · Privacy scan", scan_present, "page: Privacy Scan")
        workflow_step("3 · Protect", protected_present, "page: Protect")
        workflow_step("4 · Indicators", indicators_present, "page: Indicators")
        workflow_step("5 · Report", report_present, "page: Reports")
        workflow_step("6 · Audit", audit_present, "page: Audit")

        if not data_present:
            empty_state(
                "No data folder detected.",
                "Place Kobo/ODK exports in <code>data/</code> inside this project, "
                "or use the <strong>Upload & Quality</strong> page to drop a file in.",
            )

        st.divider()
        mearl_coverage_card()

    with right:
        st.subheader("Project snapshot")
        st.markdown(f"**Folder**\n`{paths.root}`")
        if paths.config.exists():
            st.markdown("**zyuka.yml** · present")
        if paths.logframe.exists():
            st.markdown("**logframe.yml** · present")
        if report_present:
            st.markdown("**Latest report** · available")

        st.divider()
        st.subheader("Privacy promise")
        st.markdown(
            "- Data stays on this machine.\n"
            "- No telemetry, no sync, no cloud.\n"
            "- Previews mask identifiers.\n"
            "- Keys live outside the project folder."
        )

        st.divider()
        st.subheader("Standards followed")
        st.markdown(
            "- **DAC** evaluation criteria (relevance, coherence, "
            "effectiveness, efficiency, impact, sustainability).\n"
            "- **CHS** core humanitarian standard "
            "(accountability, complaints handling — roadmap).\n"
            "- **Zambia DPA 2021** · **GDPR**-aligned data handling.\n"
            "- **IATI**-ready indicator outputs (roadmap)."
        )


main()
