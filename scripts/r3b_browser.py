"""Rehearsal R3b: drive the REAL local dashboard (http://localhost:8050 only) in headless Chromium at below-normal priority. Tooling only.

    python scripts/r3b_browser.py --token <throwaway token the stack was started with> [--max-draws 8]

Order: invalid-token messages (a wrong token, a token with a non-Latin-1 character), mode set to Ask first with the throwaway token, the Approve path (hidden draws
from supported faults and healthy runs until one produces a proposal, at most --max-draws), the Reject path (same), one --unseen run in ask-first (a proposal, if any,
is REJECTED, never approved). Screenshots go to docs/screenshots/r3b_*.png, the record to results/rehearsals/R3b.json. Stops (exit 3) if free RAM < 1.5 GB.
The throwaway token is passed on this process's command line only and is never printed or written.
"""
import argparse
import ctypes
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import memguard  # noqa: E402

DASH, EAI, EV = "http://localhost:8050", "http://localhost:8000", "http://localhost:8200"
SHOTS = ROOT / "docs" / "screenshots"
LOG = []


class LowRam(Exception):
    pass


def note(**k):
    k["t"] = round(time.time(), 1)
    LOG.append(k)
    print(json.dumps(k, default=str)[:400], flush=True)


def ram_ok():
    g = memguard.free_ram_gb()
    if g < 1.5:
        note(event="PAUSE_LOW_RAM", free_ram_gb=round(g, 2))
        raise LowRam(g)
    return round(g, 2)


def challenge(*args):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_challenge.py"), *args], capture_output=True, text=True, timeout=60)
    return out.stdout.strip()


def state(rid):
    return httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"]


def reveal(rid):
    for _ in range(30):
        r = httpx.get(f"{EV}/runs/{rid}/reveal", timeout=10)
        if r.status_code == 200:
            j = r.json()
            return {"scenario": j["truth"]["scenario"], "target": j["truth"]["target"], **{k: j["score"].get(k) for k in (
                "detected", "time_to_detect_s", "recovered", "time_to_verified_recovery_s", "failed_request_pct", "incidents_opened", "actions_executed",
                "abstained_correctly", "harmful_interventions")}}
        time.sleep(5)
    return {"error": "no reveal"}


def shot(pg, name, sel=None):
    p = SHOTS / f"r3b_{name}.png"
    (pg.locator(sel).locator("xpath=..").first if sel else pg).screenshot(path=p, **({} if sel else {"full_page": True}))
    return p.name


def set_mode(pg, label, token):
    pg.fill("#token", token)
    pg.click("#mode")
    pg.get_by_text(label, exact=True).last.click()
    pg.wait_for_timeout(2500)
    return pg.locator("#mode_msg").inner_text()


def wait_run_end(rid, limit=420):
    t0 = time.time()
    while state(rid) == "running" and time.time() - t0 < limit:
        ram_ok()
        time.sleep(3)


def proposal_path(pg, action, max_draws):
    for draw in range(1, max_draws + 1):
        ram_ok()
        rid = json.loads(challenge("start"))["run_id"]
        t_start, card = time.time(), None
        while state(rid) == "running":
            ram_ok()
            btn = pg.locator("#approvals button", has_text="Approve" if action == "approve" else "Reject")
            if btn.count():
                card = pg.locator("#approvals").inner_text()
                t_card = time.time()
                shots = [shot(pg, f"{action}_1_card_full"), shot(pg, f"{action}_1_card", "#t_approvals"), shot(pg, f"{action}_1_causes", "#t_causes")]
                anomalous = sorted(s for s, v in (httpx.get(f"{EAI}/services", timeout=5).json()["services"] or {}).items() if v and v.get("anomalous"))
                btn.first.click()
                t_click = time.time()
                pg.wait_for_timeout(2500)
                msg = pg.locator("#approval_msg").inner_text()
                rec = {"path": action, "draw": draw, "run_id": rid, "card_text": card, "anomalous_at_card": anomalous, "click_message": msg,
                       "s_start_to_card": round(t_card - t_start, 1), "s_card_to_click": round(t_click - t_card, 1)}
                if action == "approve":
                    t_ban = None
                    for _ in range(200):
                        ram_ok()
                        b = pg.locator("#check .banner")
                        if b.count():
                            t_ban = time.time()
                            rec["banner"] = b.first.inner_text()
                            break
                        pg.wait_for_timeout(1000)
                    rec["s_click_to_banner"] = round(t_ban - t_click, 1) if t_ban else None
                    shots += [shot(pg, "approve_2_banner_full"), shot(pg, "approve_2_banner", "#t_check")]
                else:
                    pg.wait_for_timeout(2000)
                    last = httpx.get(f"{EAI}/incidents", timeout=5).json()[-1]
                    rec["incident_status_after_reject"] = last["status"]
                    rec["actions_after_reject"] = [{k: a.get(k) for k in ("runbook_id", "service", "verdict", "executed")} for a in last["actions"]]
                    shots += [shot(pg, "reject_2_after_full")]
                wait_run_end(rid)
                rec.update(screenshots=shots, reveal=reveal(rid), free_ram_gb=ram_ok())
                note(event=f"{action}_path", **rec)
                return rec
            time.sleep(1)
        note(event="draw_without_proposal", path=action, draw=draw, run_id=rid, reveal=reveal(rid))
        time.sleep(20)
    note(event=f"{action}_path_no_proposal_in_{max_draws}_draws")
    return None


def unseen(pg):
    ram_ok()
    rid = json.loads(challenge("start", "--unseen"))["run_id"]
    seen_inc, card, shots = False, None, []
    while state(rid) == "running":
        ram_ok()
        if not seen_inc and httpx.get(f"{EAI}/incidents", timeout=5).json() and pg.locator("#report").inner_text().strip():
            last = httpx.get(f"{EAI}/incidents", timeout=5).json()[-1]
            if last["opened_t"] > time.time() - 120:
                seen_inc = True
                pg.wait_for_timeout(9000)                 # let the diagnosis land
                shots += [shot(pg, "unseen_1_full"), shot(pg, "unseen_1_report", "#t_report"), shot(pg, "unseen_1_causes", "#t_causes"), shot(pg, "unseen_1_map", "#t_map")]
        btn = pg.locator("#approvals button", has_text="Reject")
        if btn.count() and card is None:
            card = pg.locator("#approvals").inner_text()
            shots.append(shot(pg, "unseen_2_card", "#t_approvals"))
            btn.first.click()
            pg.wait_for_timeout(2000)
        time.sleep(1)
    last = httpx.get(f"{EAI}/incidents", timeout=5).json()
    rec = {"run_id": rid, "card_text": card, "report_text": pg.locator("#report").inner_text(), "margin_text": pg.locator("#margin").inner_text(),
           "incidents": [{k: i.get(k) for k in ("id", "status", "likely_cause", "abstained", "services", "ranking")} for i in last[-3:]],
           "screenshots": shots, "reveal": reveal(rid), "free_ram_gb": ram_ok()}
    note(event="unseen_path", **rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--max-draws", type=int, default=8)
    a = ap.parse_args()
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL; Chromium inherits it
    out = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "free_ram_gb_start": ram_ok()}
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": 1500, "height": 1250})
            pg.goto(DASH, wait_until="load", timeout=60000)
            pg.wait_for_timeout(5000)
            out["msg_wrong_token"] = set_mode(pg, "Autopilot", "PS D:\\eAI-release> python scripts")
            shot(pg, "token_1_wrong", "#mode_msg")
            out["msg_non_latin1_token"] = set_mode(pg, "Watch only", "tok€n")
            out["msg_correct_token"] = set_mode(pg, "Ask first", a.token)
            out["brain_mode_after"] = httpx.get(f"{EAI}/status", timeout=5).json().get("mode")
            note(event="token_tests", **{k: out[k] for k in ("msg_wrong_token", "msg_non_latin1_token", "msg_correct_token", "brain_mode_after")})
            if out["brain_mode_after"] != "ask-first":
                raise SystemExit("mode not set with the throwaway token; stopping")
            out["approve"] = proposal_path(pg, "approve", a.max_draws)
            out["reject"] = proposal_path(pg, "reject", a.max_draws)
            out["unseen"] = unseen(pg)
            b.close()
    except LowRam as e:
        out["stopped"] = f"free RAM {e} GB < 1.5"
    out["log"] = LOG
    (ROOT / "results" / "rehearsals").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "rehearsals" / "R3b.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("wrote results/rehearsals/R3b.json")
    sys.exit(3 if "stopped" in out else 0)


if __name__ == "__main__":
    main()
