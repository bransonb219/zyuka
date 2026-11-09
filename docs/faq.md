# FAQ

## Does Zyuka upload my data anywhere?

No. Zyuka is local-first: no server component, no telemetry, no CDN
assets in the reports. The Streamlit GUI binds to `127.0.0.1` only.

## Does installing Zyuka make my organisation compliant with the DPA?

No. Zyuka *enables* compliance but your organisation remains the data
controller. See [data-protection.md](data-protection.md) for the
principle-by-principle mapping.

## Where are keys stored?

Wherever you point `key_path:` in `zyuka.yml`. The recommended location
is **outside** the project directory, for example
`~/.zyuka-keys/<programme>.key`. Zyuka never writes the key into
datasets, reports, logs or config.

## What happens if I lose my key?

Zyuka uses the key for two things:

1. Deterministic HMAC-SHA256 pseudonymisation of identifiers.
2. AES-GCM encryption of `--encrypt` outputs.

Without the key you cannot honour subject requests on protected
datasets (because the identifier → pseudonym mapping lives in the key)
and you cannot decrypt `.enc` files. Back up the key out-of-band.

## Can I rotate keys?

Yes: `zyuka key rotate OLD NEW --data <dir>`. The pseudonymised
identifiers in every CSV under `<dir>` are re-hashed with the new key
and a mapping manifest is written so you can prove continuity.

## My survey has `select_multiple` fields. Does Zyuka handle them?

Yes, both space-separated and one-hot layouts are handled by the Kobo
and ODK ingest modules. In indicator expressions use
`selected(column, 'value')`.

## Can I use Zyuka with REDCap / SurveyCTO / CommCare?

The ingest layer is tested with Kobo and ODK. REDCap/SurveyCTO/CommCare
exports can be loaded if you convert them to a Kobo-like CSV first.
Mapping those formats natively is on the roadmap.

## How big a dataset can Zyuka handle?

The whole pipeline runs in memory via pandas. A laptop with 8 GB RAM
should handle 100k rows comfortably. Larger datasets are feasible but
out-of-scope for the first release.

## Does Zyuka work offline?

Yes. After `pipx install zyuka` the toolkit never contacts the
network. Reports are self-contained single HTML files with inline SVG
charts.

## Where do I report a security issue?

See `SECURITY.md`. Do not open a public issue.

## Who maintains Zyuka?

Branson Bazungu, Zambia — <bbazungu@gmail.com>.
