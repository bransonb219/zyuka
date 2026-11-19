"""View and validate the project's logframe."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from zyuka.config import load_logframe
from zyuka.errors import ZyukaError
from zyuka.gui.components import empty_state, init_page, project_guard

paths = init_page("Indicators")
if not project_guard(paths):
    st.stop()

if not paths.logframe.exists():
    empty_state(
        "No logframe yet.",
        f"Expected <code>{paths.logframe}</code>. "
        "Run <code>zyuka init</code> for a template, then edit it in your editor.",
    )
    st.stop()

try:
    logframe = load_logframe(paths.logframe)
except ZyukaError as exc:
    st.error(exc.message)
    if exc.suggest:
        st.info(f"Suggested fix: {exc.suggest}")
    st.stop()

st.caption(
    "Read-only view. Edit `logframe.yml` in your editor; "
    "`zyuka compute` validates it against your data."
)

st.markdown(f"**Goal.** {logframe.goal}")

all_inds = logframe.all_indicators()
c1, c2, c3 = st.columns(3)
c1.metric("Indicators", len(all_inds))
c2.metric("Outcomes", len(logframe.outcomes))
c3.metric("Outputs", sum(len(oc.outputs) for oc in logframe.outcomes))

results_path = paths.outputs_dir / "indicator_results.json"
if results_path.exists():
    st.success(
        f"Latest computed results available at `{results_path}`. "
        "Open the Reports page to see them in context."
    )
else:
    st.info("No computed results yet. Run `zyuka compute` or `zyuka run` to produce them.")

st.subheader("Indicators")
rows = [
    {
        "Code": ind.code,
        "Name": ind.name,
        "Type": ind.type,
        "Numerator": ind.numerator,
        "Denominator": ind.denominator or "",
        "Disaggregations": ", ".join(ind.disaggregations),
        "Unit": ind.unit,
    }
    for ind in all_inds
]
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with st.expander("Structure"):
    for oc in logframe.outcomes:
        st.markdown(f"**{oc.code} · {oc.name}** — {len(oc.indicators)} indicator(s)")
        for op in oc.outputs:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ {op.code} · {op.name}")
