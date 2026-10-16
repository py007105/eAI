import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.obs import call, setup

app = FastAPI(title="web")
log = setup(app)

ORDERS = os.getenv("ORDERS_URL", "http://orders:8000")
INVENTORY = os.getenv("INVENTORY_URL", "http://inventory:8000")
_client = httpx.AsyncClient()


class Checkout(BaseModel):
    sku: str
    qty: int = Field(gt=0, le=20)
    card: str


@app.get("/")
def index():
    return {"app": "eai-shop", "endpoints": ["/api/products", "/api/checkout"]}


@app.get("/api/products")
async def products():
    try:
        r = await call(_client, "inventory", "GET", f"{INVENTORY}/items")
    except httpx.HTTPError:
        log.error("inventory unreachable")
        raise HTTPException(502, "catalog unavailable")
    if r.status_code != 200:
        raise HTTPException(502, "catalog unavailable")
    return r.json()


@app.post("/api/checkout")
async def checkout(c: Checkout):
    try:
        r = await call(_client, "orders", "POST", f"{ORDERS}/orders", json=c.model_dump(), timeout=5.0)
    except httpx.HTTPError:
        log.error("orders unreachable")
        raise HTTPException(502, "checkout unavailable")
    if r.status_code != 200:
        raise HTTPException(r.status_code if r.status_code < 500 else 502, "checkout failed")
    return r.json()
