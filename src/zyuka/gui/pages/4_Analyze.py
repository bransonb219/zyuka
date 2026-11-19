"""Analysis Advisor — suggest and run statistical tests on approval."""

from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st

from zyuka.analysis.advisor import AnalysisSuggestion, suggest_analyses
from zyuka.analysis.tests import run_many
from zyuka.gui.components import empty_state, init_page, project_guard

paths = init_page("Analyze")
if not project_guard(paths):
    st.stop()

st.caption(
    "The advisor inspects your data and proposes tests that fit. "
    "Approve the ones you want, hit <strong>Run</strong>, and results are written to "
    "<code>outputs/analysis/</code>.",
)

df = st.session_state.get("uploaded_df")
if df is None:
    empty_state(
        "No dataset loaded yet.",
        "Upload a file from <strong>Upload & Quality</strong> first.",
    )
    st.stop()

pii_cols = list(st.session_state.get("pii_columns", []))
suggestions: list[AnalysisSuggestion] = suggest_analyses(df, pii_columns=pii_cols)

if not suggestions:
    empty_state(
        "No tests to suggest yet.",
        "The dataset might be too small or lack the column types needed. "
        "You can still run tests manually via the CLI (<code>zyuka analyze</code>).",
    )
    st.stop()

st.success(f"{len(suggestions)} test(s) suggested.")
if pii_cols:
    st.caption(f"Excluded from analysis: {', '.join(pii_cols)}")

if "analyze_approvals" not in st.session_state:
    st.session_state["analyze_approvals"] = {}

by_category: dict[str, list[AnalysisSuggestion]] = {}
for s in suggestions:
    by_category.setdefault(s.category or "Other", []).append(s)

for category, items in by_category.items():
    st.subheader(category)
    for s in items:
        key = f"{s.test}:{','.join(s.columns)}"
        with st.container(border=True):
            top = st.columns([3, 1])
            top[0].markdown(f"**{s.name}**")
            top[1].markdown(
                f"<div style='text-align:right;color:#64748B'>confidence {s.confidence:.0%}</div>",
                unsafe_allow_html=True,
            )
            st.caption(s.rationale)
            st.markdown(s.explanation)
            st.session_state["analyze_approvals"][key] = st.checkbox(
                "Run this test",
                value=s.confidence >= 0.7,
                key=f"approve_{key}",
            )

st.divider()
cols = st.columns([1, 1, 2])

if cols[0].button("Run approved tests", type="primary"):
    approved: list[dict[str, object]] = []
    for s in suggestions:
        key = f"{s.test}:{','.join(s.columns)}"
        if st.session_state["analyze_approvals"].get(key):
            approved.append({"test": s.test, "columns": s.columns})

    if not approved:
        st.warning("Nothing was approved.")
        st.stop()

    results = run_many(df, approved)

    analysis_dir = paths.outputs_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    round_name = st.session_state.get("round_name", "baseline")
    written: list[Path] = []
    for result in results:
        slug_cols = "_".join(result.columns)[:60]
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", f"{result.kind}_{slug_cols}")
        path = analysis_dir / f"{safe}_{round_name}.json"
        path.write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
        written.append(path)

    st.success(f"Ran {len(results)} test(s); wrote {len(written)} file(s) to {analysis_dir}")
    for result in results:
        with st.container(border=True):
            st.markdown(f"**{result.name}** · `{' × '.join(result.columns)}`")
            st.write(result.summary)
            if result.metrics:
                st.json(result.metrics, expanded=False)
            if result.warnings:
                st.warning(" · ".join(result.warnings))

if cols[1].button("Reset approvals"):
    st.session_state["analyze_approvals"] = {}
    st.rerun()
