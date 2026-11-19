"""Scan an uploaded dataset for PII and sensitive fields."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from zyuka.errors import ZyukaError
from zyuka.gui.components import empty_state, init_page, project_guard
from zyuka.privacy.scanner import scan_dataframe

paths = init_page("Privacy scan")
if not project_guard(paths):
    st.stop()

st.caption(
    "Flags each column as high/medium/low risk using name and value heuristics "
    "(NRC, phone, email, GPS, DOB, sensitive attributes)."
)

df = st.session_state.get("uploaded_df")
if df is None:
    empty_state(
        "No dataset loaded.",
        "Go to <strong>Upload & Quality</strong> and bring in a CSV/XLSX first. "
        "The scan runs on the same in-memory dataset — no need to upload twice.",
    )
    st.stop()

st.markdown(
    f"Scanning **{st.session_state.get('uploaded_name', 'dataset')}** "
    f"({len(df):,} rows, {df.shape[1]:,} columns)."
)

if st.button("Run privacy scan", type="primary"):
    try:
        report = scan_dataframe(df)
    except ZyukaError as exc:
        st.error(exc.message)
        st.stop()

    rows = [
        {
            "Column": col.name,
            "Risk": col.risk,
            "Signals": ", ".join(col.signals),
            "Suggested action": col.suggested_action,
        }
        for col in report.columns
    ]
    scan_df = pd.DataFrame(rows)

    by_risk = scan_df["Risk"].value_counts().to_dict() if not scan_df.empty else {}
    c1, c2, c3 = st.columns(3)
    c1.metric("High risk", by_risk.get("high", 0))
    c2.metric("Medium risk", by_risk.get("medium", 0))
    c3.metric("Low risk", by_risk.get("low", 0))

    st.subheader("Columns")
    st.dataframe(scan_df, width="stretch", hide_index=True)

    if by_risk.get("high", 0) > 0:
        st.warning(
            "High-risk columns were found. Visit the **Protect** page to "
            "pseudonymise and generalise them before sharing or storing."
        )
    else:
        st.success("No high-risk columns detected.")
