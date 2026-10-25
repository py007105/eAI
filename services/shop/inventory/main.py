import os
import sqlite3
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.obs import setup

app = FastAPI(title="inventory")
log = setup(app)

DB = os.getenv("DB_PATH", "/data/inventory.db")
_lock = threading.Lock()
_conn = None


def db():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB), exist_ok=True)
        _conn = sqlite3.connect(DB, check_same_thread=False)
        _conn.execute("create table if not exists items(sku text primary key, name text, price real, stock int)")
        if _conn.execute("select count(*) from items").fetchone()[0] == 0:
            _conn.executemany("insert into items values(?,?,?,?)", [
                ("sku-lamp", "Desk lamp", 24.0, 100000), ("sku-mug", "Ceramic mug", 9.5, 100000),
                ("sku-bag", "Canvas bag", 18.0, 100000), ("sku-book", "Notebook", 6.25, 100000)])
            _conn.commit()
    return _conn


class Reserve(BaseModel):
    sku: str
    qty: int = Field(gt=0, le=20)


@app.get("/items")
def items():
    with _lock:
        rows = db().execute("select sku,name,price,stock from items").fetchall()
    return [{"sku": s, "name": n, "price": p, "stock": k} for s, n, p, k in rows]


@app.post("/reserve")
def reserve(r: Reserve):
    with _lock:
        cur = db().execute("update items set stock=stock-? where sku=? and stock>=?", (r.qty, r.sku, r.qty))
        db().commit()
    if cur.rowcount == 0:
        raise HTTPException(409, "unknown sku or insufficient stock")
    return {"reserved": r.qty, "sku": r.sku}
