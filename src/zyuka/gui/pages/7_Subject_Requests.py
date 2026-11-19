"""Honour data-subject access and erasure requests."""

from __future__ import annotations

import streamlit as st

from zyuka.errors import ZyukaError
from zyuka.gui.components import empty_state, init_page, project_guard
from zyuka.rights.subject import erase_subject, find_subject

paths = init_page("Subject requests")
if not project_guard(paths):
    st.stop()

st.caption(
    "Search protected datasets for a specific person by raw identifier. "
    "Zyuka hashes the identifier with the project key before searching — the raw value never hits disk."
)

if not paths.protected_dir.exists():
    empty_state(
        "No protected dataset yet.",
        "Run <code>zyuka protect</code> (or the full <code>zyuka run</code>) first. "
        "Subject requests operate on the pseudonymised outputs, not raw data.",
    )
    st.stop()

identifier = st.text_input(
    "Raw identifier",
    type="password",
    help="e.g. NRC or phone. Hashed with your project key before lookup.",
    key="subject_identifier",
)

tab_find, tab_erase = st.tabs(["Find", "Erase"])

with tab_find:
    st.markdown(
        "Search protected files for this subject. Only file paths and row "
        "counts are returned — no field contents."
    )
    if st.button("Find", type="primary", key="subject_find_btn"):
        if not identifier:
            st.warning("Enter an identifier first.")
        else:
            try:
                matches = find_subject(paths.root, paths.protected_dir, identifier)
            except ZyukaError as exc:
                st.error(exc.message)
            else:
                if not matches:
                    st.info("No matches.")
                else:
                    st.success(f"Found {len(matches)} file(s).")
                    for m in matches:
                        st.markdown(
                            f"- `{m.path}` — {m.row_count} row(s) "
                            f"in columns: `{', '.join(m.matched_columns)}`"
                        )

with tab_erase:
    st.markdown(
        "Permanently removes this subject's rows from every protected file "
        "and writes an erasure entry to the audit log."
    )
    confirmed = st.checkbox(
        "I confirm this erasure is authorised and documented.",
        key="subject_erase_confirm",
    )
    if st.button("Erase", type="primary", key="subject_erase_btn"):
        if not identifier:
            st.warning("Enter an identifier first.")
        elif not confirmed:
            st.warning("Tick the confirmation box first.")
        else:
            try:
                report = erase_subject(paths.root, paths.protected_dir, identifier)
            except ZyukaError as exc:
                st.error(exc.message)
            else:
                st.success(
                    f"Erased {report.rows_removed} row(s) across {len(report.files)} file(s)."
                )
