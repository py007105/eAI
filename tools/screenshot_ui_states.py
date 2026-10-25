"""Screenshots of the dashboard in fixed fixture states (hand-made test data, not telemetry) for before/after UI comparisons.

    python tools/screenshot_ui_states.py --prefix ui_after [--app dashboard/app.py] [--states awaiting recovered abstained]

For each state it starts tools/fixture_backend.py and a dashboard on local ports, saves docs/screenshots/<prefix>_<state>_full.png and
<prefix>_<state>_top.png (header, status line and the first row), and prints the page title. The token field is never filled.
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


def start(cmd, env_extra, port, path="/"):
    p = subprocess.Popen([sys.executable, *cmd], cwd=ROOT, env={**os.environ, **env_extra}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            if requests.get(f"http://127.0.0.1:{port}{path}", timeout=1).ok:
                return p
        except requests.RequestException:
            time.sleep(0.5)
    p.kill()
    raise RuntimeError(f"{cmd} did not start")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--app", default="dashboard/app.py")
    ap.add_argument("--states", nargs="+", default=["awaiting", "recovered", "abstained"])
    a = ap.parse_args()
    out = ROOT / "docs" / "screenshots"
    for st in a.states:
        procs = []
        try:
            procs.append(start(["tools/fixture_backend.py"], {"FIXTURE": st, "FIXTURE_PORT": "8120"}, 8120, "/status"))
            procs.append(start([a.app], {"PORT": "8070", "BACKEND_URL": "http://127.0.0.1:8120"}, 8070))
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                pg = b.new_page(viewport={"width": 1500, "height": 1250})
                pg.goto("http://127.0.0.1:8070", wait_until="load", timeout=60000)
                pg.wait_for_timeout(6000)
                assert not pg.locator("#token").input_value(), "token field must be empty"
                pg.screenshot(path=out / f"{a.prefix}_{st}_full.png", full_page=True)
                pg.screenshot(path=out / f"{a.prefix}_{st}_top.png", clip={"x": 0, "y": 0, "width": 1500, "height": 620})
                print(f"{a.prefix}_{st}: title={pg.title()!r}")
                b.close()
        finally:
            for p in procs:
                p.kill()
            time.sleep(1)


if __name__ == "__main__":
    main()
