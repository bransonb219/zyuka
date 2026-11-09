# Changelog

All notable changes to Zyuka will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
