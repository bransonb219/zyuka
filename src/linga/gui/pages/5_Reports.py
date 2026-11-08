"""Preview the HTML report and download outputs."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

st.title("Reports")

project = st.text_input("Project directory", value=str(Path.cwd()), key="rep_project")
report_dir = Path(project) / "outputs" / "report"
html_path = report_dir / "report.html"
excel_path = report_dir / "iptt.xlsx"

if not html_path.exists():
    st.info("No report yet. Run `linga run` or use the demo to generate one.")
else:
    st.success(f"Report: {html_path}")
    with html_path.open("rb") as fh:
        st.download_button(
            "Download HTML report",
            data=fh.read(),
            file_name="report.html",
            mime="text/html",
        )
    if excel_path.exists():
        with excel_path.open("rb") as fh:
            st.download_button(
                "Download Excel IPTT",
                data=fh.read(),
                file_name="iptt.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    st.subheader("Preview")
    st.components.v1.html(html_path.read_text(encoding="utf-8"), height=800, scrolling=True)
