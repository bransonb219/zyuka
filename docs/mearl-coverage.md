# MEARL coverage and roadmap

Zyuka positions itself as a local-first toolkit for **Monitoring, Evaluation,
Accountability, Research and Learning**. This page records where each pillar
stands today and the staged plan for the gaps, so M&E officers choosing a
tool can make an informed decision rather than relying on marketing claims.

## Scope status

| Pillar | Status | What is in v0.1.0 | Gap |
| --- | --- | --- | --- |
| Monitoring | Shipped | Data quality checks (duplicates, missingness, outliers, constraint & skip-logic violations, interview duration, enumerator performance). Round tagging (baseline/midline/endline). | Live dashboards during fieldwork. Streaming enumerator feedback. |
| Evaluation | Shipped | Indicator engine (count, count_unique, proportion, mean, median, sum, ratio) with disaggregations, longitudinal change vs baseline, traffic-light status, Excel IPTT and self-contained HTML report. | Sampling-weighted analysis, qualitative-data coding, mixed-methods merging. |
| Accountability | Planned | Audit log (hash-chained), data-subject access and erasure (Zambia DPA), consent check. | Complaints & feedback mechanism (CFM) intake, response tracking, resolution SLAs. Beneficiary callback logs. |
| Research | Partial | Synthetic data generation, outlier detection, PII scanner (NRC, phone, email, GPS, DOB, sensitive attributes). | Study-design helpers (power calculations, sample size, sampling frames). Qualitative coding workflow. Research-ethics / informed-consent template library. |
| Learning | Planned | — | Learning briefs (what worked / what didn't / what next), after-action review templates, reflection prompt library, lessons-learned repository with searchable tags. |

## Standards and frameworks the toolkit aligns with

Zyuka's design is informed by widely used M&E and humanitarian standards. The
toolkit does not certify compliance — the user organisation remains the data
controller and the reporting body — but it structures outputs so that
compliance work is cheaper.

- **OECD-DAC evaluation criteria** — relevance, coherence, effectiveness,
  efficiency, impact, sustainability. Reports surface these as headings when
  the logframe is written against them.
- **Core Humanitarian Standard (CHS) commitments** — informs the planned
  Accountability module (complaints handling, participation, information
  sharing).
- **IATI** (International Aid Transparency Initiative) — the IPTT structure
  is designed to export as an IATI-ready table once the final mapping is in
  place (roadmap).
- **Zambia Data Protection Act (No. 3 of 2021)** and **GDPR** principles —
  pseudonymisation, minimisation, subject rights, retention, audit.

## Staged plan

### Phase 1 — Harden what exists (now)

- Windows end-to-end dogfood (in progress).
- Streamlit GUI polish, shared state, brand.
- PyPI publication.
- Screenshot-rich README and quickstart.

### Phase 2 — Accountability (v0.2)

- `zyuka feedback` command and GUI page: intake form for complaints and
  feedback; classification (safeguarding / service-delivery / information /
  praise); response tracking with SLA; linked audit entries.
- CHS-aligned accountability report block for the HTML report.
- Optional SMS/email bridge (local-only; no third-party sync).

### Phase 3 — Learning (v0.3)

- `zyuka learn` templates: learning brief, after-action review, lessons
  log. Markdown-first so they diff cleanly.
- Searchable lessons repository keyed to outcome/output codes.
- Reflection prompts attached to indicator traffic-light status
  ("off track — what did we learn?").

### Phase 4 — Research (v0.4)

- Sample-size / power calculator for common designs.
- Study-design scaffolds: cross-sectional, pre/post, difference-in-differences.
- Qualitative-coding workflow: thematic codes linked to interview transcripts
  with PII protection intact.

### Phase 5 — Standards integrations (v0.5)

- IATI export from the IPTT.
- OECD-DAC criteria auto-mapping in logframe templates.
- CHS self-assessment checklist generator.

## Non-goals

To keep Zyuka honest and installable in one command, the following are out
of scope indefinitely:

- Cloud sync, multi-tenant hosting, or shared databases.
- Real-time collaborative editing.
- Replacing a fully fledged database (PostgreSQL, SQL Server).
- Case-management systems (health records, child protection).
- Replacing Kobo / ODK / SurveyCTO for data collection.

Zyuka picks up where collection platforms stop and donor reports begin.
