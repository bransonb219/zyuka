"""Upload a Kobo/ODK export and run quality checks (masked preview)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from linga.gui.mask import masked_preview
from linga.ingest.rounds import read_table
from linga.quality.report import run_quality

st.title("Upload and quality")

uploaded = st.file_uploader("Kobo or ODK export (CSV/XLSX)", type=["csv", "xlsx"])
round_name = st.selectbox("Round", options=["baseline", "midline", "endline"], index=0)

if uploaded is not None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="linga-gui-"))
    tmp = tmp_dir / uploaded.name
    tmp.write_bytes(uploaded.read())
    df: pd.DataFrame = read_table(tmp)
    df["round"] = round_name

    st.subheader("Preview (masked)")
    st.dataframe(masked_preview(df, limit=10), use_container_width=True)

    if st.button("Run quality checks"):
        report = run_quality(df)
        st.subheader("Summary")
        st.table(pd.DataFrame(sorted(report.summary.items()), columns=["Check", "Count"]))
        st.subheader("Flags")
        st.dataframe(report.flags, use_container_width=True)
