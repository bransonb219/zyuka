# Zyuka — Privacy-first M&E Toolkit

[![Release](https://img.shields.io/github/v/release/bransonb219/zyuka?label=release&color=blue)](https://github.com/bransonb219/zyuka/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/bransonb219/zyuka/ci.yml?branch=master&label=CI)](https://github.com/bransonb219/zyuka/actions/workflows/ci.yml)
[![Licence](https://img.shields.io/github/license/bransonb219/zyuka?color=green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20windows-lightgrey)](.github/workflows/ci.yml)

> **Zyuka** (pronounced *zyoo-KAH*) — from *Chizyuka*, a Tonga name borne by the
> author. The toolkit guards beneficiary data while turning raw survey exports
> into clean data, indicators and donor-ready reports.

Zyuka is an **open-source, local-first** Monitoring & Evaluation toolkit for
NGOs, government programmes and researchers in Zambia and the region. It:

- Runs locally. No server, no uploads, no telemetry, no CDN assets.
- Checks data quality from KoboToolbox / ODK exports.
- Scans for personally identifiable information (PII) and sensitive fields.
- Pseudonymises, minimises and generalises data before analysis.
- Computes logframe indicators across baseline / midline / endline rounds.
- Produces a single self-contained HTML report and an Excel IPTT workbook.
- Helps organisations comply with Zambia's **Data Protection Act No. 3 of 2021**
  and follow good practice under the **Cyber Security Act No. 3 of 2025**.

**Honest positioning.** Zyuka *enables* compliance. Your organisation remains
the data controller. See [docs/data-protection.md](docs/data-protection.md).

## Install

```bash
pipx install zyuka
# or, for development
pip install -e ".[dev]"
```

Zyuka requires Python 3.11+. It works on Windows, macOS and Linux.

## Quick start

```bash
# Try the full pipeline on synthetic data
zyuka demo --open

# Initialise a project in the current folder
zyuka init

# Run the full pipeline on your own survey exports
zyuka run --round baseline

# Local Streamlit GUI (localhost only)
zyuka gui
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
src/zyuka/
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

pytest --cov=zyuka
ruff check . && ruff format --check .
mypy src
bandit -q -r src
pip-audit
```

Coverage target: ≥85% on `privacy/`, `security/`, `indicators/`.

## Author

Branson Bazungu — <bbazungu@gmail.com>

## Licence

Zyuka is released under the **GNU Affero General Public License v3.0 or later**
(AGPL-3.0-or-later). See [LICENSE](LICENSE) for the full text.

Copyright © 2026 Branson Bazungu.

### What AGPL-3.0 means for you

- **NGOs, researchers, public-sector programmes, individuals:** free to use,
  modify and self-host Zyuka without restriction, provided derivative works
  and network-service deployments publish their source under the same licence.
- **Commercial / proprietary use:** if AGPL-3.0's copyleft reach-through is
  incompatible with your product or hosted service, a **commercial licence** is
  available from the author. Contact <bbazungu@gmail.com>.

The author retains the right to re-license this code under commercial terms;
contributions by third parties are accepted under the same AGPL-3.0-or-later
licence unless a Contributor Licence Agreement is signed.
