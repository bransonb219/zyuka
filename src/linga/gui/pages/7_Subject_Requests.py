"""Honour data-subject access and erasure requests."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from linga.rights.subject import erase_subject, find_subject

st.title("Subject requests")

project = st.text_input("Project directory", value=str(Path.cwd()), key="subj_project")
data_dir = st.text_input(
    "Protected data directory",
    value=str(Path(project) / "outputs" / "protected"),
    key="subj_data",
)
identifier = st.text_input(
    "Raw identifier (will be hashed with the project key before searching)",
    type="password",
    key="subj_id",
)

col1, col2 = st.columns(2)

with col1:
    if st.button("Find"):
        if not identifier:
            st.warning("Enter an identifier first.")
        else:
            matches = find_subject(Path(project), Path(data_dir), identifier)
            if not matches:
                st.info("No matches.")
            else:
                for m in matches:
                    st.write(f"- `{m.path}` ({m.row_count} rows, columns: {m.matched_columns})")

with col2:
    confirm = st.checkbox("I confirm this erasure is authorised.")
    if st.button("Erase"):
        if not identifier:
            st.warning("Enter an identifier first.")
        elif not confirm:
            st.warning("Tick the confirmation box first.")
        else:
            report = erase_subject(Path(project), Path(data_dir), identifier)
            st.success(f"Erased {report.rows_removed} rows across {len(report.files)} files.")
