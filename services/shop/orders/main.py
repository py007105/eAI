import os
import sqlite3
import threading
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.obs import call, setup

app = FastAPI(title="orders")
log = setup(app)

DB = os.getenv("DB_PATH", "/data/orders.db")
INVENTORY = os.getenv("INVENTORY_URL", "http://inventory:8000")
PAYMENTS = os.getenv("PAYMENTS_URL", "http://payments:8000")
_lock = threading.Lock()
_conn = None
_client = httpx.AsyncClient()


def db():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB), exist_ok=True)
        _conn = sqlite3.connect(DB, check_same_thread=False)
        _conn.execute("create table if not exists orders(id text primary key, sku text, qty int, total real, status text)")
    return _conn


class NewOrder(BaseModel):
    sku: str
    qty: int = Field(gt=0, le=20)
    card: str


@app.post("/orders")
async def create_order(o: NewOrder):
    oid = uuid.uuid4().hex[:12]
    try:
        items = await call(_client, "inventory", "GET", f"{INVENTORY}/items")
        price = next((i["price"] for i in items.json() if i["sku"] == o.sku), None)
        if price is None:
            raise HTTPException(404, "unknown sku")
        r = await call(_client, "inventory", "POST", f"{INVENTORY}/reserve", json={"sku": o.sku, "qty": o.qty})
        if r.status_code != 200:
            raise HTTPException(409, "cannot reserve stock")
        total = price * o.qty
        p = await call(_client, "payments", "POST", f"{PAYMENTS}/charge",
                       json={"order_id": oid, "amount": total, "card": o.card})
        if p.status_code != 200:
            raise HTTPException(402, "payment failed")
    except httpx.HTTPError as e:
        log.error(f"dependency failure creating order: {type(e).__name__}")
        raise HTTPException(502, "dependency unavailable")
    with _lock:
        db().execute("insert into orders values(?,?,?,?,?)", (oid, o.sku, o.qty, total, "confirmed"))
        db().commit()
    return {"order_id": oid, "total": total, "status": "confirmed"}


@app.get("/orders/{oid}")
def get_order(oid: str):
    with _lock:
        row = db().execute("select id,sku,qty,total,status from orders where id=?", (oid,)).fetchone()
    if not row:
        raise HTTPException(404, "not found")
    return dict(zip(("order_id", "sku", "qty", "total", "status"), row))
