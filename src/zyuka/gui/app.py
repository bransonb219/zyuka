"""Streamlit entry point for ``zyuka gui``.

The app is local-first by construction: the CLI launches it bound to
``127.0.0.1`` with telemetry disabled. Every preview renders only column
names, counts and masked samples — never raw PII. All heavy lifting lives
in ``zyuka.pipeline``; the GUI is a thin wrapper.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import streamlit as st

from zyuka import __version__

# Telemetry safety-belt: even if the user overrode their global Streamlit
# config, the CLI launcher sets ``--browser.gatherUsageStats=false``; here
# we additionally set the runtime option so ``streamlit run <file>`` from
# a developer shell can't leak either.
with contextlib.suppress(Exception):
    st.set_option("browser.gatherUsageStats", False)

st.set_page_config(
    page_title="Zyuka",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


def _sidebar() -> Path:
    st.sidebar.title("Zyuka")
    st.sidebar.caption(f"v{__version__} — local only, no telemetry")
    project = st.sidebar.text_input("Project directory", value=str(Path.cwd()))
    st.sidebar.info(
        "Zyuka runs on your machine. Nothing is uploaded. "
        "Raw personal data is never shown in this GUI."
    )
    return Path(project).expanduser()


def main() -> None:
    project_dir = _sidebar()
    st.title("Zyuka — privacy-first M&E toolkit")
    st.markdown(
        """
Use the pages on the left to upload exports, scan for PII, protect a dataset,
compute indicators, preview reports and verify the audit log.

- All previews are **masked**.
- Keys stay in the file named in `zyuka.yml` and are never shown here.
- Reports produced by the GUI are identical to those from `zyuka run`.
        """
    )
    st.subheader("Project")
    st.write(f"Directory: `{project_dir}`")
    if not (project_dir / "zyuka.yml").exists():
        st.warning(
            "No `zyuka.yml` found. Run `zyuka init` first, or create one in the project directory."
        )
    else:
        st.success("`zyuka.yml` found. Ready to use.")


if __name__ == "__main__":  # pragma: no cover
    main()
else:
    main()
