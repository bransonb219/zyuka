"""Protect (pseudonymise + generalise + minimise) a dataset."""

from __future__ import annotations

import streamlit as st

from zyuka.errors import ZyukaError
from zyuka.gui.components import empty_state, init_page, project_guard
from zyuka.gui.mask import masked_preview
from zyuka.pipeline_support import protect_dataframe

paths = init_page("Protect")
if not project_guard(paths):
    st.stop()

st.caption(
    "Applies the three protection rules: pseudonymise identifiers (HMAC-SHA256), "
    "generalise GPS/DOB/dates, drop free text. Produces a manifest describing each column."
)

df = st.session_state.get("uploaded_df")
if df is None:
    empty_state(
        "No dataset loaded.",
        "Go to <strong>Upload & Quality</strong> first — Protect works on the "
        "same in-memory dataset so you don't re-upload.",
    )
    st.stop()

name = st.session_state.get("uploaded_name", "dataset")
st.markdown(
    f"Protecting **{name}** ({len(df):,} rows, {df.shape[1]:,} columns) "
    f"using settings in `{paths.config}`."
)

st.subheader("Before (masked)")
st.dataframe(masked_preview(df, limit=5), use_container_width=True, hide_index=True)

if st.button("Apply protection", type="primary"):
    try:
        protected, manifest = protect_dataframe(df, project_dir=paths.root)
    except ZyukaError as exc:
        st.error(exc.message)
        if exc.suggest:
            st.info(f"Suggested fix: {exc.suggest}")
        st.stop()

    st.success(
        f"Protected dataset: {len(protected):,} rows, {protected.shape[1]:,} columns retained."
    )
    st.subheader("After (masked)")
    st.dataframe(masked_preview(protected, limit=5), use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    stem = name.rsplit(".", 1)[0] if "." in name else name
    with c1:
        st.download_button(
            "Download protected CSV",
            data=protected.to_csv(index=False).encode("utf-8"),
            file_name=f"protected_{stem}.csv",
            mime="text/csv",
            type="primary",
        )
    with c2:
        st.download_button(
            "Download protection manifest",
            data=manifest.encode("utf-8"),
            file_name=f"protection_manifest_{stem}.json",
            mime="application/json",
        )

    with st.expander("Manifest (JSON)"):
        st.code(manifest, language="json")
