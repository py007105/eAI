import os
import sqlite3
import threading
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.obs import setup

app = FastAPI(title="payments")
log = setup(app)

DB = os.getenv("DB_PATH", "/data/payments.db")
_lock = threading.Lock()
_conn = None


def db():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB), exist_ok=True)
        _conn = sqlite3.connect(DB, check_same_thread=False)
        _conn.execute("create table if not exists payments(id text primary key, order_id text, amount real, status text)")
    return _conn


class Charge(BaseModel):
    order_id: str
    amount: float = Field(gt=0)
    card: str  # sandbox only: 4242424242424242 succeeds, anything else is declined


@app.post("/charge")
def charge(c: Charge):
    ok = c.card == "4242424242424242"
    pid = uuid.uuid4().hex[:12]
    with _lock:
        db().execute("insert into payments values(?,?,?,?)", (pid, c.order_id, c.amount, "paid" if ok else "declined"))
        db().commit()
    if not ok:
        raise HTTPException(402, "card declined")
    return {"payment_id": pid, "status": "paid"}
