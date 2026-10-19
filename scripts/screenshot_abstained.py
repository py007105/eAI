"""Screenshot of the report panel for an ABSTAINED incident (fixture data, not telemetry): before/after the label fix found in rehearsal R3.

    python scripts/screenshot_abstained.py --out docs/screenshots/abstained_after.png
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def start(cmd, env_extra, port, path="/"):
    import os
    p = subprocess.Popen([sys.executable, *cmd], cwd=ROOT, env={**os.environ, **env_extra}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    procs = []
    try:
        procs.append(start(["scripts/fixture_backend.py"], {"FIXTURE": "abstained", "FIXTURE_PORT": "8120"}, 8120, "/status"))
        procs.append(start(["dashboard/app.py"], {"PORT": "8070", "BACKEND_URL": "http://127.0.0.1:8120"}, 8070))
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": 1400, "height": 1000})
            pg.goto("http://127.0.0.1:8070", wait_until="load", timeout=60000)
            pg.wait_for_timeout(5000)
            box = pg.locator("#t_report").locator("xpath=..")
            box.first.screenshot(path=ROOT / a.out)
            print("saved", a.out, "| panel text:", box.first.inner_text().replace("\n", " | ")[:400])
            b.close()
    finally:
        for p in procs:
            p.kill()


if __name__ == "__main__":
    main()
