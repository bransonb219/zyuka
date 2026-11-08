"""Show and verify the hash-chained audit log."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from linga.security.audit import read_audit, verify_audit

st.title("Audit")

project = st.text_input("Project directory", value=str(Path.cwd()), key="audit_project")
log_path = Path(project) / ".linga" / "audit.jsonl"

if not log_path.exists():
    st.info("No audit log yet. Run `linga run` to create one.")
else:
    entries = read_audit(log_path)
    st.caption(f"{len(entries)} entries")
    ok, bad = verify_audit(log_path)
    if ok:
        st.success("Audit chain verified.")
    else:
        st.error(f"Audit chain broken at entry index {bad}.")
    rows = [
        {
            "timestamp": e.get("timestamp"),
            "command": e.get("command"),
            "rows": e.get("rows"),
            "columns": e.get("columns"),
            "hash": (e.get("hash") or "")[:12] + "…",
        }
        for e in entries
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
