# Dashboard charts preview

A standalone page that exercises `charts.py` and `explain_words.py` on **synthetic sample data
only**. It is not connected to the live dashboard, the brain API, or any network service.

## Run it

```powershell
cd "$HOME\eAI-mihir"
.\.venv\Scripts\python.exe dashboard\preview\preview_app.py
```

Open http://127.0.0.1:8071 in a browser. Stop the server with `Ctrl+C`.

If port 8071 is already in use on your machine, edit the `port=8071` argument at the bottom of
`preview_app.py` to a free port and note the port you used in your hand-back.

## What it shows

- A banner confirming the page uses **synthetic sample data**, not live telemetry.
- A language selector (English / हिन्दी), a service selector, and a tick slider (0-59).
- The per-service chart for the selected service, built from `sample_services.json` up to the
  chosen tick.
- The plain-language sentences `explain_service` produces for that service at the latest shown
  tick.
- The incident-statistics table, computed once from `sample_incidents.json`.

## Data

`sample_services.json` and `sample_incidents.json` are generated deterministically by
`make_samples.py` (no randomness; running it twice produces byte-identical files). Regenerate
with:

```powershell
.\.venv\Scripts\python.exe dashboard\preview\make_samples.py
```

Both files start with a `"label"` field stating they are synthetic, hand-made data, never real
telemetry.
