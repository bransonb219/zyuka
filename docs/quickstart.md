# Quickstart

This walkthrough takes 10 minutes and ends with a finished HTML report and
Excel IPTT generated entirely on your laptop.

## 1. Install

```bash
pipx install linga-me
# or clone the repo and
pip install -e ".[dev]"
```

Python 3.11+ is required. Works on Windows, macOS and Linux.

## 2. Try the demo

```bash
linga demo --open
```

This:

1. Generates a synthetic 3-round dataset under `./linga-demo/data/`.
2. Writes `linga.yml` and `logframe.yml` into `./linga-demo/`.
3. Creates a project key under `./linga-demo/.linga-keys/demo.key`.
4. Runs the full pipeline (check → scan → protect → compute → report).
5. Opens `./linga-demo/outputs/report/report.html` in your browser.

Nothing leaves your machine. The key file is stored outside the data
directory and is never written into the report.

## 3. Start your own project

```bash
mkdir my-programme && cd my-programme
linga init          # answer the interactive prompts
linga key generate ~/.linga-keys/my-programme.key
```

Edit `logframe.yml` to describe your indicators (see
[logframe-guide.md](logframe-guide.md)). Then place your Kobo/ODK CSV
exports under `data/`, named like `survey_baseline.csv`,
`survey_midline.csv`, `survey_endline.csv`.

## 4. Run the pipeline

```bash
linga run --round baseline
linga run --round midline
linga run --round endline
```

You can also pass `--encrypt` to produce `.enc` copies and `--open` to
automatically open the report.

## 5. Use the GUI

```bash
linga gui
```

Opens on `http://127.0.0.1:8501` only. The GUI shows masked previews only
and runs the same pipeline as the CLI.

## 6. Verify the audit log

Every mutating step appends a hash-chained entry.

```bash
linga audit show
linga audit verify
```

## 7. Honour subject rights

```bash
linga subject find --id "100001/10/1"
linga subject erase --id "100001/10/1"
```

Linga hashes the identifier with your project key before searching;
the raw value never touches a protected file.
