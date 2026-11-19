"""Upload a Kobo/ODK export and run quality checks (masked preview)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from zyuka.errors import ZyukaError
from zyuka.gui.components import empty_state, init_page, project_guard
from zyuka.gui.mask import masked_preview
from zyuka.ingest.rounds import read_table
from zyuka.quality.report import run_quality

paths = init_page("Upload & quality")
if not project_guard(paths):
    st.stop()

st.caption("Drop a CSV or XLSX export. Zyuka reads it in memory and shows a masked preview.")

uploaded = st.file_uploader(
    "Kobo or ODK export",
    type=["csv", "xlsx"],
    key="upload_quality_file",
    help="Max 200 MB. File stays on this machine.",
)

if uploaded is None and st.session_state.get("uploaded_df") is None:
    empty_state(
        "No file yet.",
        "Choose a CSV or XLSX export above. Nothing leaves this machine.",
        cta="Tip: start with `data/survey_baseline.csv` from the demo.",
    )
    st.stop()

if uploaded is not None:
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="zyuka-gui-"))
        tmp = tmp_dir / uploaded.name
        tmp.write_bytes(uploaded.read())
        df: pd.DataFrame = read_table(tmp)
        df["round"] = st.session_state["round_name"]
        st.session_state["uploaded_df"] = df
        st.session_state["uploaded_name"] = uploaded.name
    except ZyukaError as exc:
        st.error(f"Could not read the file: {exc.message}")
        if exc.suggest:
            st.info(f"Suggested fix: {exc.suggest}")
        st.stop()
    except Exception as exc:
        st.error(f"Could not read the file: {exc}")
        st.stop()

df = st.session_state["uploaded_df"]
name = st.session_state.get("uploaded_name", "(in-memory dataset)")

col1, col2, col3 = st.columns(3)
col1.metric("File", name)
col2.metric("Rows", f"{len(df):,}")
col3.metric("Columns", f"{df.shape[1]:,}")

st.subheader("Preview (masked)")
st.dataframe(masked_preview(df, limit=10), use_container_width=True, hide_index=True)
st.caption(
    f"Round tag: **{st.session_state['round_name']}** (change in the sidebar). "
    "Identifier columns are starred out."
)

st.divider()
st.subheader("Data quality")
st.caption("Runs duplicate, missingness, outlier, constraint, duration and enumerator checks.")

if st.button("Run quality checks", type="primary"):
    try:
        report = run_quality(df)
    except ZyukaError as exc:
        st.error(exc.message)
        st.stop()
    summary_rows = [{"Check": k, "Count": v} for k, v in sorted(report.summary.items())]
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        st.markdown("**Summary**")
        st.table(pd.DataFrame(summary_rows))
    with c2:
        st.markdown("**Flags**")
        if report.flags.empty:
            st.success("No issues flagged.")
        else:
            st.dataframe(report.flags, use_container_width=True, hide_index=True)
            st.download_button(
                "Download flags (CSV)",
                data=report.flags.to_csv(index=False).encode("utf-8"),
                file_name=f"quality_flags_{Path(name).stem}.csv",
                mime="text/csv",
            )
