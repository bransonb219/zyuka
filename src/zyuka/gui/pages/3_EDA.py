"""Exploratory data analysis on the current round.

Profiles the dataframe loaded by Upload & Quality (or produced by
Clean & Approve) and surfaces per-column stats, distribution hints and
the strongest pairwise numeric correlations. Nothing is written to
disk unless the user clicks ``Save EDA snapshot``.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from zyuka.analysis.eda import profile_dataframe
from zyuka.gui.components import empty_state, init_page, project_guard

paths = init_page("Exploratory data analysis")
if not project_guard(paths):
    st.stop()

st.caption(
    "Automatic profiling: dtypes, missingness, moments and correlations — "
    "all derived locally, no raw rows leave the machine."
)

df = st.session_state.get("uploaded_df")
if df is None:
    empty_state(
        "No dataset loaded yet.",
        "Upload a file from <strong>Upload & Quality</strong>, then come back.",
    )
    st.stop()

profile = profile_dataframe(df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{profile.n_rows:,}")
c2.metric("Columns", profile.n_cols)
c3.metric("Duplicate rows", profile.duplicate_rows)
kinds: dict[str, int] = {}
for col in profile.columns:
    kinds[col.kind] = kinds.get(col.kind, 0) + 1
c4.metric(
    "Numeric / categorical / text / date",
    " · ".join(str(kinds.get(k, 0)) for k in ("numeric", "categorical", "text", "datetime")),
)

st.divider()
st.subheader("Columns")

column_rows = []
for col in profile.columns:
    column_rows.append(
        {
            "Column": col.name,
            "Kind": col.kind,
            "Dtype": col.dtype,
            "Missing %": round(col.missing_pct, 1),
            "Unique": col.unique,
            "Mean": None if col.mean is None else round(col.mean, 3),
            "Std": None if col.std is None else round(col.std, 3),
            "Min": col.min,
            "Median": col.median,
            "Max": col.max,
            "Skew": None if col.skew is None else round(col.skew, 2),
        }
    )
st.dataframe(pd.DataFrame(column_rows), width="stretch", hide_index=True)

if not profile.correlations.empty:
    st.subheader("Top numeric correlations")
    st.caption("Pairwise Pearson r with |r| descending. Investigate collinearity > 0.8.")
    st.dataframe(profile.correlations.head(20), width="stretch", hide_index=True)

with st.expander("Top values per categorical column", expanded=False):
    for col in profile.by_kind("categorical"):
        if not col.top_values:
            continue
        top = pd.DataFrame(col.top_values, columns=["value", "count"]).head(10)
        st.markdown(f"**{col.name}** · {col.unique} unique")
        st.dataframe(top, width="stretch", hide_index=True)

st.divider()
if st.button("Save EDA snapshot", type="primary"):
    eda_dir = paths.outputs_dir / "eda"
    eda_dir.mkdir(parents=True, exist_ok=True)
    round_name = st.session_state.get("round_name", "baseline")
    path = eda_dir / f"eda_{round_name}.json"
    path.write_text(json.dumps(profile.to_dict(), indent=2, default=str), encoding="utf-8")
    st.success(f"Wrote {path.name} to {eda_dir}")
