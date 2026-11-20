import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OWNER_PW = "owner-pass-1"
ADMIN_PW = "admin-secret-9"


class Shop:
    """Test helper wrapping a TestClient with auth-aware calls."""

    def __init__(self, client):
        self.c = client
        r = client.post("/api/v1/setup", json={
            "shop_name": "Alimentation Diawara", "shop_phone": "+223 76 12 34 56", "shop_city": "Bamako",
            "owner_name": "Boubacar", "owner_password": OWNER_PW, "admin_password": ADMIN_PW})
        assert r.status_code == 200, r.text
        self.owner = r.json()["token"]
        self.owner_user = r.json()["user"]
        self.recovery = r.json()["recovery_code"]

    def h(self, token):
        return {"Authorization": f"Bearer {token}"}

    def call(self, method, url, token=None, **kw):
        return self.c.request(method, "/api/v1" + url, headers=self.h(token or self.owner), **kw)

    def worker(self, credit=False, receive=True, name="Aminata Traoré"):
        r = self.call("POST", "/workers", json={"name": name, "can_sell_credit": credit, "can_receive_stock": receive})
        assert r.status_code == 200, r.text
        w = r.json()
        lg = self.c.post("/api/v1/auth/login", json={"identifier": w["username"], "password": w["password"]})
        assert lg.status_code == 200, lg.text
        return lg.json()["token"], w

    def product(self, name="Riz", base="Paquet", price="100", units=None, stock=None, cost="0"):
        body = {"name_fr": name, "base_unit": base, "price": price, "cost": cost, "units": units or []}
        if stock is not None:
            body["initial_stock"] = stock
        r = self.call("POST", "/products", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def stock(self, pid):
        rows = self.call("GET", "/products?active_only=false").json()
        return Decimal(next(p for p in rows if p["id"] == pid)["stock_qty"])

    def balances(self):
        b = self.call("GET", "/finance/balances").json()
        return Decimal(b["cash"]), Decimal(b["mobile"])


@pytest.fixture()
def shop(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOP_DATA_DIR", str(tmp_path))
    from app import db
    db.reset_engine()
    from app.main import create_app
    with TestClient(create_app()) as c:
        yield Shop(c)
    db.reset_engine()
