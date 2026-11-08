# GUI guide

The Linga GUI is a local Streamlit app. It is launched by the CLI and
binds to `127.0.0.1` only — it cannot be reached from another machine.
Telemetry is disabled both in the CLI launcher and inside the app.

## Launch

```bash
linga gui
```

Opens on `http://127.0.0.1:8501`. Close the terminal window to shut it
down.

## Pages

### Home

Shows the project directory and whether `linga.yml` is present. Reminds
you that nothing leaves your machine and that raw PII is never shown in
the GUI.

### Upload and quality

Upload a Kobo or ODK export. The dataset is **previewed with masked
columns**: identifiers are shown as `0*******6` so the raw values are
not visible on screen. Click **Run quality checks** to see duplicates,
missingness, outliers, duration issues and enumerator performance.

### Privacy scan

Upload a dataset and get per-column risk levels (`high` / `medium` /
`low`) with the signals that triggered each one and the suggested
action.

### Protect

Upload a dataset and press **Apply protection**. The result is shown
with the same masking rules. Download the protected CSV and the
protection manifest.

### Indicators

Shows the logframe parsed from `logframe.yml`. Edit the file on disk;
the GUI re-reads it on each page load.

### Reports

Preview the last generated HTML report inline and download the HTML or
Excel IPTT.

### Audit

Lists every audit entry with timestamp, command, row/column counts and
a short hash. A banner confirms whether the hash chain verifies.

### Subject requests

Enter a raw identifier (hidden-input field). The GUI hashes it with the
project key before searching the protected files — the raw value never
touches disk. Erasure requires ticking a confirmation box.

## Safety-belt behaviour

- The CLI launcher sets `--browser.gatherUsageStats false` and
  `--server.address 127.0.0.1`.
- The app additionally calls `st.set_option("browser.gatherUsageStats",
  False)` so a developer running `streamlit run src/linga/gui/app.py`
  still gets telemetry off.
- Any column whose name hints at PII (`name`, `nrc`, `phone`, `email`,
  `address`, `gps`, `lat`, `lon`, `dob`, `birth`, `notes`, …) is masked
  in every preview.
