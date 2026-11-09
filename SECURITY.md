# Security policy

## Reporting a vulnerability

If you believe you have found a security vulnerability in Zyuka, please email
**bbazungu@gmail.com** with details. Do **not** open a public issue.

Please include:

- A description of the issue and its potential impact.
- Steps to reproduce (synthetic or redacted inputs only).
- Any suggested fix, if known.

You will receive a response within 7 days.

## Scope

Zyuka is a local-first toolkit; there is no server component to attack.
Vulnerabilities we care about:

- Cryptography misuse (keys leaking into logs, outputs, errors, manifests).
- PII leakage (raw values appearing in previews, logs, reports, audit).
- Expression-parser sandbox escape (indicator filters or XLSForm rules).
- CSV / Excel formula injection in exported workbooks.
- Dependency vulnerabilities flagged by `pip-audit`.
- Audit-log tampering that is not detected by `zyuka audit verify`.

## Threat model (short)

Zyuka assumes:

- The host machine is trusted. If it is compromised, Zyuka cannot protect data.
- The key file lives **outside** the project folder and is backed up out of
  band. If the key is lost, pseudonymisation cannot be reversed by design.
- The user organisation is the **data controller** under Zambia's Data
  Protection Act No. 3 of 2021. Zyuka *enables* compliance; it does not
  provide it.

## Cryptography

- HMAC-SHA256 for deterministic pseudonymisation.
- AES-GCM for file encryption.
- scrypt for password-wrapped key files.
- A fixed-sentinel HMAC is stored as a key *fingerprint* so other outputs can
  check they were produced with a matching key — the key itself is never stored.
