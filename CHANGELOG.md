# Changelog

All notable changes to Zyuka will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-11-19

### Added

- **Quality**: detect → clean → remember pipeline with a Streamlit "Clean
  and approve" page and `zyuka clean` CLI. Approved rules persist to
  `cleaning_rules.json` and replay on every subsequent round.
- **EDA**: column-level profile, auto-advisor suggesting analyses to run,
  statistical test dispatcher (t-test, Mann-Whitney, chi-square, ANOVA,
  correlation), GUI and CLI entry points.
- **Advanced modelling**: PCA, VIF, Breusch-Pagan, classifier evaluation
  and cluster profiling.
- **Qualitative**: TF-IDF theme extraction, hierarchical response
  clustering, lexicon sentiment with negation handling, and a draft
  code-book builder.
- **Warehouse**: per-round snapshots saved to `outputs/warehouse/`, a
  cross-round diff (row counts, added / dropped columns, missingness
  drift, numeric mean drift) surfaced in the HTML report, plus a
  `zyuka warehouse list|show|compare` CLI.
- **Evaluation payload on each indicator**: Wilson interval for
  proportions, t-interval for means, per-disaggregation equity gap,
  linear trajectory with time-to-target, and a pre/post significance
  test (two-proportion z or Welch's t). Logframe files can now carry
  optional OECD-DAC criteria and per-indicator means_of_verification
  and assumptions; all surface in the HTML report when populated.
- **GUI**: workflow dashboard home page, brand assets + sidebar polish,
  shared project state across pages, MEARL coverage card, and empty /
  error states on every page.

### Fixed

- Demo logframe now references leaf column names (e.g.
  `has_income_source`) instead of Kobo group-prefixed names so the
  indicator engine computes every demo indicator cleanly.
- `zyuka docs consent` strips group prefixes on read so
  `consent_column` behaves the same against raw and ingested CSVs.
- `drop_duplicate_rows` tolerates rows already removed by an earlier
  rule in the same clean run.

### Changed

- Brand refresh (teal + amber palette, dawn-arc mark with 28° tilt),
  light / dark / mono asset set, `<picture>` switching.
- CI bandit step now fails only on medium+ severity findings;
  intentional subprocess calls in the GUI file-manager helper no
  longer block releases.

## [0.1.0] — 2026-11-09

First public release.

Released under **AGPL-3.0-or-later**. Commercial licensing available from the
author on request.

### Added

- **Scaffold**: packaging via `pyproject.toml` (hatchling), CI workflow,
  pre-commit, synthetic 3-round dataset generator, `ZyukaConfig` /
  `LogframeConfig` pydantic models, plain-language `ZyukaError` hierarchy.
- **Ingest**: Kobo + ODK CSV / XLSX readers, XLSForm parser, multi-round
  loader that tags each dataset with its round.
- **Quality**: duplicate detection by UUID and fuzzy identity, per-column
  and per-enumerator missingness, IQR + z-score outliers, constraint and
  skip-logic violations from XLSForm, interview duration checks,
  enumerator performance summary.
- **Privacy**: Zambian NRC / phone regex scanner, keyed HMAC-SHA256
  pseudonymisation, column minimisation driven by the logframe, age-band /
  DOB / GPS / date generalisation, small-cell suppression (default *n* < 5
  → `<5`) with secondary suppression.
- **Security**: scrypt-wrapped key generation and rotation, key fingerprint,
  AES-GCM file encryption (`--encrypt`), CSV/Excel injection sanitiser,
  hash-chained append-only JSONL audit log with `show` / `verify`.
- **Indicators**: AST-based safe expression parser (no `eval`), engine
  supporting `count`, `count_unique`, `proportion`, `mean`, `median`,
  `sum`, `ratio`, disaggregation by any categorical, longitudinal change
  and traffic-light status, plain-language validator with "did you mean?"
  suggestions.
- **Reports**: single self-contained HTML report with inline SVG charts and
  print-friendly CSS; Excel IPTT workbook with per-round values, targets,
  percent of target, status, disaggregation sheets and metadata.
- **Pipeline**: one-shot `zyuka run` orchestrating
  check → scan → protect → compute → report → audit; `zyuka demo`
  running the full pipeline on synthetic data; interactive `zyuka init`
  wizard.
- **Rights**: `zyuka subject find` / `erase` honouring access and
  erasure requests via pseudonymised lookup; `zyuka retention check` /
  `purge` for the configured retention window.
- **Compliance**: DPIA starter in Markdown + HTML pre-filled from scan
  results; `zyuka docs consent` reports and optionally filters
  non-consenting rows.
- **GUI**: local Streamlit app bound to `127.0.0.1` with telemetry off,
  masked previews on every page.
- **Docs**: quickstart, logframe guide, GUI guide, data-protection
  mapping, FAQ.

### Design rules enforced

- Local-first, offline after install, zero telemetry.
- Keys never written to datasets, reports, logs or the repo.
- Raw PII never written to logs, errors, audit entries or GUI previews
  (hypothesis-tested).
- Synthetic data only in the repo and tests.
