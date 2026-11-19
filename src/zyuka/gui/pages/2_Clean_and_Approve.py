"""Review quality flags, approve fixes, write a cleaned round.

The page shows one card per flag group with a masked sample, the
proposed fix and Approve / Modify / Reject controls. Approved choices
are saved to ``.zyuka/cleaning_rules.json`` so subsequent rounds
auto-apply them.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from zyuka.gui.components import empty_state, init_page, project_guard
from zyuka.gui.mask import masked_preview
from zyuka.quality.remediate import (
    VALID_KINDS,
    CleaningDecision,
    FixAction,
    apply_decisions,
    propose_actions,
)
from zyuka.quality.report import run_quality
from zyuka.quality.rules import load_rules, preapproved_decisions, save_rules


def _render_action_card(df: pd.DataFrame, action: FixAction, index: int) -> None:
    """One card per action; writes the user's choice into session_state."""

    key = f"decision_{action.reason}_{action.column}_{index}"
    with st.container(border=True):
        top = st.columns([3, 1])
        top[0].markdown(
            f"**{action.reason}** · `{action.column}`  "
            f"<span style='color:#64748B'>— {len(action.row_indices)} row(s)</span>",
            unsafe_allow_html=True,
        )
        top[1].markdown(
            f"<div style='text-align:right;color:#64748B'>default: "
            f"<code>{action.kind}</code></div>",
            unsafe_allow_html=True,
        )
        if action.rationale:
            st.caption(action.rationale)

        if action.row_indices:
            sample_idx = list(action.row_indices)[:5]
            sample = df.loc[[i for i in sample_idx if i in df.index]]
            if not sample.empty:
                with st.expander("Masked sample", expanded=False):
                    st.dataframe(masked_preview(sample, limit=5), width="stretch", hide_index=True)

        choice = st.radio(
            "Decision",
            ["Approve default", "Modify", "Reject"],
            key=f"choice_{key}",
            horizontal=True,
            label_visibility="collapsed",
        )

        override_kind: str | None = None
        override_params: dict[str, float] | None = None
        if choice == "Modify":
            override_kind = st.selectbox(
                "Alternative fix",
                list(VALID_KINDS),
                index=list(VALID_KINDS).index(action.kind),
                key=f"kind_{key}",
            )
            if override_kind == "winsorize":
                col1, col2 = st.columns(2)
                p_low = col1.number_input(
                    "Lower percentile",
                    value=0.01,
                    min_value=0.0,
                    max_value=0.5,
                    step=0.01,
                    key=f"plow_{key}",
                )
                p_high = col2.number_input(
                    "Upper percentile",
                    value=0.99,
                    min_value=0.5,
                    max_value=1.0,
                    step=0.01,
                    key=f"phigh_{key}",
                )
                override_params = {"p_low": float(p_low), "p_high": float(p_high)}

        status_map = {"Approve default": "approved", "Modify": "modified", "Reject": "rejected"}
        st.session_state["clean_decisions"][key] = CleaningDecision(
            action=action,
            status=status_map[choice],
            override_kind=override_kind,
            override_params=override_params,
        )


paths = init_page("Clean & approve")
if not project_guard(paths):
    st.stop()

st.caption(
    "One card per issue group. Approve the proposed fix, modify it, or reject it. "
    "Approvals are remembered for future rounds."
)

df = st.session_state.get("uploaded_df")
if df is None:
    empty_state(
        "No dataset loaded yet.",
        "Head to <strong>Upload & quality</strong> first — Clean & approve runs on "
        "what you just uploaded.",
    )
    st.stop()

quality = run_quality(df)
actions = propose_actions(df, quality.flags, quality.per_column_missing)

if not actions:
    st.success("No quality issues to clean.")
    st.caption("You can move on to Privacy Scan.")
    st.stop()

rules = load_rules(paths.root)
pre = preapproved_decisions(actions, rules)
pre_keys = {(d.action.reason, d.action.column) for d in pre}

c1, c2, c3 = st.columns(3)
c1.metric("Flag groups", len(actions))
c2.metric("Pre-approved (from saved rules)", len(pre))
c3.metric("Need decisions", len(actions) - len(pre))

if pre:
    with st.expander(f"{len(pre)} fix(es) already approved from a previous round", expanded=False):
        for d in pre:
            st.markdown(
                f"- **{d.action.reason}** · `{d.action.column}` → `{d.effective_kind}` "
                f"{dict(d.effective_params) or ''}"
            )

st.divider()
st.subheader("Decisions")

if "clean_decisions" not in st.session_state:
    st.session_state["clean_decisions"] = {}

for i, action in enumerate(actions):
    if (action.reason, action.column) in pre_keys:
        continue
    _render_action_card(df, action, index=i)

st.divider()

cols = st.columns([1, 1, 2])
if cols[0].button("Apply approved fixes", type="primary"):
    all_decisions = list(pre) + list(st.session_state["clean_decisions"].values())
    result = apply_decisions(df, all_decisions)

    for decision in all_decisions:
        if decision.status in {"approved", "modified"}:
            rules.upsert(decision)
    save_rules(paths.root, rules)

    clean_dir = paths.outputs_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    round_name = st.session_state.get("round_name", "baseline")
    clean_path = clean_dir / f"clean_{round_name}.csv"
    result.cleaned.to_csv(clean_path, index=False)

    review_path: Path | None = None
    if not result.review_rows.empty:
        review_path = clean_dir / f"review_{round_name}.csv"
        result.review_rows.to_csv(review_path, index=False)

    st.session_state["uploaded_df"] = result.cleaned
    st.success(f"Wrote {clean_path.name} · {len(result.cleaned):,} rows after cleaning.")

    summary_rows = [{"Action": k, "Rows affected": v} for k, v in result.summary.items()]
    if summary_rows:
        st.table(pd.DataFrame(summary_rows))
    if review_path is not None:
        st.caption(f"{len(result.review_rows)} row(s) tagged for review in {review_path.name}.")

if cols[1].button("Reset decisions"):
    st.session_state["clean_decisions"] = {}
    st.rerun()
