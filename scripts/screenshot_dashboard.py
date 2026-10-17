"""Screenshot the dashboard (headless Chromium) in several states and run basic design checks.

    python scripts/screenshot_dashboard.py [--out docs/screenshots]

States: offline (no backend), recovered / awaiting-approval / down (fixture data from scripts/fixture_backend.py),
and the Hindi UI. The fixture data is hand-made sample data for design review, not telemetry.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PANELS = {"map": "t_map", "report": "t_report", "causes": "t_causes", "timeline": "t_timeline", "evidence": "t_evidence",
          "forecast": "t_forecast", "approvals": "t_approvals", "proof": "t_proof", "challenge": "t_challenge",
          "scorecard": "t_score"}


def start(cmd, env_extra, port, path="/"):
    env = {**os.environ, **env_extra, "OMP_NUM_THREADS": "1"}
    p = subprocess.Popen([sys.executable, *cmd], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            if requests.get(f"http://127.0.0.1:{port}{path}", timeout=1).ok:
                return p
        except requests.RequestException:
            time.sleep(0.5)
    p.kill()
    raise RuntimeError(f"{cmd} did not start")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/screenshots")
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    procs, report = [], []
    try:
        # offline dashboard points at a port nothing listens on
        procs.append(start(["dashboard/app.py"], {"PORT": "8051", "BACKEND_URL": "http://127.0.0.1:8999"}, 8051))
        states = {"offline": 8051}
        for i, st in enumerate(("recovered", "awaiting", "down")):
            procs.append(start(["scripts/fixture_backend.py"], {"FIXTURE": st, "FIXTURE_PORT": str(8100 + i)}, 8100 + i, "/status"))
            procs.append(start(["dashboard/app.py"], {"PORT": str(8060 + i), "BACKEND_URL": f"http://127.0.0.1:{8100 + i}"}, 8060 + i))
            states[st] = 8060 + i
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for st, port in states.items():
                pg = b.new_page(viewport={"width": 1600, "height": 1300})
                pg.goto(f"http://127.0.0.1:{port}", wait_until="load", timeout=60000)
                pg.wait_for_timeout(5000)  # the page polls every 1.5 s, so networkidle never fires; let panels fill
                pg.screenshot(path=out / f"{st}_full.png", full_page=True)
                if st in ("recovered", "offline"):
                    for name, el in PANELS.items():
                        box = pg.locator(f"#{el}").locator("xpath=..")
                        if box.count():
                            box.first.screenshot(path=out / f"{st}_panel_{name}.png")
                if st == "recovered":
                    fam = pg.evaluate("getComputedStyle(document.body).fontFamily")
                    loaded = pg.evaluate("document.fonts.check('16px \"Noto Sans Devanagari\"')")
                    glow = pg.evaluate("getComputedStyle(document.querySelector('.panel')).boxShadow")
                    icons = pg.locator(".icon-circle").count()
                    report += [f"body font-family: {fam}", f"Noto Sans Devanagari loaded: {loaded}",
                               f"panel box-shadow: {glow[:90]}", f"icon circles on page: {icons}"]
                    pg.locator("#lang").click()
                    pg.get_by_text("हिन्दी").click()
                    pg.wait_for_timeout(2500)
                    pg.screenshot(path=out / "recovered_hindi_full.png", full_page=True)
                    report.append("Hindi title rendered: " + pg.locator("#t_map").inner_text())
                pg.close()
            b.close()
    finally:
        for p in procs:
            p.kill()
    (out / "checks.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print("screenshots:", sorted(f.name for f in out.glob("*.png")))


if __name__ == "__main__":
    main()
