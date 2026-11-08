# Linga — Privacy-first M&E Toolkit

> *Linga* (chiTonga / chiNyanja): a protective stockade or fortress. Linga guards
> beneficiary data while turning raw survey exports into clean data, indicators
> and donor-ready reports.

Linga is an **open-source, local-first** Monitoring & Evaluation toolkit for
NGOs, government programmes and researchers in Zambia and the region. It:

- Runs locally. No server, no uploads, no telemetry, no CDN assets.
- Checks data quality from KoboToolbox / ODK exports.
- Scans for personally identifiable information (PII) and sensitive fields.
- Pseudonymises, minimises and generalises data before analysis.
- Computes logframe indicators across baseline / midline / endline rounds.
- Produces a single self-contained HTML report and an Excel IPTT workbook.
- Helps organisations comply with Zambia's **Data Protection Act No. 3 of 2021**
  and follow good practice under the **Cyber Security Act No. 3 of 2025**.

**Honest positioning.** Linga *enables* compliance. Your organisation remains
the data controller. See [docs/data-protection.md](docs/data-protection.md).

## Install

```bash
pipx install linga-me
# or, for development
pip install -e ".[dev]"
```

Linga requires Python 3.11+. It works on Windows, macOS and Linux.

## Quick start

```bash
# Try the full pipeline on synthetic data
linga demo --open

# Initialise a project in the current folder
linga init

# Run the full pipeline on your own survey exports
linga run --round baseline

# Local Streamlit GUI (localhost only)
linga gui
```

See [docs/quickstart.md](docs/quickstart.md) for the full walkthrough.

## What the pipeline does

```
check  →  scan  →  protect  →  compute  →  report  →  audit
```

- **check** — duplicates, missingness, outliers, constraint & skip-logic
  violations, interview duration, enumerator performance.
- **scan** — detects Zambian NRCs, phone numbers, emails, GPS points,
  dates of birth, names, and sensitive fields (sex, health, HIV status,
  disability, marital status, ethnicity, religion, political opinion,
  biometrics).
- **protect** — keyed HMAC-SHA256 pseudonymisation, column minimisation,
  generalisation (age bands, GPS rounding, dates → month), small-cell
  suppression (default *n* < 5 → `<5`), with secondary suppression.
- **compute** — indicator engine with a safe expression parser (no `eval`),
  disaggregation, longitudinal change and traffic-light status.
- **report** — single self-contained HTML + Excel IPTT workbook.
- **audit** — append-only, hash-chained JSONL.

## Non-negotiable design rules

1. **Local-first.** All processing happens on the user's machine.
2. **Offline after install.** No CDN assets, web fonts or remote JS.
3. **Zero telemetry.** Streamlit runs with `browser.gatherUsageStats = false`
   bound to `localhost`.
4. **Privacy by default.** Identifiers are pseudonymised; unmapped columns
   dropped unless explicitly opted out.
5. **Never log or display personal data.** Logs, audit and GUI previews show
   column names, counts, hashes and masked samples only (e.g. `0977****12`).
6. **Keys stay with the organisation.** Keys are never written into datasets,
   reports, logs, configs or the repo.

## Repository layout

```
src/linga/
  ingest/      kobo.py odk.py xlsform.py rounds.py
  quality/     duplicates.py missing.py outliers.py constraints.py ...
  privacy/     patterns.py scanner.py pseudonymise.py minimise.py ...
  indicators/  expressions.py engine.py disaggregate.py ...
  reports/     html.py excel.py charts.py summary.py templates/
  security/    crypto.py keys.py audit.py sanitize.py
  rights/      subject.py retention.py
  compliance/  dpia.py consent.py templates/
  gui/         app.py pages/
  pipeline.py  demo.py synthetic.py cli.py config.py errors.py
```

## Development

```bash
pip install -e ".[dev]"
pre-commit install

pytest --cov=linga
ruff check . && ruff format --check .
mypy src
bandit -q -r src
pip-audit
```

Coverage target: ≥85% on `privacy/`, `security/`, `indicators/`.

## Author

Branson Bazungu — <bbazungu@gmail.com>

## Licence

Apache-2.0. See [LICENSE](LICENSE).
