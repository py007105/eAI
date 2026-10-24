# EternalAI Console

A read-only landing page and operations console for inspecting service state, incidents, approvals, policy summaries, audit records, and recorded evaluation source material. The interface never invokes an operational action.

## Prerequisites

- Node.js 24.11.1 and npm 11.6.2 were used for this implementation.
- Install the exact pinned dependency tree with `npm ci`.
- For live telemetry, start the EternalAI API separately before opening the frontend. This project does not start or configure the backend.

## Run and verify

```powershell
npm ci
npm run dev
npm run test -- --run
npm run lint
npm run build
npm run preview
```

For a presentation, use `npm run build && npm run preview`, not the development server. Vite preview is only a local preview server, not production hosting. Keep one browser tab open; the 3D topology is lazy-loaded and caps pixel ratio.

## API target and deployment

The browser calls only relative `/api/...` paths. Vite dev and preview proxy these paths to `VITE_API_TARGET`, which is read by the server-side Vite config and defaults to `http://127.0.0.1:8000`; `/api` is stripped before forwarding. Set `VITE_API_TARGET` in the server environment for a different backend address. The browser receives no credentials or cross-origin target. A deployed static build needs a same-origin reverse proxy configured outside this project. Do not treat `vite preview` as production hosting.

Only common observational GET routes from `demo-stable-1` and `origin/plan-complete` are used: `/health` contract is documented but not enough for live freshness; `/status`, `/services`, `/incidents`, `/approvals`, and `/audit` provide the displayed data. Freshness is a six-second threshold and includes schema-valid responses from status, services, incidents, approvals, and audit; mixed failures are marked partial and expired values are historical. No approval, rejection, mode, kill-switch, reset, feedback, or fault-injection route is called. See [API compatibility](docs/API_COMPATIBILITY.md).

## Scope and limitations

Browser regression checks use pinned `@playwright/test` 1.56.1 and an existing Brave executable. After building, run `node scripts/verify-browser.mjs`. To use another installed Chromium browser, set `CONSOLE_BROWSER_PATH` to its executable. The script starts and stops only its own frontend servers on 4173 and 4180, tests three exact viewports, and writes real-response observations/screenshots under `evidence/`. It does not intercept responses, start the backend, or create incidents. Successful rendering while disconnected is not live API integration evidence.

- If the backend is stopped or an endpoint fails, current values are unavailable or explicitly historical. Missing fields are not converted into zero or healthy states.
- Service dependencies are shown from API topology; they do not imply traffic. When the API returns numeric service scores, Overview samples those real snapshots into a bounded in-memory sparkline; charts start empty and show gaps for unavailable samples.
- Incident details are selected from the returned incident list. The API does not provide list pagination, query filters, or approval expiry; filters are client-side over only returned records.
- Probabilities are displayed only when `/status.calibration.show_probability` is true.
- Static evaluation material is sourced from `docs/CURRENT_NUMBERS.md` and labeled as recorded results on its own page.
- This is read-only visibility, not an action console and not a remediation executor.
- Known limitation: live integration requires the backend to be independently running and reachable through the proxy. No backend or Docker stack was started during implementation.
