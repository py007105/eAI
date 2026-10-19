"""Read-only evidence capture for an ask-first rehearsal: what the brain offers for approval and what the dashboard renders, second by second.

    python scripts/approval_capture.py [--minutes 45] [--out results/rehearsals/R5_capture]

Every second it records, as one JSON line in <out>/<start>/capture.jsonl:
  - brain:  GET http://localhost:8000/approvals -> HTTP code, latency, pending (incident_id, runbook, service)
  - dash:   what a headless page on http://localhost:8050 shows in the Approval queue (card text, buttons) and under it (approval_msg)
Screenshots (full page) go to the same folder every 5 s while either side shows a pending approval, and every 60 s otherwise.

Read-only: GET requests and page reads only. It never types a token, never clicks, never changes mode. The headless page uses the dashboard server's
shared backend cache, so it shows what the dashboard served; it cannot prove what another browser window displayed. Runs at below-normal priority and
stops if free RAM < 1.5 GB. Stop it with Ctrl+C (the file is flushed every line).
"""
import argparse
import ctypes
import json
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import memguard  # noqa: E402


def brain_view(base):
    t0 = time.perf_counter()
    try:
        r = httpx.get(f"{base}/approvals", timeout=5)
        items = r.json() if r.status_code == 200 else []
        return {"code": r.status_code, "ms": round((time.perf_counter() - t0) * 1000),
                "pending": [{k: a.get(k) for k in ("incident_id", "runbook_id", "service")} for a in items]}
    except (httpx.HTTPError, ValueError) as e:
        return {"code": None, "ms": round((time.perf_counter() - t0) * 1000), "error": type(e).__name__, "pending": []}


def dash_view(pg):
    try:
        q = pg.locator("#approvals")
        return {"queue_text": " | ".join(q.inner_text(timeout=2000).splitlines())[:300],
                "approve_buttons": pg.locator("#approvals button", has_text="Approve").count(),
                "approval_msg": pg.locator("#approval_msg").inner_text(timeout=2000)[:200],
                "mode_pill": pg.locator(".pill").first.inner_text(timeout=2000) if pg.locator(".pill").count() else None}
    except Exception as e:  # page reload, navigation or timeout: record it, keep going
        return {"error": type(e).__name__}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=45)
    ap.add_argument("--out", default="results/rehearsals/R5_capture")
    ap.add_argument("--brain", default="http://localhost:8000")
    ap.add_argument("--dash", default="http://localhost:8050")
    a = ap.parse_args()
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL; Chromium inherits it
    out = ROOT / a.out / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "capture.jsonl").open("a", encoding="utf-8")
    print(f"capturing to {out} (Ctrl+C to stop)", flush=True)
    end, last_shot, n = time.time() + a.minutes * 60, 0.0, 0
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": 1500, "height": 1250})
            pg.goto(a.dash, wait_until="load", timeout=60000)
            pg.wait_for_selector("#approvals", timeout=60000)
            end = time.time() + a.minutes * 60                  # count the duration from when the page is ready
            while time.time() < end:
                t0 = time.time()
                ram = memguard.free_ram_gb()
                if ram < 1.5:
                    log.write(json.dumps({"t": round(t0, 1), "stop": f"free RAM {ram:.2f} GB < 1.5"}) + "\n")
                    print("stopped: low RAM", flush=True)
                    break
                rec = {"t": round(t0, 1), "ist": time.strftime("%H:%M:%S"), "brain": brain_view(a.brain), "dash": dash_view(pg),
                       "free_ram_gb": round(ram, 2)}
                pending = bool(rec["brain"]["pending"]) or bool(rec["dash"].get("approve_buttons"))
                if t0 - last_shot >= (5 if pending else 60):
                    name = f"{time.strftime('%H%M%S')}{'_pending' if pending else ''}.png"
                    try:
                        pg.screenshot(path=out / name, full_page=True)
                        rec["screenshot"], last_shot = name, t0
                    except Exception as e:
                        rec["screenshot_error"] = type(e).__name__
                log.write(json.dumps(rec) + "\n")
                log.flush()
                n += 1
                if pending or n % 30 == 1:
                    print(f"{rec['ist']} brain pending={[p['service'] + ':' + p['runbook_id'] for p in rec['brain']['pending']]} "
                          f"dash approve_buttons={rec['dash'].get('approve_buttons')}", flush=True)
                time.sleep(max(0.0, 1.0 - (time.time() - t0)))
            b.close()
    except KeyboardInterrupt:
        pass
    finally:
        log.close()
        print(f"wrote {n} lines to {out / 'capture.jsonl'}", flush=True)


if __name__ == "__main__":
    main()
