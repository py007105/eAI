"""Debug helper: load the dashboard with no backend; print console errors, callback timings, status text and
the dropdown DOM (to write CSS against real class names)."""
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
env = {**os.environ, "PORT": "8071", "BACKEND_URL": "http://127.0.0.1:8999", "OMP_NUM_THREADS": "1"}
p = subprocess.Popen([sys.executable, "dashboard/app.py"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    for _ in range(60):
        try:
            requests.get("http://127.0.0.1:8071", timeout=1)
            break
        except requests.RequestException:
            time.sleep(0.5)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.on("console", lambda m: print(f"console[{m.type}] {m.text[:160]}") if m.type in ("error", "warning") else None)
        pg.goto("http://127.0.0.1:8071", wait_until="load", timeout=60000)
        pg.wait_for_timeout(6000)
        print("statusbar text:", repr(pg.locator("#statusbar").inner_text()))
        print("report text:", repr(pg.locator("#report").inner_text()))
        html = pg.locator("#lang").evaluate("e => e.outerHTML")
        print("lang dropdown html:", html[:900])
        pg.locator("#lang").click()
        pg.wait_for_timeout(500)
        print("open menu classes:", pg.evaluate("[...document.querySelectorAll('[class*=dropdown]')].map(e=>e.className).slice(0,12)"))
        b.close()
finally:
    p.kill()
