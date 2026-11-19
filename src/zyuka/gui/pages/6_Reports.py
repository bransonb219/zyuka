"""Preview the HTML report and download outputs."""

from __future__ import annotations

import streamlit as st

from zyuka.gui.components import empty_state, init_page, project_guard

paths = init_page("Reports")
if not project_guard(paths):
    st.stop()

if not paths.report_html.exists():
    empty_state(
        "No report yet.",
        "Reports are produced by <code>zyuka run</code> (full pipeline) "
        "or <code>zyuka demo</code>. Run one in a terminal, then reload this page.",
    )
    st.stop()

st.caption(f"Latest HTML report: `{paths.report_html}`")

c1, c2 = st.columns(2)
with c1, paths.report_html.open("rb") as fh:
    st.download_button(
        "Download HTML report",
        data=fh.read(),
        file_name="report.html",
        mime="text/html",
        type="primary",
    )
with c2:
    if paths.report_excel.exists():
        with paths.report_excel.open("rb") as fh:
            excel_bytes = fh.read()
        st.download_button(
            "Download Excel IPTT",
            data=excel_bytes,
            file_name="iptt.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.caption("Excel IPTT not found.")

st.subheader("Preview")
st.caption(
    "Rendered inline. For the proper standalone view, download the HTML and open it in a browser."
)
try:
    html = paths.report_html.read_text(encoding="utf-8")
except OSError as exc:
    st.error(f"Could not read report: {exc}")
else:
    st.components.v1.html(html, height=800, scrolling=True)
