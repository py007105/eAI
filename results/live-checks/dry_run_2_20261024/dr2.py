"""Dry run 2 step driver (outside git). Usage: python dr2.py a|c|b_start|b_finish|d. Never prints the token."""
import datetime as dt
import json
import sys
import time

import httpx

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
B, EV = "http://127.0.0.1:8000", "http://127.0.0.1:8200"
TOK = open(r"D:\eAI\demo\dryrun2.token", encoding="utf-8").read().strip()
H = {"X-Approval-Token": TOK}
STATE = r"D:\eAI\demo\dr2_state.json"


def f(t):
    return dt.datetime.fromtimestamp(t, IST).strftime("%I:%M:%S %p").lstrip("0")


def say(m):
    print(f"{f(time.time())} {m}", flush=True)


def save(**kw):
    try:
        s = json.load(open(STATE))
    except Exception:  # noqa: BLE001
        s = {}
    s.update(kw)
    json.dump(s, open(STATE, "w"), indent=1)


def load():
    return json.load(open(STATE))


def post(url, body):
    r = httpx.post(url, json=body, headers=H, timeout=20)
    r.raise_for_status()
    return r.json()


def run(scenario, target, timeout_s):
    t0 = time.time()
    rid = post(f"{EV}/runs", {"scenario": scenario, "target": target, "timeout_s": timeout_s})["run_id"]
    say(f"{scenario} on {target}: run {rid} started")
    return rid, t0


def wait_run(rid, limit=420, on_tick=None):
    end = time.time() + limit
    while time.time() < end:
        st = httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()
        if on_tick:
            on_tick()
        if st.get("state") != "running":
            break
        time.sleep(2)
    else:
        say(f"run {rid}: still running after {limit} s (skipped)")
        return None
    for _ in range(20):
        r = httpx.get(f"{EV}/runs/{rid}/reveal", timeout=10)
        if r.status_code == 200:
            return r.json()
        time.sleep(2)
    return None


def incidents_since(t):
    return [i for i in httpx.get(f"{B}/incidents", timeout=10).json() if i["opened_t"] >= t - 1]


def show(rev, t_from):
    if rev:
        ti, sc = rev["truth"]["t_inject"], rev["score"]
        say(f"injected {f(ti)}; detected={sc.get('detected')} in {sc.get('time_to_detect_s')} s; recovered={sc.get('recovered')} "
            f"at {sc.get('time_to_verified_recovery_s')} s; actions_executed={sc.get('actions_executed')}; failed %={sc.get('failed_request_pct')}")
        t_from = ti
    for i in incidents_since(t_from):
        acts = [(a.get("runbook_id"), a.get("verdict"), a.get("executed"), a.get("approved_by")) for a in i.get("actions", [])]
        say(f"  incident {i['id']} {i['status']} cause={i['likely_cause']} services={i['services']} actions={acts} "
            f"verification={(i.get('verification') or {}).get('outcome')}")
        for x in i.get("timeline", []):
            print(f"      {f(x['t'])} {x['msg']}", flush=True)


step = sys.argv[1]
if step == "a":
    rid, t0 = run("crash", "web", 150)
    save(a_run=rid)
    show(wait_run(rid), t0)
elif step == "c":
    k = post(f"{B}/killswitch", {"on": True})
    say(f"kill switch ON: {k}")
    rid, t0 = run("disk_fill", "web", 150)
    save(c_run=rid)
    show(wait_run(rid), t0)
    k = post(f"{B}/killswitch", {"on": False})
    m = post(f"{B}/mode", {"mode": "autopilot"})
    st = httpx.get(f"{B}/status", timeout=10).json()
    say(f"kill switch OFF + mode autopilot: kill_switch={st.get('kill_switch')} mode={st.get('mode')}")
elif step == "b_start":
    m = post(f"{B}/mode", {"mode": "ask-first"})
    say(f"mode {m.get('mode')}")
    rid, t0 = run("bad_deploy", "payments", 400)
    save(b_run=rid, b_t0=t0)
    end = time.time() + 400
    while time.time() < end:
        p = [a for a in httpx.get(f"{B}/approvals", timeout=10).json() if a.get("service") == "payments"]
        if p:
            save(b_pending=time.time(), b_incident=p[0]["incident_id"])
            say(f"PENDING: {p[0].get('runbook_id')} on payments, incident {p[0]['incident_id']} (+{time.time() - t0:.0f} s after start)")
            break
        time.sleep(1)
    else:
        say("no approval appeared (skipped)")
elif step == "b_finish":
    s = load()
    iid = s["b_incident"]
    end = time.time() + 330
    while time.time() < end:
        i = httpx.get(f"{B}/incidents/{iid}", timeout=10).json()
        if i["status"] in ("recovered", "partially_recovered", "unresolved", "escalated"):
            break
        time.sleep(3)
    a = i["actions"][-1]
    say(f"incident {iid} status={i['status']} verification={(i.get('verification') or {}).get('outcome')}")
    say(f"action {a['runbook_id']} verdict={a['verdict']} executed={a['executed']} approved_by={a.get('approved_by')}")
    if a.get("executed_t"):
        say(f"proposed {f(a['t'])}; executed {f(a['executed_t'])}; wait {a['executed_t'] - a['t']:.1f} s; "
            f"after PENDING {a['executed_t'] - s['b_pending']:.1f} s")
    for x in httpx.get(f"{B}/audit", timeout=10).json()[-4:]:
        if x.get("service") == "payments":
            say(f"  audit {f(x['t'])} {x.get('runbook')} actor={x.get('actor')} ok={x.get('ok')} outcome={x.get('outcome')}")
    rev = wait_run(s["b_run"], limit=120)
    if rev:
        say(f"run: detected in {rev['score'].get('time_to_detect_s')} s; recovered={rev['score'].get('recovered')} "
            f"at {rev['score'].get('time_to_verified_recovery_s')} s; failed %={rev['score'].get('failed_request_pct')}")
elif step == "d":
    s = load()
    r = httpx.get(f"{B}/incidents/{s['b_incident']}", timeout=10).json().get("report") or {}
    say(f"report keys: {sorted(r)}")
    say(f"summary: {str(r.get('summary'))[:200]}")
