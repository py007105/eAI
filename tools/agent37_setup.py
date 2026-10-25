"""Agent37 instance management for EternalAI (reads AGENT37_API_KEY from the environment; never prints it).

    python tools/agent37_setup.py status               # free: wallet balance, instance budget and status
    python tools/agent37_setup.py create --cap-usd 3 --yes
        # PAID: creates one agent37-hermes instance with auto-sleep after 5 idle minutes and a provider-enforced
        # monthly managed-spend cap. Prints the instance id to put in AGENT37_INSTANCE_ID.
    python tools/agent37_setup.py stop --yes           # stop the instance (bills disk only while stopped)

Endpoints (official docs, https://www.agent37.com/docs): POST /v1/instances, GET /v1/billing,
GET /v1/instances/{id}, GET /v1/instances/{id}/budget, POST /v1/instances/{id}/stop.
"""
import argparse
import os
import sys

import httpx

API = "https://api.agent37.com"


def _h():
    key = os.getenv("AGENT37_API_KEY", "")
    if not key:
        sys.exit("AGENT37_API_KEY is not set in this shell")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _get(path):
    r = httpx.get(f"{API}{path}", headers=_h(), timeout=20)
    return r.status_code, (r.json() if r.content else {})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "create", "stop"])
    ap.add_argument("--cap-usd", type=float, default=3.0, help="monthly managed-spend cap for the instance")
    ap.add_argument("--yes", action="store_true", help="confirm a paid or state-changing call")
    a = ap.parse_args(argv)
    iid = os.getenv("AGENT37_INSTANCE_ID", "")
    if a.cmd == "status":
        code, b = _get("/v1/billing")
        print("wallet:", code, {k: b.get(k) for k in ("balance_usd", "tier", "instance_limit", "past_due")})
        if iid:
            code, inst = _get(f"/v1/instances/{iid}")
            print("instance:", code, {k: inst.get(k) for k in ("id", "status", "template", "auto_sleep", "idle_timeout_seconds")})
            code, bud = _get(f"/v1/instances/{iid}/budget")
            print("budget (micros):", code, bud)
        return 0
    if not a.yes:
        sys.exit(f"'{a.cmd}' changes paid resources: rerun with --yes after the owner approves")
    if a.cmd == "create":
        body = {"template": "agent37-hermes", "name": "eternalai-investigator", "auto_sleep": True,
                "idle_timeout_seconds": 300, "budget": {"monthly_cap_micros": int(a.cap_usd * 1_000_000)}}
        r = httpx.post(f"{API}/v1/instances", headers=_h(), json=body, timeout=60)
        out = r.json() if r.content else {}
        print("create:", r.status_code, {k: out.get(k) for k in ("id", "status", "url", "template")})
        if r.status_code < 300:
            print(f"Set AGENT37_INSTANCE_ID={out.get('id')} (and keep AGENT37_API_KEY server-side only).")
        return 0 if r.status_code < 300 else 1
    if not iid:
        sys.exit("AGENT37_INSTANCE_ID is not set")
    r = httpx.post(f"{API}/v1/instances/{iid}/stop", headers=_h(), timeout=60)
    print("stop:", r.status_code, r.json() if r.content else {})
    return 0


if __name__ == "__main__":
    sys.exit(main())
