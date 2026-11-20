"""Customer credit / advances (staff can record, nobody can rewrite) and owner insight reports."""
import sqlite3
from decimal import Decimal

from app import config

D = Decimal
ADMIN = "admin-secret-9"


def credit(shop, token=None, **extra):
    body = {"customer_name": "Fatoumata", "customer_phone": "76000000", "lines": []}
    body.update(extra)
    return shop.call("POST", "/finance/customer-credit", token, json=body)


# ------------------------------------------------------------------ credit
def test_worker_records_credit_with_items_and_actor(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10", cost="500")
    wtok, w = shop.worker(credit=True)
    r = credit(shop, wtok, lines=[{"product_id": p["id"], "quantity": "2"}])
    assert r.status_code == 201, r.text
    d = r.json()["debt"]
    assert D(d["balance"]) == 1500 and d["items"] == ["Riz × 2 Kg"] and d["recorded_by"] == w["name"]
    assert shop.stock(p["id"]) == 8
    cust = shop.call("GET", "/customers", wtok).json()[0]
    assert cust["phone"] == "76000000"
    # worker sees receivables only, and can record the repayment
    lst = shop.call("GET", "/finance/debts", wtok, params={"direction": "PAYABLE"}).json()
    assert all(i["direction"] == "RECEIVABLE" for i in lst["items"]) and D(lst["total_payable"]) == 0
    rp = shop.call("POST", f"/finance/debts/{d['id']}/payments", wtok, json={"amount": "500", "method": "cash"})
    assert rp.status_code == 201 and D(rp.json()["balance"]) == 1000
    # repayment is never revenue
    s = shop.call("GET", "/reports/summary").json()
    assert D(s["revenue"]) == 1500
    actions = [a["action"] for a in shop.call("GET", "/admin/audit").json()["items"]]
    assert "CUSTOMER_CREDIT" in actions and "DEBT_REPAYMENT" in actions


def test_credit_needs_customer_phone_permission_and_real_credit(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10")
    wtok, _ = shop.worker(credit=True)
    line = [{"product_id": p["id"], "quantity": "1"}]
    assert credit(shop, wtok, lines=line, customer_phone="").json()["code"] == "PHONE_REQUIRED"
    assert credit(shop, wtok, lines=line, customer_name="").json()["code"] == "CUSTOMER_REQUIRED"
    nocred, _ = shop.worker(credit=False, name="Oumar")
    r = credit(shop, nocred, lines=line)
    assert r.status_code == 403 and r.json()["code"] == "CREDIT_NOT_ALLOWED"
    r = credit(shop, wtok, lines=line, paid_amount="750")
    assert r.status_code == 422 and r.json()["code"] == "NOT_A_CREDIT"
    assert shop.stock(p["id"]) == 10  # rejected credit changed nothing
    # a worker cannot hide a cheaper price: override needs the owner admin password
    r = credit(shop, wtok, lines=[{"product_id": p["id"], "quantity": "1", "unit_price": "1"}])
    assert r.status_code == 403 and r.json()["code"] == "ADMIN_PASSWORD_REQUIRED"


def test_credit_history_cannot_be_edited_or_deleted(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10")
    wtok, _ = shop.worker(credit=True)
    d = credit(shop, wtok, lines=[{"product_id": p["id"], "quantity": "1"}]).json()["debt"]
    shop.call("POST", f"/finance/debts/{d['id']}/payments", wtok, json={"amount": "100", "method": "cash"})
    for method in ("PATCH", "PUT", "DELETE"):
        assert shop.call(method, f"/finance/debts/{d['id']}", wtok).status_code in (404, 405)
    con = sqlite3.connect(config.db_path())
    for sql in ("DELETE FROM debts", "UPDATE debts SET original_amount = '1'",
                "UPDATE debts SET customer_id = 999", "DELETE FROM debt_payments"):
        try:
            con.execute(sql)
            raise AssertionError(f"not blocked: {sql}")
        except sqlite3.DatabaseError:
            pass
    con.close()


# ------------------------------------------------------------------ deposits
def test_deposit_is_cash_in_but_not_revenue_and_can_pay_a_credit(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10")
    wtok, _ = shop.worker(credit=True)
    cash0, _ = shop.balances()
    r = shop.call("POST", "/finance/customer-deposits", wtok,
                  json={"customer_name": "Awa", "customer_phone": "70", "amount": "1000", "method": "cash"})
    assert r.status_code == 201 and D(r.json()["deposit_balance"]) == 1000
    cid = r.json()["customer_id"]
    assert shop.balances()[0] - cash0 == 1000
    assert D(shop.call("GET", "/reports/summary").json()["revenue"]) == 0
    d = credit(shop, wtok, customer_id=cid, lines=[{"product_id": p["id"], "quantity": "2"}]).json()["debt"]
    assert D(d["deposit_balance"]) == 1000 and D(d["balance"]) == 1500
    over = shop.call("POST", f"/finance/debts/{d['id']}/apply-deposit", wtok, json={"amount": "1200"})
    assert over.status_code == 422 and over.json()["code"] == "INSUFFICIENT_DEPOSIT"
    ok = shop.call("POST", f"/finance/debts/{d['id']}/apply-deposit", wtok, json={"amount": "1000"})
    assert ok.status_code == 201 and D(ok.json()["balance"]) == 500 and D(ok.json()["deposit_balance"]) == 0
    assert shop.balances()[0] - cash0 == 1000  # applying an advance moves no new cash
    acc = shop.call("GET", "/finance/customer-accounts", wtok).json()
    assert acc[0]["customer_id"] == cid and D(acc[0]["owed"]) == 500
    hist = shop.call("GET", f"/finance/customers/{cid}/history", wtok).json()
    assert [e["kind"] for e in hist["deposits"]] == ["APPLY", "DEPOSIT"] and hist["deposits"][0]["by"]


def test_voiding_a_credit_returns_the_applied_advance(shop):
    p = shop.product("Riz", base="Kg", price="750", stock="10")
    cid = shop.call("POST", "/finance/customer-deposits",
                    json={"customer_name": "Awa", "customer_phone": "70", "amount": "700"}).json()["customer_id"]
    out = credit(shop, customer_id=cid, lines=[{"product_id": p["id"], "quantity": "2"}]).json()
    shop.call("POST", f"/finance/debts/{out['debt']['id']}/apply-deposit", json={"amount": "700"})
    r = shop.call("POST", f"/invoices/{out['invoice']['id']}/void", json={"reason": "erreur", "admin_password": ADMIN})
    assert r.status_code == 200, r.text
    assert D(shop.call("GET", f"/finance/customers/{cid}/history").json()["deposit_balance"]) == 700
    assert shop.stock(p["id"]) == 10


def test_deposit_refund_is_owner_with_admin_password_only_and_deposits_are_append_only(shop):
    wtok, _ = shop.worker()
    cid = shop.call("POST", "/finance/customer-deposits", wtok,
                    json={"customer_name": "Awa", "customer_phone": "70", "amount": "700"}).json()["customer_id"]
    body = {"customer_id": cid, "amount": "200"}
    assert shop.call("POST", "/finance/customer-deposits/refund", wtok, json=body).status_code == 403
    assert shop.call("POST", "/finance/customer-deposits/refund", json=body).json()["code"] == "ADMIN_PASSWORD_REQUIRED"
    ok = shop.call("POST", "/finance/customer-deposits/refund", json={**body, "admin_password": ADMIN})
    assert ok.status_code == 200 and D(ok.json()["deposit_balance"]) == 500
    con = sqlite3.connect(config.db_path())
    for sql in ("DELETE FROM customer_balance_entries", "UPDATE customer_balance_entries SET amount = '9'"):
        try:
            con.execute(sql)
            raise AssertionError(f"not blocked: {sql}")
        except sqlite3.DatabaseError:
            pass
    con.close()


# ------------------------------------------------------------------ reports
def sell(shop, pid, qty, price=None):
    line = {"product_id": pid, "quantity": str(qty)}
    if price:
        line["unit_price"] = price
    body = {"lines": [line]}
    if price:
        body["admin_password"] = ADMIN
    r = shop.call("POST", "/invoices", json=body)
    assert r.status_code == 201, r.text


def test_period_filter_is_real_and_top20_ranked_by_qty_and_profit(shop):
    a = shop.product("Riz", base="Kg", price="1000", cost="900", stock="500")   # many units, thin profit
    b = shop.product("Huile", base="Litre", price="2000", cost="500", stock="500")  # few units, big profit
    sell(shop, a["id"], 10)
    sell(shop, b["id"], 3)
    for per in ("day", "week", "month"):
        d = shop.call("GET", "/dashboard", params={"period": per}).json()
        assert D(d["summary"]["revenue"]) == 16000 and d["period"]["key"] == per
    assert shop.call("GET", "/dashboard", params={"period": "year"}).status_code == 422
    old = shop.call("GET", "/dashboard", params={"date_from": "2020-01-01", "date_to": "2020-01-02"}).json()
    assert D(old["summary"]["revenue"]) == 0  # explicit dates really change the query
    ins = shop.call("GET", "/reports/insights", params={"period": "week"}).json()
    assert [r["label"] for r in ins["top_by_qty"]] == ["Riz", "Huile"]
    assert [r["label"] for r in ins["top_by_profit"]] == ["Huile", "Riz"]
    assert D(ins["top_by_profit"][0]["profit"]) == 4500 and ins["top_by_profit"][0]["margin_pct"] == "75.0"
    assert ins["peak_hours"] and ins["peak_hours"][0]["invoices"] == 2
    top = ins["peak_hours"][0]["top_products"]
    assert top[0]["label"] == "Riz" and len(ins["hours"]) == 24
    assert shop.call("GET", "/reports/insights", token=shop.worker()[0]).status_code == 403


def test_top_list_is_capped_at_20(shop):
    for i in range(23):
        p = shop.product(f"P{i:02d}", price="100", stock="10", cost="10")
        sell(shop, p["id"], 1)
    ins = shop.call("GET", "/reports/insights", params={"period": "day"}).json()
    assert len(ins["top_by_qty"]) == 20 and len(ins["top_by_profit"]) == 20


def test_diagnostics_flag_losses_margin_restock_dead_stock_credit_and_register(shop):
    loss = shop.product("Sucre", base="Kg", price="500", cost="450", stock="50")
    thin = shop.product("Lait", base="Boite", price="1000", cost="950", stock="50")
    fast = shop.product("Pain", base="Pièce", price="100", cost="50", stock="6")
    dead = shop.product("Bougie", base="Pièce", price="100", cost="40", stock="30")
    sell(shop, loss["id"], 2, price="300")   # sold under cost (needs admin password override)
    sell(shop, thin["id"], 1)
    sell(shop, fast["id"], 5)
    wtok, _ = shop.worker(credit=True)
    credit(shop, wtok, lines=[{"product_id": thin["id"], "quantity": "1"}])
    shop.call("POST", "/finance/register/open", json={"opening_cash": "0"})
    shop.call("POST", "/finance/register/close", json={"counted_cash": "1", "counted_mobile": "0"})
    ins = shop.call("GET", "/reports/insights",
                    params={"period": "day", "dead_days": 0, "overdue_days": 0}).json()
    by = {a["type"]: a for a in ins["diagnostics"]}
    assert {"LOSS_SALES", "LOW_MARGIN", "RESTOCK", "DEAD_STOCK", "OVERDUE_CREDIT", "REGISTER_DIFF"} <= set(by)
    assert by["LOSS_SALES"]["items"][0]["label"] == "Sucre" and D(by["LOSS_SALES"]["items"][0]["loss"]) == 300
    assert by["LOW_MARGIN"]["items"][0]["label"] == "Lait"
    assert by["RESTOCK"]["items"][0]["label"] == "Pain" and D(by["RESTOCK"]["items"][0]["suggested_qty"]) >= 1
    assert "Bougie" in [i["label"] for i in by["DEAD_STOCK"]["items"]]
    assert D(by["OVERDUE_CREDIT"]["total"]) == 1000
    assert by["REGISTER_DIFF"]["items"][0]["diff_cash"] != "0"
    assert ins["diagnostics"][0]["severity"] == "high"
    # with the default thresholds nothing is "overdue" or "dead" yet
    d2 = shop.call("GET", "/reports/insights").json()
    assert not {"DEAD_STOCK", "OVERDUE_CREDIT"} & {a["type"] for a in d2["diagnostics"]}
    # a catalog price below cost is flagged too
    shop.call("PATCH", f"/products/{dead['id']}", json={"price": "10", "admin_password": ADMIN})
    d3 = shop.call("GET", "/reports/insights").json()
    assert "PRICE_BELOW_COST" in {a["type"] for a in d3["diagnostics"]}


def test_create_product_with_initial_stock_in_cartons(shop):
    wtok, _ = shop.worker()
    r = shop.call("POST", "/products", wtok, json={
        "name_fr": "Lait", "base_unit": "Boite", "price": "500", "cost": "400",
        "units": [{"name": "Carton", "factor": "12"}], "initial_stock": "5", "initial_stock_unit": "Carton"})
    assert r.status_code == 200, r.text
    assert shop.stock(r.json()["id"]) == 60
    bad = shop.call("POST", "/products", wtok, json={
        "name_fr": "Thé", "base_unit": "Boite", "price": "1", "initial_stock": "1", "initial_stock_unit": "Palette"})
    assert bad.status_code == 422
