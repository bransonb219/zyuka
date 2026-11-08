"""Protect (pseudonymise + generalise + minimise) a dataset."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from linga.gui.mask import masked_preview
from linga.ingest.rounds import read_table
from linga.pipeline_support import protect_dataframe

st.title("Protect")

uploaded = st.file_uploader("Dataset (CSV/XLSX)", type=["csv", "xlsx"], key="protect_upload")
project = st.text_input("Project directory", value=str(Path.cwd()))

if uploaded is not None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="linga-gui-"))
    tmp = tmp_dir / uploaded.name
    tmp.write_bytes(uploaded.read())
    df = read_table(tmp)

    st.subheader("Before (masked)")
    st.dataframe(masked_preview(df, limit=5), use_container_width=True)

    if st.button("Apply protection"):
        protected, manifest = protect_dataframe(df, project_dir=Path(project))
        st.subheader("After (masked)")
        st.dataframe(masked_preview(protected, limit=5), use_container_width=True)
        st.download_button(
            label="Download protected CSV",
            data=protected.to_csv(index=False).encode("utf-8"),
            file_name=f"protected_{tmp.name}",
            mime="text/csv",
        )
        st.download_button(
            label="Download protection manifest",
            data=manifest.encode("utf-8"),
            file_name=f"protection_manifest_{tmp.stem}.json",
            mime="application/json",
        )
