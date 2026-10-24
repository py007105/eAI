# EternalAI Console handoff

## Integration follow-up — 25 October 2026, 01:36 IST

**Live integration remains blocked, not verified.** Direct `GET http://127.0.0.1:8000/health` was unreachable. Docker inspection found no running containers and existing stopped `eai` containers. The documented normal startup command is `docker compose up -d` from the repository root. This worktree has no `.env` (existence checked only), and `CHAOS_TOKEN` is absent from the process environment; Compose requires a real value for that variable. `ETERNALAI_APPROVAL_TOKEN` is also absent, but is not needed by the read-only frontend. No secret file was read or copied. No backend, Docker service, fault, or operational action was started. The next live check requires owner-provided backend configuration and the shared Docker lock before the normal startup command; do not substitute defaults or recreate the saved stack speculatively.

Runtime fix and verification tooling: `b7ee5d2def943e40bb2b02b8f307ea8e62d821a1`. Failed polling now immediately suppresses retained current values; confidence requires a fresh successful permission response; all failed endpoints report disconnected; unmount aborts pending requests. Partial/recovery and six-second stale behavior are verified in tests only, using fixtures restricted to tests.

| Check | Observed result |
| --- | --- |
| Full frontend suite | `npm run test -- --run`: 16 passed, 2 test files; 25 October 01:33 IST |
| Type checking and production build | `npm run lint` and `npm run build` passed; optional lazy 3D chunk still generates the >500 kB warning |
| Development and preview API routes | Both `/api/health`, `/api/status`, `/api/services`, `/api/incidents`, `/api/approvals`, `/api/audit` returned HTTP 500 text/plain with the backend unavailable. They did not fall through to the SPA. Successful forwarding/response mapping is still unverified live. |
| Browser routes | 54 observations: 9 routes in each server mode at all 3 requested sizes; zero horizontal-overflow or non-GET failures. Includes all console pages and an unavailable incident deep link. |
| Polling | Two actual `/api/status` retries during each 4.3-second observation, in both development and preview, approximately two seconds apart. |
| Responsive visual inspection | Exact 1440×900, 1280×720, 390×844 viewports tested; mobile navigation exercised. Landing, Overview, and topology screenshots saved; mobile Overview/topology and desktop Landing/Overview visually inspected. Reduced-motion preference enabled. |
| Actual incident, populated services, 3D service selection | Blocked by unavailable API; no incident created and no populated screenshot fabricated. Keyboard-only navigation and a live WebGL context-loss scenario were not separately exercised in this follow-up. |

Latest execution began **25 October 2026 01:34:31 IST**. Machine-readable observations and nine screenshots are in [evidence/2026-10-24T20-04-31-780Z/report.json](evidence/2026-10-24T20-04-31-780Z/report.json). Directory and JSON timestamps use UTC. Screenshots are real **disconnected frontend** captures, not live backend evidence; backend ref is unknown/null, so neither `demo-stable-1` nor `plan-complete` can be attributed to them. The earlier [first execution](evidence/2026-10-24T19-58-21-602Z/report.json) ran with uncommitted fixes; its recorded HEAD is not an exact runtime revision. Prefer the latest execution, which used the committed runtime fix. No screenshots contain credentials or operational payloads.

Reproduce from `D:\eAI\eAI-console\console`:

```powershell
npm ci
npm run test -- --run
npm run lint
npm run build
node scripts/verify-browser.mjs
npm run preview -- --host 127.0.0.1 --port 4180
```

Open `http://127.0.0.1:4180`; for development use `npm run dev -- --port 4173`. Both use the default server-side API target `http://127.0.0.1:8000`; an existing backend elsewhere can be selected with `$env:VITE_API_TARGET='http://127.0.0.1:8000'` before starting Vite. Browser verification uses installed Brave and starts/stops only its own frontend processes; set `CONSOLE_BROWSER_PATH` for another installed Chromium executable. Once the normally configured backend is available, repeat the script and inspect actual returned incidents without creating one. Partial/stale/recovery checks remain explicitly test-only until observed with the real API. The previous implementation notes below are historical; the exact-viewport limitation is superseded by this follow-up.

## Branch and scope

Work is isolated on `team/console`, based on `origin/plan-complete` at `7cc615a48d8378dcf781b4f7e3deb428c16654c7`. Every project change is inside `console/`. No backend files, protected refs, tags, Docker services, or clusters were changed. No merge or push to `plan-complete` was performed.

The implementation is in commit `87bffad` (`Console: build read-only landing and operations UI`). The initial documentation and handoff are in `5286940` (`Console: document API contract and presentation handoff`). This handoff update records the finished checks and visual review.

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
