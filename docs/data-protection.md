# Data protection in Linga

This note maps Linga's features to the principles of the Zambia Data
Protection Act No. 3 of 2021 (DPA). It is **not** legal advice; use it to
hold a conversation with your Data Protection Officer.

## What Linga is

A **local-first** toolkit that runs on the user's laptop. It never uploads
your data, never contacts a server, and has no telemetry.

## What Linga is not

A compliance guarantee. Your organisation remains the **data controller**
and is responsible for:

- lawful basis and consent collection in your survey instruments,
- registration with the Data Protection Commissioner where required,
- breach notification within 72 hours,
- staff training and physical security.

## Principle-by-principle mapping

| DPA principle | Linga feature |
|---|---|
| Lawfulness, fairness and transparency | `linga docs consent` warns on missing consent; DPIA starter documents processing |
| Purpose limitation | `logframe.yml` defines what is measured; `linga protect --minimise` drops columns the logframe doesn't reference |
| Data minimisation | Pseudonymisation of identifiers; `drop_free_text: true` by default |
| Accuracy | Quality checks (`linga check`) flag duplicates, outliers, constraint violations |
| Storage limitation | `retention_days` in `linga.yml`; `linga retention check` and `linga retention purge` |
| Integrity and confidentiality | AES-GCM encryption via `--encrypt`; keys never written into datasets, reports, logs or the repo |
| Accountability | Hash-chained audit log (`linga audit show` / `verify`) |

## Data subject rights

- **Access** — `linga subject find --id <raw>` hashes the raw identifier
  with the project key and reports which protected files contain that
  person.
- **Erasure** — `linga subject erase --id <raw>` removes those rows and
  records the action in the audit log.

Raw identifiers are *never* stored by Linga once protection has run; the
project key is required to run either command.

## Cross-border transfer

Linga does not transfer data anywhere. If your organisation uses cloud
storage or shares reports internationally, the DPA's cross-border rules
apply to *that* transfer, not to Linga.

## Breach response

If a protected dataset is exposed:

1. The impact depends on whether the attacker also has the project key.
   Without it, pseudonyms cannot be reversed by Linga's design.
2. Use `linga audit verify` to check whether the audit log has been
   tampered with.
3. Follow your organisation's breach-response procedure and notify the
   Commissioner within 72 hours where required by the DPA.
