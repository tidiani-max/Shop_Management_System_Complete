"""Strict SERVER-SIDE role + admin-password enforcement (never frontend-only)."""

import sqlite3
from decimal import Decimal

import pytest
from app import config

D = Decimal
ADMIN = "admin-secret-9"


def make_invoice(shop, token=None, pid=None, qty="2", price=None):
    line = (
        {"product_id": pid, "quantity": qty}
        if pid
        else {"quantity": qty, "unit_price": price or "500"}
    )
    r = shop.call("POST", "/invoices", token, json={"lines": [line]})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------- workers cannot change prices / costs
def test_worker_cannot_modify_product_price_or_cost(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10", cost="500")
    wtok, _ = shop.worker()
    for body in (
        {"price": "1"},
        {"cost": "1"},
        {"price": "1", "admin_password": ADMIN},
    ):
        r = shop.call("PATCH", f"/products/{p['id']}", wtok, json=body)
        assert r.status_code == 403 and r.json()["code"] == "WORKER_FORBIDDEN", body
    rows = shop.call("GET", "/products").json()
    assert D(rows[0]["price"]) == 750
    assert (
        shop.call("GET", "/products", wtok).json()[0].get("cost") is None
    )  # cost hidden from workers


def test_worker_can_create_product_but_cannot_delete_or_reprice_it(shop):
    existing = shop.product("Riz", base="Kg", price="750")
    wtok, _ = shop.worker()
    body = {
        "name_fr": "Savon",
        "base_unit": "Pièce",
        "price": "250",
        "cost": "150",
        "initial_stock": "10",
    }
    r = shop.call("POST", "/products", wtok, json=body)
    assert r.status_code == 200, r.text
    assert "cost" not in r.json()  # cost stays hidden from workers
    pid = r.json()["id"]
    assert shop.stock(pid) == 10
    # available straight away to the Fast Sell screen (same /products list the POS uses)
    assert any(p["id"] == pid for p in shop.call("GET", "/products", wtok).json())
    # ...but a worker can never delete, reprice or re-create an existing product to change its price
    assert shop.call("DELETE", f"/products/{pid}", wtok).status_code == 403
    assert (
        shop.call("PATCH", f"/products/{pid}", wtok, json={"price": "1"}).status_code
        == 403
    )
    dup = shop.call(
        "POST",
        "/products",
        wtok,
        json={"name_fr": " riz ", "base_unit": "Kg", "price": "1"},
    )
    assert dup.status_code == 409 and dup.json()["code"] == "DUPLICATE_PRODUCT"
    assert D(shop.call("GET", "/products").json()[0]["price"]) in (D(250), D(750))
    assert (
        D(
            next(
                p
                for p in shop.call("GET", "/products").json()
                if p["id"] == existing["id"]
            )["price"]
        )
        == 750
    )
    # no-stock-permission worker cannot add stock while creating
    deny, _ = shop.worker(receive=False, name="Oumar")
    r = shop.call(
        "POST", "/products", deny, json={**body, "name_fr": "Sel", "initial_stock": "5"}
    )
    assert r.status_code == 403
    assert (
        shop.call(
            "POST",
            "/products",
            deny,
            json={**body, "name_fr": "Sel", "initial_stock": None},
        ).status_code
        == 200
    )
    actions = [a["action"] for a in shop.call("GET", "/admin/audit").json()["items"]]
    assert "PRODUCT_CREATED" in actions


def test_owner_price_change_needs_admin_password(shop):
    p = shop.product("Riz", base="Kg", price="750")
    url = f"/products/{p['id']}"
    r = shop.call("PATCH", url, json={"price": "800"})
    assert r.status_code == 403 and r.json()["code"] == "ADMIN_PASSWORD_REQUIRED"
    r = shop.call("PATCH", url, json={"price": "800", "admin_password": "wrong-pass"})
    assert r.status_code == 403 and r.json()["code"] == "ADMIN_PASSWORD_INVALID"
    r = shop.call("PATCH", url, json={"price": "800", "admin_password": ADMIN})
    assert r.status_code == 200 and D(r.json()["price"]) == 800
    actions = [a["action"] for a in shop.call("GET", "/admin/audit").json()["items"]]
    assert "PRODUCT_PRICE_CHANGED" in actions and "ADMIN_PW_FAILED" in actions


def test_worker_stock_receive_cost_is_allowed_audited_and_never_touches_selling_price(
    shop,
):
    p = shop.product("Riz", base="Kg", price="750", cost="500", stock="10")
    wtok, _ = shop.worker()
    r = shop.call(
        "POST",
        "/stock/receive",
        wtok,
        json={"product_id": p["id"], "quantity": "10", "unit_cost": "600"},
    )
    assert r.status_code == 201 and shop.stock(p["id"]) == 20
    row = shop.call("GET", "/products").json()[0]
    assert (
        D(row["price"]) == 750 and D(row["cost"]) == 550
    )  # weighted average (10@500 + 10@600)
    assert shop.call("GET", "/products", wtok).json()[0].get("cost") is None
    actions = [a["action"] for a in shop.call("GET", "/admin/audit").json()["items"]]
    assert "STOCK_RECEIVED_COST" in actions
    # paying the supplier stays owner-only
    r = shop.call(
        "POST",
        "/stock/receive",
        wtok,
        json={
            "product_id": p["id"],
            "quantity": "1",
            "unit_cost": "600",
            "pay_method": "cash",
        },
    )
    assert r.status_code == 403
    deny, _ = shop.worker(receive=False, name="Oumar")
    assert (
        shop.call(
            "POST",
            "/stock/receive",
            deny,
            json={"product_id": p["id"], "quantity": "1"},
        ).status_code
        == 403
    )


def test_worker_receives_cartons_converted_and_sells_immediately(shop):
    p = shop.product(
        "Eau", base="Bouteille", price="100", units=[{"name": "Carton", "factor": "12"}]
    )
    wtok, _ = shop.worker()
    r = shop.call(
        "POST",
        "/stock/receive",
        wtok,
        json={
            "product_id": p["id"],
            "unit_name": "Carton",
            "quantity": "2",
            "unit_cost": "1200",
        },
    )
    assert r.status_code == 201, r.text
    assert D(r.json()["added_base_qty"]) == 24 and shop.stock(p["id"]) == 24
    row = shop.call("GET", "/products").json()[0]
    assert (
        D(row["price"]) == 100 and D(row["cost"]) == 100
    )  # 1200 per carton / 12 bottles
    # immediately sellable by the carton, at the catalogue price (12 x 100)
    inv = shop.call(
        "POST",
        "/invoices",
        wtok,
        json={
            "lines": [{"product_id": p["id"], "unit_name": "Carton", "quantity": "1"}]
        },
    )
    assert inv.status_code == 201 and D(inv.json()["total"]) == 1200
    assert shop.stock(p["id"]) == 12
    # a worker still cannot redefine units or prices
    r = shop.call(
        "PATCH",
        f"/products/{p['id']}",
        wtok,
        json={"units": [{"name": "Carton", "factor": "6"}]},
    )
    assert r.status_code == 403


def test_worker_can_add_new_packaging_but_not_edit_existing(shop):
    p = shop.product(
        "Chewing-gum",
        base="Pièce",
        price="25",
        units=[{"name": "Paquet", "factor": "10"}],
    )
    wtok, _ = shop.worker()
    url = f"/products/{p['id']}/units"
    r = shop.call("POST", url, wtok, json={"name": "Carton", "factor": "200"})
    assert r.status_code == 201, r.text
    units = {u["name"]: D(u["factor"]) for u in r.json()["units"]}
    assert units["Carton"] == 200 and units["Paquet"] == 10
    assert "cost" not in r.json()
    # duplicates (also against the base unit) and bad factors are rejected
    dup = shop.call("POST", url, wtok, json={"name": "carton", "factor": "5"})
    assert dup.status_code == 422 and dup.json()["code"] == "DUPLICATE_UNIT"
    base = shop.call("POST", url, wtok, json={"name": "pièce", "factor": "5"})
    assert base.status_code == 422 and base.json()["code"] == "DUPLICATE_UNIT"
    bad = shop.call("POST", url, wtok, json={"name": "Sac", "factor": "0"})
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_FACTOR"
    # existing packagings still cannot be edited by a worker
    r = shop.call(
        "PATCH",
        f"/products/{p['id']}",
        wtok,
        json={"units": [{"name": "Paquet", "factor": "1"}]},
    )
    assert r.status_code == 403
    # the new packaging works at once: 2 cartons = 400 pieces, priced 25 x 200
    r = shop.call(
        "POST",
        "/stock/receive",
        wtok,
        json={"product_id": p["id"], "unit_name": "Carton", "quantity": "2"},
    )
    assert r.status_code == 201 and shop.stock(p["id"]) == 400
    row = shop.call("GET", "/products").json()[0]
    assert D(next(u for u in row["units"] if u["name"] == "Carton")["price"]) == 5000
    actions = [a["action"] for a in shop.call("GET", "/admin/audit").json()["items"]]
    assert "PRODUCT_UNIT_ADDED" in actions


def test_worker_cannot_delete_or_edit_invoices(shop):
    wtok, _ = shop.worker()
    inv = make_invoice(shop, wtok)
    for method in ("DELETE", "PUT", "PATCH"):
        r = shop.call(method, f"/invoices/{inv['id']}", wtok, json={"total": "1"})
        assert r.status_code == 403 and r.json()["code"] == "WORKER_FORBIDDEN", method
    assert (
        shop.call("GET", f"/invoices/{inv['id']}", wtok).json()["status"] == "COMPLETED"
    )


def test_even_owner_cannot_delete_invoice(shop):
    inv = make_invoice(shop)
    r = shop.call("DELETE", f"/invoices/{inv['id']}")
    assert r.status_code == 409 and r.json()["code"] == "INVOICE_IMMUTABLE"
    assert shop.call("GET", f"/invoices/{inv['id']}").status_code == 200


def test_database_triggers_block_direct_tampering(shop):
    inv = make_invoice(shop)
    con = sqlite3.connect(config.db_path())
    for sql in (
        "DELETE FROM invoices",
        "UPDATE invoices SET total='1'",
        "DELETE FROM invoice_lines",
        "UPDATE invoice_lines SET unit_price='1'",
        "DELETE FROM audit_log",
        "UPDATE audit_log SET reason='x'",
        "DELETE FROM ledger",
        "UPDATE ledger SET amount='1'",
    ):
        with pytest.raises(sqlite3.DatabaseError):
            con.execute(sql)
    con.close()


# ---------------- void requires admin password + reason; reverses stock & cash; audited
def test_void_flow_requires_admin_password_reason_and_reverses_everything(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10")
    wtok, w = shop.worker()
    inv = make_invoice(shop, wtok, p["id"], "4")  # 3000 cash, stock 6
    assert shop.stock(p["id"]) == 6 and shop.balances()[0] == 3000
    url = f"/invoices/{inv['id']}/void"

    assert (
        shop.call("POST", url, wtok, json={"reason": "erreur"}).status_code == 422
    )  # no password
    r = shop.call(
        "POST", url, wtok, json={"reason": "erreur", "admin_password": "nope-nope"}
    )
    assert r.status_code == 403 and r.json()["code"] == "ADMIN_PASSWORD_INVALID"
    assert (
        shop.call(
            "POST", url, wtok, json={"reason": "", "admin_password": ADMIN}
        ).status_code
        == 422
    )  # no reason
    assert shop.stock(p["id"]) == 6  # nothing changed yet

    r = shop.call(
        "POST",
        url,
        wtok,
        json={"reason": "Mauvais article saisi", "admin_password": ADMIN},
    )
    assert r.status_code == 200
    v = r.json()
    assert v["status"] == "VOIDED" and v["void_reason"] == "Mauvais article saisi"
    assert (
        shop.stock(p["id"]) == 10 and shop.balances()[0] == 0
    )  # stock + cash automatically reversed
    again = shop.call(
        "POST", url, wtok, json={"reason": "encore", "admin_password": ADMIN}
    )
    assert again.status_code == 409

    entry = [
        a
        for a in shop.call("GET", "/admin/audit").json()["items"]
        if a["action"] == "INVOICE_VOIDED"
    ][0]
    assert (
        entry["actor"] == w["name"]
        and entry["reason"] == "Mauvais article saisi"
        and inv["receipt_no"] in entry["details"]
    )


def test_price_override_needs_admin_password_and_is_audited(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10")
    wtok, _ = shop.worker()
    line = {"product_id": p["id"], "quantity": "1", "unit_price": "100"}
    r = shop.call("POST", "/invoices", wtok, json={"lines": [line]})
    assert r.status_code == 403 and r.json()["code"] == "ADMIN_PASSWORD_REQUIRED"
    r = shop.call(
        "POST",
        "/invoices",
        wtok,
        json={"lines": [line], "admin_password": "bad-bad-bad"},
    )
    assert r.status_code == 403
    assert (
        shop.stock(p["id"]) == 10 and shop.call("GET", "/invoices").json() == []
    )  # nothing was sold
    r = shop.call(
        "POST",
        "/invoices",
        wtok,
        json={"lines": [line], "admin_password": ADMIN, "override_reason": "remise"},
    )
    assert r.status_code == 201 and r.json()["lines"][0]["price_overridden"] is True
    assert D(r.json()["total"]) == 100
    # same price as the catalog is NOT an override and needs no password
    ok = shop.call(
        "POST",
        "/invoices",
        wtok,
        json={"lines": [{"product_id": p["id"], "quantity": "1", "unit_price": "750"}]},
    )
    assert ok.status_code == 201
    assert any(
        a["action"] == "PRICE_OVERRIDE"
        for a in shop.call("GET", "/admin/audit").json()["items"]
    )


def test_admin_password_lockout_after_repeated_failures(shop):
    inv = make_invoice(shop)
    for _ in range(5):
        r = shop.call(
            "POST",
            f"/invoices/{inv['id']}/void",
            json={"reason": "test", "admin_password": "wrong-wrong"},
        )
        assert r.status_code == 403
    r = shop.call(
        "POST",
        f"/invoices/{inv['id']}/void",
        json={"reason": "test", "admin_password": ADMIN},
    )
    assert r.status_code == 429  # locked even for the right password for a few minutes


# ---------------- roles
def test_worker_role_boundaries(shop):
    wtok, _ = shop.worker()
    for method, url in [
        ("GET", "/workers"),
        ("POST", "/workers"),
        ("GET", "/reports/summary"),
        ("GET", "/dashboard"),
        ("GET", "/finance/balances"),
        ("POST", "/finance/expenses"),
        ("GET", "/reports/insights"),
        ("POST", "/finance/customer-deposits/refund"),
        ("GET", "/finance/ledger"),
        ("POST", "/stock/adjust"),
        ("GET", "/admin/overview"),
        ("POST", "/backup/export"),
    ]:
        r = shop.call(method, url, wtok, json={})
        assert r.status_code == 403, (method, url, r.status_code)
    # customer credit is now a staff task (record only; supplier payables stay hidden)
    assert shop.call("GET", "/finance/debts", wtok).status_code == 200


def test_worker_sees_only_own_sales(shop):
    t1, _ = shop.worker(name="Awa")
    t2, _ = shop.worker(name="Bako")
    a = make_invoice(shop, t1)
    make_invoice(shop, t2)
    assert [i["id"] for i in shop.call("GET", "/invoices", t1).json()] == [a["id"]]
    assert len(shop.call("GET", "/invoices").json()) == 2  # owner sees all
    other = [i for i in shop.call("GET", "/invoices").json() if i["id"] != a["id"]][0]
    assert shop.call("GET", f"/invoices/{other['id']}", t1).status_code == 404


def test_dds_admin_has_no_access_to_sales_or_finance(shop):
    import os

    creds = (config.data_dir() / "DDS_ADMIN_CREDENTIALS.txt").read_text().splitlines()
    pw = creds[1].split(": ")[1]
    r = shop.c.post(
        "/api/v1/auth/login",
        json={"identifier": "dds-admin", "password": pw, "role": "admin"},
    )
    assert r.status_code == 200
    tok = r.json()["token"]
    assert shop.call("GET", "/admin/overview", tok).status_code == 200
    for url in ("/invoices", "/finance/balances", "/dashboard", "/products"):
        assert shop.call("GET", url, tok).status_code == 403, url
    # DDS cannot learn or reset the owner's admin password: no endpoint exposes it
    assert (
        shop.call(
            "POST",
            "/owner/admin-password",
            tok,
            json={"new_admin_password": "hacked-123"},
        ).status_code
        == 403
    )


def test_credit_sale_permission_enforced(shop):
    c = shop.call("POST", "/customers", json={"name": "Fatou"}).json()
    no_credit, _ = shop.worker(credit=False, name="Awa")
    r = shop.call(
        "POST",
        "/invoices",
        no_credit,
        json={
            "lines": [{"quantity": "1", "unit_price": "100"}],
            "payment_method": "credit",
            "customer_id": c["id"],
        },
    )
    assert r.status_code == 403 and r.json()["code"] == "CREDIT_NOT_ALLOWED"


def test_passwords_hashed_with_argon2id_and_never_returned_again(shop):
    con = sqlite3.connect(config.db_path())
    hashes = [r[0] for r in con.execute("SELECT password_hash FROM users")] + [
        r[0]
        for r in con.execute("SELECT value FROM settings WHERE key='owner_admin_hash'")
    ]
    assert hashes and all(h.startswith("$argon2id$") for h in hashes)
    assert "password" not in str(shop.call("GET", "/workers").json())


def test_login_lockout_and_recovery(shop):
    _, w = shop.worker()
    for _ in range(5):
        assert (
            shop.c.post(
                "/api/v1/auth/login",
                json={"identifier": w["username"], "password": "x" * 8},
            ).status_code
            == 401
        )
    assert (
        shop.c.post(
            "/api/v1/auth/login",
            json={"identifier": w["username"], "password": w["password"]},
        ).status_code
        == 429
    )
    r = shop.c.post(
        "/api/v1/auth/recover",
        json={
            "identifier": shop.owner_user["username"],
            "recovery_code": shop.recovery,
            "new_password": "brand-new-pw",
        },
    )
    assert r.status_code == 200
    assert (
        shop.c.post(
            "/api/v1/auth/login",
            json={
                "identifier": shop.owner_user["username"],
                "password": "brand-new-pw",
            },
        ).status_code
        == 200
    )


def test_audit_chain_is_verifiable(shop):
    inv = make_invoice(shop)
    shop.call(
        "POST",
        f"/invoices/{inv['id']}/void",
        json={"reason": "test void", "admin_password": ADMIN},
    )
    chain = shop.call("GET", "/admin/audit").json()["chain"]
    assert chain["ok"] is True and chain["checked"] >= 2
