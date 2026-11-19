"""Show and verify the hash-chained audit log."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from zyuka.gui.components import empty_state, init_page, project_guard
from zyuka.security.audit import read_audit, verify_audit

paths = init_page("Audit")
if not project_guard(paths):
    st.stop()

if not paths.audit_log.exists():
    empty_state(
        "No audit log yet.",
        "The audit log is appended by every <code>zyuka run</code>. "
        "Run the pipeline once, then reload this page.",
    )
    st.stop()

entries = read_audit(paths.audit_log)
ok, bad = verify_audit(paths.audit_log)

c1, c2, c3 = st.columns(3)
c1.metric("Entries", len(entries))
c2.metric("Chain", "✓ valid" if ok else "✗ broken")
c3.metric("Latest", entries[-1].get("timestamp", "—") if entries else "—")

if ok:
    st.success("Audit chain verified — no tampering detected.")
else:
    st.error(f"Audit chain broken at entry index {bad}.")

st.caption(f"Log file: `{paths.audit_log}`")

rows = [
    {
        "When": e.get("timestamp"),
        "Command": e.get("command"),
        "Rows": e.get("rows"),
        "Columns": e.get("columns"),
        "Hash": (e.get("hash") or "")[:12] + "…" if e.get("hash") else "",
    }
    for e in entries
]
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

st.download_button(
    "Download audit log (JSONL)",
    data=paths.audit_log.read_bytes(),
    file_name="audit.jsonl",
    mime="application/jsonl",
)
