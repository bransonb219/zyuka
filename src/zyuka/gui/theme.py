"""Brand theme for the Streamlit app.

Colours mirror the dawn-arc logo: deep teal (``#083344``) for primary
actions and headings, a warmer teal (``#0F766E``) for secondary accents,
and amber (``#F59E0B``) for the rising-seed highlight used sparingly on
positive states. CSS is kept short — Streamlit's own layout already does
most of the heavy lifting; we only reach for custom rules where defaults
read as generic or hinder Fitts/Hick heuristics.
"""

from __future__ import annotations

import streamlit as st

PRIMARY = "#083344"
PRIMARY_SOFT = "#0F766E"
ACCENT = "#F59E0B"
ACCENT_SOFT = "#FBBF24"
SURFACE = "#F8FAFC"
MUTED = "#64748B"

_CUSTOM_CSS = f"""
<style>
:root {{
    --zyuka-primary: {PRIMARY};
    --zyuka-primary-soft: {PRIMARY_SOFT};
    --zyuka-accent: {ACCENT};
    --zyuka-accent-soft: {ACCENT_SOFT};
    --zyuka-muted: {MUTED};
    --zyuka-surface: {SURFACE};
}}

h1, h2, h3, h4 {{
    color: var(--zyuka-primary);
    letter-spacing: -0.01em;
}}

h1 {{ font-weight: 700; }}

/* Primary buttons: taller + firmer colour to satisfy Fitts and improve affordance. */
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {{
    background-color: var(--zyuka-primary);
    color: #FFFFFF;
    border: 1px solid var(--zyuka-primary);
    padding: 0.55rem 1.1rem;
    font-weight: 600;
    border-radius: 8px;
}}

.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {{
    background-color: var(--zyuka-primary-soft);
    border-color: var(--zyuka-primary-soft);
    color: #FFFFFF;
}}

.stButton > button[kind="secondary"],
.stDownloadButton > button[kind="secondary"] {{
    border-radius: 8px;
    padding: 0.5rem 1rem;
}}

/* Alerts: tighten padding so stacked messages don't dominate the viewport. */
div[data-testid="stAlert"] {{
    border-radius: 10px;
}}

/* Dataframe container: subtle border reads as a surface, not a block. */
div[data-testid="stDataFrame"] {{
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 2px;
}}

/* Sidebar branding block. */
.zyuka-brand {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid #E2E8F0;
    margin-bottom: 0.75rem;
}}
.zyuka-brand .mark {{
    font-size: 1.3rem;
}}
.zyuka-brand .wordmark {{
    font-weight: 700;
    color: var(--zyuka-primary);
    letter-spacing: -0.02em;
    font-size: 1.1rem;
}}

/* Workflow status card used on the home dashboard. */
.zyuka-step {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.55rem 0.8rem;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    margin-bottom: 0.5rem;
    background: var(--zyuka-surface);
}}
.zyuka-step.done {{ border-color: {PRIMARY_SOFT}; background: #ECFDF5; }}
.zyuka-step.pending {{ opacity: 0.85; }}
.zyuka-step .dot {{
    width: 10px; height: 10px; border-radius: 50%;
    background: #CBD5E1; flex-shrink: 0;
}}
.zyuka-step.done .dot {{ background: {PRIMARY_SOFT}; }}
.zyuka-step .label {{ font-weight: 600; color: var(--zyuka-primary); }}
.zyuka-step .hint {{ color: var(--zyuka-muted); font-size: 0.85rem; margin-left: auto; }}

.zyuka-callout {{
    border-left: 3px solid var(--zyuka-accent);
    padding: 0.75rem 1rem;
    background: #FFFBEB;
    border-radius: 0 10px 10px 0;
    margin: 0.5rem 0 1rem 0;
}}
</style>
"""


def apply_theme() -> None:
    """Inject the custom CSS once per page load."""

    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)
