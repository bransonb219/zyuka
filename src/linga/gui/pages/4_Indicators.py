"""View and validate the project's logframe."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from linga.config import load_logframe

st.title("Indicators")

project = st.text_input("Project directory", value=str(Path.cwd()), key="ind_project")
logframe_path = Path(project) / "logframe.yml"

if not logframe_path.exists():
    st.warning(f"No `logframe.yml` found at {logframe_path}.")
else:
    logframe = load_logframe(logframe_path)
    st.subheader(f"Goal: {logframe.goal}")
    rows = []
    for ind in logframe.all_indicators():
        rows.append(
            {
                "code": ind.code,
                "name": ind.name,
                "type": ind.type,
                "numerator": ind.numerator,
                "denominator": ind.denominator or "",
                "disaggregations": ", ".join(ind.disaggregations),
                "unit": ind.unit,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    st.caption("Edit `logframe.yml` in your editor. The CLI command `linga compute` validates it.")
