"""Inventory stock gate (harness tooling; no system code is changed).

    python scripts/stock_gate.py --check                  # print the per-SKU stock, exit 1 if any SKU is below the threshold
    python scripts/stock_gate.py --restock                # restock to the seeded level if any SKU is below the threshold, then verify
    python scripts/stock_gate.py --restock --force        # restock to the seeded level now (demo start), then verify

WHY: the inventory service only subtracts stock (`POST /reserve`); it has no add-stock endpoint, and adding one would change `app/` (a v3 change under
Amendment 4). A long evaluation or demo therefore runs out of stock (docs/postmortems/v2-stock-exhaustion.md). Amendment 8 allows a direct SQL restock
as a harness action, with these safeguards: it runs only between runs, never restarts the inventory container, never touches a volume, is one transaction,
and is verified through the service's own `GET /items`.

The seeded level is the value `app/inventory/main.py` inserts into a fresh database (lines 26-27: 100000 per SKU). SEED_STOCK below must equal it;
`seed_value_in_source()` reads the source and the tests compare the two.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SEED_STOCK = 100000
THRESHOLD = 50000           # restock when any SKU is below this (about a day of evaluation load per SKU is 100000; one run uses a few hundred)
TOLERANCE = 0.01            # after a restock every SKU must read at least SEED_STOCK * (1 - TOLERANCE) (the load generator keeps buying)
SKUS = ["sku-lamp", "sku-mug", "sku-bag", "sku-book"]
CONTAINER = "eai-inventory-1"
DOCKER = r"C:\Program Files\Docker\Docker\resources\bin"
BRAIN = os.getenv("EAI_PUBLIC_URL", "http://localhost:8000")

READ_PY = "import urllib.request,json;print(urllib.request.urlopen('http://localhost:8000/items',timeout=5).read().decode())"
# one transaction; BEGIN IMMEDIATE takes the write lock so the service's own commits queue behind it instead of interleaving
RESTOCK_SQL = "UPDATE items SET stock=?"
RESTOCK_PY = ("import sqlite3,sys;c=sqlite3.connect('/data/inventory.db',timeout=30,isolation_level=None);c.execute('BEGIN IMMEDIATE');"
              "n=c.execute('%s',(int(sys.argv[1]),)).rowcount;c.execute('COMMIT');print(n)" % RESTOCK_SQL)


class GateError(RuntimeError):
    pass


def _docker(args, timeout=60):
    env = {**os.environ, "PATH": os.environ.get("PATH", "") + os.pathsep + DOCKER}
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, env=env)


def read_stock():
    """{sku: stock} from the service's own GET /items, called inside the inventory container (its port is not published)."""
    r = _docker(["exec", CONTAINER, "python", "-c", READ_PY])
    if r.returncode:
        raise GateError(f"could not read the stock: {r.stderr.strip()[-200:]}")
    try:
        return {i["sku"]: int(i["stock"]) for i in json.loads(r.stdout)}
    except (ValueError, KeyError, TypeError) as e:
        raise GateError(f"unexpected /items answer: {type(e).__name__}") from e


def restock(level=SEED_STOCK):
    r = _docker(["exec", CONTAINER, "python", "-c", RESTOCK_PY, str(level)])
    if r.returncode:
        raise GateError(f"restock failed: {r.stderr.strip()[-200:]}")
    return int(r.stdout.strip())


def brain_incidents_between(t0, t1):
    """Incidents the brain opened in [t0, t1]; None if no brain is answering (between arms)."""
    try:
        import httpx
        return [i["id"] for i in httpx.get(f"{BRAIN}/incidents", timeout=5).json() if t0 - 1 <= i["opened_t"] <= t1 + 1]
    except Exception:  # noqa: BLE001 - a brain that is down is reported as None, not as an error
        return None


def gate(threshold=THRESHOLD, force=False):
    """Read the stock; restock to SEED_STOCK if any SKU is below `threshold` (or `force`); verify. Returns the record that goes into the result row.
    Raises GateError if the stock cannot be read, the restock fails, or the verification fails: the caller must then NOT start the run."""
    rec = {"t": time.time(), "threshold": threshold, "seed_level": SEED_STOCK, "before": read_stock(), "restocked": False}
    if set(rec["before"]) != set(SKUS):
        raise GateError(f"unexpected SKUs: {sorted(rec['before'])}")
    if force or min(rec["before"].values()) < threshold:
        t0 = time.time()
        rec["rows_updated"] = restock()
        rec["restocked"] = True
        rec["after_restock"] = read_stock()
        rec["brain_incidents_in_restock_window"] = brain_incidents_between(t0, time.time())
        if rec["rows_updated"] != len(SKUS) or min(rec["after_restock"].values()) < SEED_STOCK * (1 - TOLERANCE):
            raise GateError(f"restock did not verify: {rec['after_restock']}")
    else:
        rec["after_restock"] = rec["before"]
    if min(rec["after_restock"].values()) < threshold:
        raise GateError(f"stock below the threshold {threshold}: {rec['after_restock']}")
    return rec


def seed_value_in_source(repo):
    """The stock literal(s) a fresh database is seeded with, read from app/inventory/main.py."""
    src = (Path(repo) / "app/inventory/main.py").read_text(encoding="utf-8")
    return sorted(set(int(x) for x in re.findall(r'\("sku-[a-z]+",\s*"[^"]+",\s*[0-9.]+,\s*(\d+)\)', src)))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--restock", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--threshold", type=int, default=THRESHOLD)
    a = ap.parse_args()
    try:
        if a.check:
            s = read_stock()
            print(json.dumps(s))
            return 0 if min(s.values()) >= a.threshold else 1
        print(json.dumps(gate(a.threshold, a.force)))
        return 0
    except GateError as e:
        print(f"STOCK GATE FAILED: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
