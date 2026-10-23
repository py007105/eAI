"""Live check of the chart / explanation / statistics cards in the real dashboard (not the synthetic preview).

    python scripts/live_check_dashboard_charts.py [--backend http://127.0.0.1:8000] [--port 8052]

Needs the stack running (the brain answering on --backend). Read-only on the stack: it only sends GET requests. It
starts this checkout's dashboard from source on 127.0.0.1:<port>, lets it poll for a while, opens it in headless
Chromium and compares what the page shows with what the brain's API returns at the same moment:
  D1 the service chart has lines built from polled /services snapshots (at least 10 points);
  D2 the explanation equals explain_service() on the live features of /services (fetched just before or just after);
  D3 the statistics card shows the counts computed by incident_stats() on the live /incidents;
  D4 the Hindi page shows the Hindi card titles and explanation heading;
  D5 the scope notes say the data is live (no synthetic banner on the real dashboard).
Writes docs/results/dashboard_charts_live.md and docs/screenshots/charts_live_en.png / charts_live_hi.png (cards only:
the token field is not in the picture). The behaviour with the backend down is unit-tested only
(tests/test_dashboard_charts_live.py).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
import charts  # noqa: E402
from explain_words import explain_service  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


def ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def get(backend, path):
    r = requests.get(f"{backend}{path}", timeout=5)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="http://127.0.0.1:8000")
    ap.add_argument("--port", type=int, default=8052)
    ap.add_argument("--service", default="web")
    ap.add_argument("--warmup", type=int, default=25)
    a = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    started = ist()
    status = get(a.backend, "/status")           # fails loudly if the stack is not running
    checks = []

    def check(cid, ok, detail):
        checks.append((cid, bool(ok), detail))

    env = {**os.environ, "BACKEND_URL": a.backend, "PORT": str(a.port)}
    dash_proc = subprocess.Popen([sys.executable, "dashboard/app.py"], cwd=ROOT, env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shots = ROOT / "docs" / "screenshots"
    try:
        for _ in range(60):
            try:
                if requests.get(f"http://127.0.0.1:{a.port}/", timeout=1).ok:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"http://127.0.0.1:{a.port}/")
            page.wait_for_selector("#svc_chart .main-svg", timeout=30000)
            if a.service != "web":
                page.locator("#chart_service").click()
                page.get_by_role("option", name=a.service, exact=True).click()
            time.sleep(a.warmup)                   # the page polls /services about once a second

            before = get(a.backend, "/services")
            incidents = get(a.backend, "/incidents")
            npoints = page.evaluate("() => { const g = document.querySelector('#svc_chart .js-plotly-plot');"
                                    " return g && g.data ? g.data.map(d => (d.y || []).filter(v => v !== null).length) : []; }")
            explanation = page.locator("#svc_explain").inner_text()
            stats_text = page.locator("#svc_stats").inner_text()
            scope = page.locator("#charts_scope").inner_text() + " | " + page.locator("#stats_scope").inner_text()
            after = get(a.backend, "/services")

            check("D1", npoints and max(npoints) >= 10, f"{len(npoints)} lines; points per line {npoints}")
            expected = []
            for snap in (before, after):
                feats = ((snap.get("services") or {}).get(a.service) or {}).get("features")
                expected.append(explain_service(a.service, feats, "en") if feats is not None else [])
            shown = [ln.strip() for ln in explanation.splitlines()[1:] if ln.strip()]
            ok2 = any(shown == e or (not e and shown and shown[0].startswith("Nothing to report")) for e in expected)
            check("D2", ok2, f"page: {shown}; API before: {expected[0]}; API after: {expected[1]}")
            st = charts.incident_stats(incidents)
            lines = stats_text.splitlines()
            want = [f"{k}\t{v}" for k, v in sorted(st["by_status"].items())] + [f"Incidents without an executed action\t{st['not_executed']}"]
            missing = [w for w in want if w not in lines]
            check("D3", not missing, f"{len(incidents)} incidents from /incidents; expected rows {want}; missing {missing}")
            check("D5", scope.count("Live") == 2 and page.locator("#synthetic-banner").count() == 0, scope)
            row = page.locator("#svc_chart").locator("xpath=ancestor::div[contains(@class,'row')][1]")
            row.screenshot(path=str(shots / "charts_live_en.png"))

            page.locator("#lang").click()
            page.get_by_role("option", name="हिन्दी").click()
            page.wait_for_function("document.querySelector('#t_charts') && document.querySelector('#t_charts').innerText.includes('सेवा चार्ट')",
                                   timeout=10000)
            hi_title = page.locator("#t_charts").inner_text() + " | " + page.locator("#t_stats").inner_text()
            hi_head = page.locator("#svc_explain").inner_text().splitlines()[0]
            check("D4", "सेवा चार्ट" in hi_title and "घटना आँकड़े" in hi_title and hi_head == "आंकड़े क्या कहते हैं",
                  f"{hi_title}; heading {hi_head}")
            row.screenshot(path=str(shots / "charts_live_hi.png"))
            b.close()
    finally:
        dash_proc.kill()

    n = sum(ok for _, ok, _ in checks)
    body = [f"# Live check: dashboard chart, explanation and statistics cards",
            "",
            f"Commit: `{commit}` (dashboard run from this checkout's source); started {started}, finished {ist()}.",
            f"Backend: `{a.backend}` (brain mode `{status.get('mode')}`); read-only GET requests only. "
            "This is the real dashboard with live data, separate from the synthetic preview (`dashboard/preview/`).",
            f"Service shown: `{a.service}`; warm-up {a.warmup} s.",
            "",
            "| id | result | detail |", "|---|---|---|"]
    body += [f"| {cid} | {'PASS' if ok else 'FAIL'} | {detail.replace('|', '/').replace(chr(9), ' = ')} |" for cid, ok, detail in checks]
    body += ["", f"**{n} of {len(checks)} checks passed**", "",
             "Screenshots: `docs/screenshots/charts_live_en.png`, `docs/screenshots/charts_live_hi.png` (the two cards only).",
             "Not checked live: the behaviour with the backend down (unit-tested in `tests/test_dashboard_charts_live.py`)."]
    out = ROOT / "docs" / "results" / "dashboard_charts_live.md"
    out.write_text("\n".join(body) + "\n", encoding="utf-8")
    print("\n".join(body))
    sys.exit(0 if n == len(checks) else 1)


if __name__ == "__main__":
    main()
