# Data protection in Zyuka

This note maps Zyuka's features to the principles of the Zambia Data
Protection Act No. 3 of 2021 (DPA). It is **not** legal advice; use it to
hold a conversation with your Data Protection Officer.

## What Zyuka is

A **local-first** toolkit that runs on the user's laptop. It never uploads
your data, never contacts a server, and has no telemetry.

## What Zyuka is not

A compliance guarantee. Your organisation remains the **data controller**
and is responsible for:

- lawful basis and consent collection in your survey instruments,
- registration with the Data Protection Commissioner where required,
- breach notification within 72 hours,
- staff training and physical security.

## Principle-by-principle mapping

| DPA principle | Zyuka feature |
|---|---|
| Lawfulness, fairness and transparency | `zyuka docs consent` warns on missing consent; DPIA starter documents processing |
| Purpose limitation | `logframe.yml` defines what is measured; `zyuka protect --minimise` drops columns the logframe doesn't reference |
| Data minimisation | Pseudonymisation of identifiers; `drop_free_text: true` by default |
| Accuracy | Quality checks (`zyuka check`) flag duplicates, outliers, constraint violations |
| Storage limitation | `retention_days` in `zyuka.yml`; `zyuka retention check` and `zyuka retention purge` |
| Integrity and confidentiality | AES-GCM encryption via `--encrypt`; keys never written into datasets, reports, logs or the repo |
| Accountability | Hash-chained audit log (`zyuka audit show` / `verify`) |

## Data subject rights

- **Access** — `zyuka subject find --id <raw>` hashes the raw identifier
  with the project key and reports which protected files contain that
  person.
- **Erasure** — `zyuka subject erase --id <raw>` removes those rows and
  records the action in the audit log.

Raw identifiers are *never* stored by Zyuka once protection has run; the
project key is required to run either command.

## Cross-border transfer

Zyuka does not transfer data anywhere. If your organisation uses cloud
storage or shares reports internationally, the DPA's cross-border rules
apply to *that* transfer, not to Zyuka.

## Breach response

If a protected dataset is exposed:

1. The impact depends on whether the attacker also has the project key.
   Without it, pseudonyms cannot be reversed by Zyuka's design.
2. Use `zyuka audit verify` to check whether the audit log has been
   tampered with.
3. Follow your organisation's breach-response procedure and notify the
   Commissioner within 72 hours where required by the DPA.
