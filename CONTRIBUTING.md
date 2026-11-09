# Contributing to Zyuka

Thanks for your interest. Zyuka is built for M&E officers in low-bandwidth,
privacy-sensitive settings. All contributions should keep that context front of
mind.

## Ground rules

1. **Synthetic data only.** Never commit real survey exports, even redacted.
   The `Faker`-based generator in `zyuka.synthetic` is the only approved source
   of sample data.
2. **No network calls** from the core pipeline. No telemetry, no analytics, no
   update pings. Everything must work on an offline laptop.
3. **No personal data in logs, errors or audit entries.** Columns, counts,
   masked samples and hashes only.
4. **Plain commits.** Use conventional commits (`feat:`, `fix:`, `docs:`,
   `chore:`, `refactor:`, `test:`, `ci:`). No author trailers added by tools.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

## Before pushing

```bash
ruff check . && ruff format --check .
mypy src
pytest --cov=zyuka
bandit -q -r src
pip-audit
```

Coverage must stay ≥85% on `privacy/`, `security/`, and `indicators/`.

## Reporting a bug

Open an issue with: Zyuka version (`zyuka --version`), OS, the command you ran,
and the plain-language error you saw. Do **not** paste survey data.
