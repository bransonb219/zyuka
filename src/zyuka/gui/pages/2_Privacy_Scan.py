"""Scan an uploaded dataset for PII and sensitive fields."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from zyuka.ingest.rounds import read_table
from zyuka.privacy.scanner import scan_dataframe

st.title("Privacy scan")

uploaded = st.file_uploader("Dataset (CSV/XLSX)", type=["csv", "xlsx"], key="scan_upload")

if uploaded is not None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="zyuka-gui-"))
    tmp = tmp_dir / uploaded.name
    tmp.write_bytes(uploaded.read())
    df = read_table(tmp)
    report = scan_dataframe(df)

    rows = [
        {
            "column": col.name,
            "risk": col.risk,
            "signals": ", ".join(col.signals),
            "suggested_action": col.suggested_action,
        }
        for col in report.columns
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
