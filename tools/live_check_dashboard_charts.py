"""Live check of the chart / explanation / statistics cards in the real dashboard (not the synthetic preview).

    python tools/live_check_dashboard_charts.py [--backend http://127.0.0.1:8000] [--port 8052]
    python tools/live_check_dashboard_charts.py --url http://127.0.0.1:8050 --populated 150 --out <md> --tag combined

Needs the stack running (the brain answering on --backend). Read-only on the stack: it only sends GET requests. Without
--url it starts this checkout's dashboard from source on 127.0.0.1:<port>; with --url it checks an already running
dashboard (e.g. the dashboard container of the deployment under test). It opens the page in headless Chromium and
compares what the page shows with what the brain's API returns at the same moment:
  D1 the service chart has lines built from polled /services snapshots (at least 10 points);
  D2 the explanation equals explain_service() on the live features of /services (fetched just before or just after);
  D3 the statistics card shows the counts computed by incident_stats() on the live /incidents;
  D4 the Hindi page shows the Hindi card titles and explanation heading;
  D5 the scope notes say the data is live (no synthetic banner on the real dashboard);
  D6 (with --populated S) within S seconds the page shows a NON-EMPTY explanation that equals explain_service() on the
     live features of one /services snapshot taken within 4 s of the page read. The caller must have injected a real
     fault on the service; if no non-empty explanation appears, D6 is INCOMPLETE (never a pass). D2 alone can pass with
     an empty explanation on both sides, which does not verify the wording of populated explanations.
Writes the report (--out, default docs/results/dashboard_charts_live.md) and two screenshots of the cards only (the token
field is not in the picture). The behaviour with the backend down is unit-tested only (tests/test_dashboard_charts_live.py).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
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


def free_gb():
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import memguard
        return round(memguard.free_ram_gb(), 2)
    except Exception:  # noqa: BLE001
        return None


def get(backend, path):
    r = requests.get(f"{backend}{path}", timeout=5)
    r.raise_for_status()
    return r.json()


def shown_sentences(explanation_text: str) -> list[str]:
    return [ln.strip() for ln in explanation_text.splitlines()[1:] if ln.strip()]


def populated_match(page_reads, api_snaps, service, window_s=4.0):
    """page_reads: [(t, sentences)], api_snaps: [(t, features)]. Returns (t, sentences) of the first NON-EMPTY page read
    that equals explain_service() of an API snapshot within window_s, else None."""
    for t, shown in page_reads:
        if not shown or shown[0].startswith("Nothing to report"):
            continue
        for ta, feats in api_snaps:
            if abs(ta - t) <= window_s and feats is not None and explain_service(service, feats, "en") == shown:
                return t, shown
    return None


class ApiSampler(threading.Thread):
    def __init__(self, backend, service):
        super().__init__(daemon=True)
        self.backend, self.service, self.snaps, self.stop_ev = backend, service, [], threading.Event()

    def run(self):
        while not self.stop_ev.is_set():
            try:
                s = get(self.backend, "/services")
                self.snaps.append((time.time(), ((s.get("services") or {}).get(self.service) or {}).get("features")))
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="http://127.0.0.1:8000")
    ap.add_argument("--port", type=int, default=8052)
    ap.add_argument("--url", help="check this running dashboard instead of starting one from source")
    ap.add_argument("--service", default="web")
    ap.add_argument("--warmup", type=int, default=25)
    ap.add_argument("--populated", type=int, default=0, help="D6: seconds to wait for a non-empty explanation")
    ap.add_argument("--out", default="docs/results/dashboard_charts_live.md")
    ap.add_argument("--tag", default="live", help="screenshot names: charts_<tag>_en.png / charts_<tag>_hi.png")
    ap.add_argument("--note", default="", help="one line about the deployment under test, written into the report")
    a = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    started = ist()
    status = get(a.backend, "/status")           # fails loudly if the stack is not running
    free_gb_start = free_gb()
    load_s = None
    checks = []

    def check(cid, ok, detail, status_=None):
        checks.append((cid, status_ or ("PASS" if ok else "FAIL"), detail))

    url = a.url or f"http://127.0.0.1:{a.port}"
    dash_proc = None
    if not a.url:
        env = {**os.environ, "BACKEND_URL": a.backend, "PORT": str(a.port)}
        dash_proc = subprocess.Popen([sys.executable, "dashboard/app.py"], cwd=ROOT, env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shots = ROOT / "docs" / "screenshots"
    sampler = ApiSampler(a.backend, a.service)
    try:
        for _ in range(120):
            try:
                if requests.get(f"{url}/", timeout=1).ok:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={"width": 1400, "height": 1000})
            t_load = time.time()       # generous limits: a 30 s page load timed out once while the stack was running
            page.goto(f"{url}/", timeout=120000, wait_until="domcontentloaded")
            page.wait_for_selector("#svc_chart .main-svg", timeout=120000)
            load_s = round(time.time() - t_load, 1)
            if a.service != "web":
                page.locator("#chart_service").click()
                page.get_by_role("option", name=a.service, exact=True).click()
            sampler.start()
            row = page.locator("#svc_chart").locator("xpath=ancestor::div[contains(@class,'row')][1]")
            populated = None
            if a.populated:            # D6 first, while the injected fault is still active
                reads, t_end = [], time.time() + a.populated
                while time.time() < t_end and populated is None:
                    reads.append((time.time(), shown_sentences(page.locator("#svc_explain").inner_text())))
                    time.sleep(1.5)       # let the API sampler cover +-4 s around this read
                    populated = populated_match(reads, list(sampler.snaps), a.service)
                if populated:
                    row.screenshot(path=str(shots / f"charts_{a.tag}_populated_en.png"))
                    check("D6", True, f"non-empty explanation {populated[1]} equals explain_service() on live features "
                                      f"read within 4 s ({len(reads)} page reads)")
                else:
                    nonempty = [s for _, s in reads if s and not s[0].startswith("Nothing to report")]
                    check("D6", False, f"{len(reads)} page reads; non-empty explanations seen: {nonempty[:3]}; none matched "
                                       "the API within 4 s" if nonempty else f"{len(reads)} page reads; no non-empty explanation "
                                       "appeared (fault not visible to the detector features?)",
                          "FAIL" if nonempty else "INCOMPLETE")
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
            shown = shown_sentences(explanation)
            ok2 = any(shown == e or (not e and shown and shown[0].startswith("Nothing to report")) for e in expected)
            check("D2", ok2, f"page: {shown}; API before: {expected[0]}; API after: {expected[1]}")
            st = charts.incident_stats(incidents)
            lines = stats_text.splitlines()
            want = [f"{k}\t{v}" for k, v in sorted(st["by_status"].items())] + [f"Incidents without an executed action\t{st['not_executed']}"]
            missing = [w for w in want if w not in lines]
            check("D3", not missing, f"{len(incidents)} incidents from /incidents; expected rows {want}; missing {missing}")
            check("D5", scope.count("Live") == 2 and page.locator("#synthetic-banner").count() == 0, scope)
            row.screenshot(path=str(shots / f"charts_{a.tag}_en.png"))

            page.locator("#lang").click()
            page.get_by_role("option", name="हिन्दी").click()
            page.wait_for_function("document.querySelector('#t_charts') && document.querySelector('#t_charts').innerText.includes('सेवा चार्ट')",
                                   timeout=10000)
            hi_title = page.locator("#t_charts").inner_text() + " | " + page.locator("#t_stats").inner_text()
            hi_head = page.locator("#svc_explain").inner_text().splitlines()[0]
            check("D4", "सेवा चार्ट" in hi_title and "घटना आँकड़े" in hi_title and hi_head == "आंकड़े क्या कहते हैं",
                  f"{hi_title}; heading {hi_head}")
            row.screenshot(path=str(shots / f"charts_{a.tag}_hi.png"))
            b.close()
    finally:
        sampler.stop_ev.set()
        if dash_proc:
            dash_proc.kill()

    n = sum(s == "PASS" for _, s, _ in checks)
    inc = sum(s == "INCOMPLETE" for _, s, _ in checks)
    where = f"the running dashboard at `{url}`" if a.url else "dashboard run from this checkout's source"
    body = [f"# Live check: dashboard chart, explanation and statistics cards",
            "",
            f"Commit: `{commit}` ({where}); execution ID: `{os.environ.get('EAI_EXEC_ID', 'none')}`; started {started}, "
            f"finished {ist()}.",
            f"Backend: `{a.backend}` (brain mode `{status.get('mode')}`); read-only GET requests only. "
            "This is the real dashboard with live data, separate from the synthetic preview (`dashboard/preview/`).",
            f"Service shown: `{a.service}`; warm-up {a.warmup} s; page ready after {load_s} s; "
            f"free RAM at start {free_gb_start} GB.", *([f"Deployment: {a.note}"] if a.note else []),
            "",
            "| id | result | detail |", "|---|---|---|"]
    body += [f"| {cid} | {s} | {str(detail).replace('|', '/').replace(chr(9), ' = ')} |" for cid, s, detail in checks]
    body += ["", f"**{n} of {len(checks)} checks passed**; INCOMPLETE: {inc}", "",
             f"Screenshots: `docs/screenshots/charts_{a.tag}_en.png`, `docs/screenshots/charts_{a.tag}_hi.png`"
             + (f", `docs/screenshots/charts_{a.tag}_populated_en.png`" if a.populated else "") + " (the two cards only).",
             "Not checked live: the behaviour with the backend down (unit-tested in `tests/test_dashboard_charts_live.py`)."]
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(body) + "\n", encoding="utf-8")
    print("\n".join(body))
    sys.exit(0 if n == len(checks) else 1)


if __name__ == "__main__":
    main()
