# EternalAI Console handoff

## Branch and scope

Work is isolated on `team/console`, based on `origin/plan-complete` at `7cc615a48d8378dcf781b4f7e3deb428c16654c7`. Every project change is inside `console/`. No backend files, protected refs, tags, Docker services, or clusters were changed. No push or merge into `plan-complete` was performed.

## Delivered

- Editorial landing page with documented architecture illustration and links into the read-only console.
- Overview, incidents and detail narrative, topology with 2D fallback and lazy 3D, approvals, safety, audit, and verified-results pages with direct routes.
- Typed adapters and a shared polling provider use only compatible observational GET routes through relative `/api/...` URLs. Polling is shared, pauses in hidden tabs, times out, marks partial/disconnected states, and labels retained stale values historical.
- Confidence appears only when `/status.calibration.show_probability` is true. No operational controls are exposed. Reports are rendered as text; no raw HTML is inserted.
- Topology uses returned service/dependency data; edges are explicitly not traffic. Overview score sparklines sample only numeric API scores, are bounded in memory, begin empty, and preserve gaps.
- Verified Results selects source-backed sections from `docs/CURRENT_NUMBERS.md`; labels and qualifiers are preserved, and that content is explicitly marked recorded rather than live telemetry.

The endpoint comparison and field mappings are in [docs/API_COMPATIBILITY.md](docs/API_COMPATIBILITY.md). The browser never receives a backend target or credential. Vite dev and preview proxy relative API paths, read `VITE_API_TARGET` server-side, default to `http://127.0.0.1:8000`, and strip `/api` before forwarding.

## Verification evidence

- `npm run test -- --run`: **15 tests passed** across 2 files.
- `npm run lint`: **passed** (`tsc --noEmit -p tsconfig.app.json`).
- `npm run build`: **passed**. Output: initial JS 361.12 kB (115.11 kB gzip); lazy score chart 289.00 kB (88.03 kB gzip); lazy 3D map 995.38 kB (280.81 kB gzip). Vite warns that the 3D chunk exceeds 500 kB; it is downloaded only when the 3D map is selected and pixel ratio is capped.
- Browser visual inspection: landing, disconnected Overview, incident empty state, topology fallback, and recorded Results at the available 1512×720 viewport. Results was refined from raw Markdown to readable, safely rendered text. Exact 1440×900, 1280×720, and 390×844 viewport emulation was unavailable in the connected browser control, so those dimensions were not separately verified.
- `npm run preview -- --host 127.0.0.1 --port 4180`: served a direct incident URL (`/console/incidents/example-id`) successfully and rendered the honest unavailable state. Preview was stopped after the check.
- Backend `/health` was not reachable during preflight. No backend or Docker stack was started. **Live API integration was not verified**, no operational data was displayed, and no live screenshots were captured. No source incident was created.

## Presentation run

Use Node.js 24.11.1 and npm 11.6.2. In `console/`, run:

```powershell
npm ci
npm run test -- --run
npm run lint
npm run build
npm run preview
```

For a presentation, build and preview with `npm run build && npm run preview`, not the dev server. Start the backend separately only if live telemetry is desired; confirm it is already running and reachable through the configured proxy. A deployed static build needs a same-origin reverse proxy. Vite preview is not production hosting. Keep one browser tab open; 3D is lazy loaded. No environment credentials are needed by this frontend.

## Limitations

- The API was unreachable during this implementation, so telemetry contract behavior is tested with test-only MSW fixtures but was not exercised against a live backend.
- Incident and audit lists have no pagination contract in the shared API; client filters and displayed counts apply only to returned records. Incident detail is selected from the returned list.
- The common approvals API does not expose an expiry timestamp, so there is no countdown. The console links no external approval destination and offers no approve/reject controls.
- The only sampled chart metric is a service `score` when the API returns a finite number; no API time-series endpoint was found.
- The recorded-results page is a curated source excerpt and does not create or validate new evaluation evidence.
