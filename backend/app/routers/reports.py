"""Owner dashboard + reports. Revenue = completed invoice totals ONLY
(debt repayments and stock purchases are cash movements, never revenue)."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..db import get_db
from ..models import Debt, Expense, Invoice, InvoiceLine, LedgerEntry, Product, RegisterSession, User
from ..services.finance import balances, local_tz, range_bounds, resolve_period
from ..services.units import ZERO

router = APIRouter(tags=["reports"])
owner_only = security.require_roles(security.OWNER)


def _period(db: Session, d_from: date | None, d_to: date | None) -> dict:
    a, b = range_bounds(d_from, d_to)
    invs = db.execute(select(Invoice).where(Invoice.created_at >= a, Invoice.created_at < b)).scalars().all()
    done = [i for i in invs if i.status == "COMPLETED"]
    revenue = sum((i.total for i in done), ZERO)
    cogs = ZERO
    direct_rev = ZERO
    prod_tot: dict[str, list] = defaultdict(lambda: [ZERO, ZERO])
    for i in done:
        for l in i.lines:
            cogs += l.cost_total
            if l.product_id is None:
                direct_rev += l.line_total
            t = prod_tot[l.label]
            t[0] += l.base_qty
            t[1] += l.line_total
    expenses = sum((e.amount for e in db.execute(select(Expense).where(Expense.created_at >= a, Expense.created_at < b)).scalars()), ZERO)
    led = list(db.execute(select(LedgerEntry).where(LedgerEntry.created_at >= a, LedgerEntry.created_at < b)).scalars())
    sale_cash_in = sum((e.amount for e in led if e.kind == "SALE"), ZERO)
    repay_in = sum((e.amount for e in led if e.kind == "DEBT_REPAYMENT"), ZERO)
    by_worker: dict[str, list] = defaultdict(lambda: [0, ZERO])
    names = {}
    for i in done:
        names.setdefault(i.worker_id, db.get(User, i.worker_id).name)
        by_worker[names[i.worker_id]][0] += 1
        by_worker[names[i.worker_id]][1] += i.total
    by_method: dict[str, object] = defaultdict(lambda: ZERO)
    for i in done:
        by_method[i.payment_method] += i.total
    best = sorted(prod_tot.items(), key=lambda kv: kv[1][1], reverse=True)[:5]
    return {
        "revenue": str(revenue), "invoices": len(done), "voided": len(invs) - len(done),
        "gross_profit_catalog": str(sum((l.line_total - l.cost_total for i in done for l in i.lines if l.product_id), ZERO)),
        "cogs_catalog": str(cogs), "direct_sales_revenue": str(direct_rev), "expenses": str(expenses),
        "cash_in_from_sales": str(sale_cash_in), "cash_in_from_debt_repayments": str(repay_in),
        "net": str(revenue - cogs - expenses),
        "by_worker": [{"worker": k, "invoices": v[0], "revenue": str(v[1])} for k, v in by_worker.items()],
        "by_payment_method": {k: str(v) for k, v in by_method.items()},
        "best_sellers": [{"label": k, "qty": str(v[0]), "revenue": str(v[1])} for k, v in best],
    }


@router.get("/reports/summary")
def summary(date_from: date | None = None, date_to: date | None = None, period: str | None = None,
            db: Session = Depends(get_db), user: User = Depends(owner_only)):
    a, b = resolve_period(period, date_from, date_to)
    return _period(db, a, b)


@router.get("/dashboard")
def dashboard(date_from: date | None = None, date_to: date | None = None, period: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(owner_only)):
    date_from, date_to = resolve_period(period, date_from, date_to)
    a, b = range_bounds(date_from, date_to)
    per = _period(db, date_from, date_to)
    recv = _received(db, a, b)
    bal = balances(db)
    debts = list(db.execute(select(Debt).where(Debt.status == "OPEN")).scalars())
    all_products = list(db.execute(select(Product).where(Product.active == True)).scalars())  # noqa: E712
    low = [p for p in all_products if p.stock_qty <= p.low_stock_threshold]
    recv_ops = len([e for e in db.execute(select(LedgerEntry).where(
        LedgerEntry.created_at >= a, LedgerEntry.created_at < b,
        LedgerEntry.kind.in_(("SALE", "DEBT_REPAYMENT")))).scalars() if e.amount > 0])
    exp_count = len(list(db.execute(select(Expense).where(Expense.created_at >= a, Expense.created_at < b)).scalars()))
    recent = []
    for e in db.execute(select(LedgerEntry).where(LedgerEntry.created_at >= a, LedgerEntry.created_at < b)
                        .order_by(LedgerEntry.id.desc()).limit(8)).scalars():
        recent.append({"kind": e.kind, "amount": str(e.amount), "note": e.note, "method": e.method,
                       "created_at": e.created_at.isoformat()})
    return {
        "period": {"key": period or "day", "from": date_from.isoformat(), "to": date_to.isoformat()},
        "received": str(recv),
        "spent": per["expenses"], "available": str(bal["CASH"] + bal["MOBILE"]),
        "cash": str(bal["CASH"]), "mobile": str(bal["MOBILE"]),
        "balance": str(recv - _num(per["expenses"])),
        "receivables": str(sum((d.balance for d in debts if d.direction == "RECEIVABLE"), ZERO)),
        "payables": str(sum((d.balance for d in debts if d.direction == "PAYABLE"), ZERO)),
        "low_stock": [{"id": p.id, "name_fr": p.name_fr, "name_ar": p.name_ar, "stock_qty": str(p.stock_qty),
                       "base_unit": p.base_unit} for p in low],
        "best_sellers": per["best_sellers"], "recent": recent, "summary": per,
        "products_count": len(all_products),
        "low_count": len([p for p in all_products if 0 < p.stock_qty <= p.low_stock_threshold]),
        "out_count": len([p for p in all_products if p.stock_qty <= 0]),
        "receivable_people": len({d.customer_id for d in debts if d.direction == "RECEIVABLE"}),
        "payable_people": len({d.supplier_id for d in debts if d.direction == "PAYABLE"}),
        "received_ops": recv_ops, "expense_count": exp_count,
    }


def _num(s: str):
    from decimal import Decimal
    return Decimal(s)


def _received(db: Session, a, b):
    rows = db.execute(select(LedgerEntry).where(
        LedgerEntry.created_at >= a, LedgerEntry.created_at < b,
        LedgerEntry.kind.in_(("SALE", "DEBT_REPAYMENT")))).scalars()
    return sum((e.amount for e in rows if e.amount > 0), ZERO)


# --------------------------------------------------------------------------- insights
def _pct(profit: Decimal, revenue: Decimal) -> str:
    return str(round(profit * 100 / revenue, 1)) if revenue > 0 else "0"


@router.get("/reports/insights")
def insights(
    period: str | None = None, date_from: date | None = None, date_to: date | None = None,
    top: int = Query(20, ge=1, le=50), low_margin_pct: int = Query(10, ge=0, le=100),
    dead_days: int = Query(30, ge=0, le=365), overdue_days: int = Query(30, ge=0, le=365),
    velocity_days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db), user: User = Depends(owner_only),
):
    """Top sellers, peak hours and 'what is wrong / what to do' alerts. Uses the same invoice-line cost
    snapshots as the profit report, so numbers always match the rest of the app."""
    d_from, d_to = resolve_period(period, date_from, date_to)
    a, b = range_bounds(d_from, d_to)
    tz = local_tz()
    now = datetime.now(timezone.utc)
    products = {p.id: p for p in db.execute(select(Product)).scalars()}

    invs = [i for i in db.execute(select(Invoice).where(Invoice.created_at >= a, Invoice.created_at < b,
                                                        Invoice.status == "COMPLETED")).scalars()]
    # ---- per product totals + hourly buckets (catalog lines only: direct sales have no cost)
    agg: dict[int, dict] = {}
    hours = {h: {"hour": h, "invoices": 0, "revenue": ZERO} for h in range(24)}
    hour_prod: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    hour_cat: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for i in invs:
        h = i.created_at.astimezone(tz).hour
        hours[h]["invoices"] += 1
        hours[h]["revenue"] += i.total
        for l in i.lines:
            if not l.product_id:
                continue
            t = agg.setdefault(l.product_id, {"qty": ZERO, "revenue": ZERO, "cost": ZERO, "loss_lines": ZERO})
            t["qty"] += l.base_qty
            t["revenue"] += l.line_total
            t["cost"] += l.cost_total
            if l.cost_total > l.line_total:
                t["loss_lines"] += l.cost_total - l.line_total
            p = products.get(l.product_id)
            hour_prod[h][l.label] += l.base_qty
            hour_cat[h][(p.category if p and p.category else "—")] += l.base_qty

    def row(pid: int, t: dict) -> dict:
        p = products.get(pid)
        profit = t["revenue"] - t["cost"]
        return {"product_id": pid, "label": p.name_fr if p else "?", "name_ar": p.name_ar if p else None,
                "base_unit": p.base_unit if p else "", "qty": str(t["qty"]), "revenue": str(t["revenue"]),
                "cost": str(t["cost"]), "profit": str(profit), "margin_pct": _pct(profit, t["revenue"])}

    rows = [row(pid, t) for pid, t in agg.items()]
    top_qty = sorted(rows, key=lambda r: (Decimal(r["qty"]), Decimal(r["profit"])), reverse=True)[:top]
    top_profit = sorted(rows, key=lambda r: (Decimal(r["profit"]), Decimal(r["qty"])), reverse=True)[:top]

    # ---- peak hours
    hour_list = [{"hour": h["hour"], "invoices": h["invoices"], "revenue": str(h["revenue"])} for h in hours.values()]
    ranked = sorted((h for h in hours.values() if h["invoices"] > 0),
                    key=lambda h: (h["revenue"], h["invoices"]), reverse=True)[:3]
    peak = []
    for h in ranked:
        hp = sorted(hour_prod[h["hour"]].items(), key=lambda kv: kv[1], reverse=True)[:3]
        hc = sorted(hour_cat[h["hour"]].items(), key=lambda kv: kv[1], reverse=True)[:3]
        peak.append({"hour": h["hour"], "invoices": h["invoices"], "revenue": str(h["revenue"]),
                     "top_products": [{"label": k, "qty": str(v)} for k, v in hp],
                     "top_categories": [{"category": k, "qty": str(v)} for k, v in hc]})

    # ---- diagnostics -------------------------------------------------------------
    alerts: list[dict] = []

    def add(kind: str, severity: str, items: list[dict], **extra):
        if items:
            alerts.append({"type": kind, "severity": severity, "count": len(items), "items": items, **extra})

    # 1. sold at a loss in the period
    add("LOSS_SALES", "high", [
        {**row(pid, t), "loss": str(t["loss_lines"])} for pid, t in agg.items() if t["loss_lines"] > 0])
    # 2. catalog price currently below cost
    add("PRICE_BELOW_COST", "high", [
        {"product_id": p.id, "label": p.name_fr, "price": str(p.price), "cost": str(p.cost)}
        for p in products.values() if p.active and p.cost > 0 and p.price < p.cost])
    # 3. abnormally low margin (still positive)
    lm = []
    for pid, t in agg.items():
        if t["revenue"] > 0 and t["loss_lines"] == 0 and t["cost"] > 0:
            pr = t["revenue"] - t["cost"]
            if pr * 100 / t["revenue"] < low_margin_pct:
                lm.append(row(pid, t))
    add("LOW_MARGIN", "medium", lm, threshold_pct=low_margin_pct)

    # 4. fast movers running low  (velocity over the last N days, independent of the selected period)
    v_start = now - timedelta(days=velocity_days)
    sold: dict[int, Decimal] = defaultdict(lambda: ZERO)
    last_sale: dict[int, datetime] = {}
    for l, created in db.execute(select(InvoiceLine, Invoice.created_at).join(Invoice, Invoice.id == InvoiceLine.invoice_id)
                                 .where(Invoice.status == "COMPLETED", InvoiceLine.product_id.is_not(None))):
        if created >= v_start:
            sold[l.product_id] += l.base_qty
        if l.product_id not in last_sale or created > last_sale[l.product_id]:
            last_sale[l.product_id] = created
    restock = []
    for pid, qty in sold.items():
        p = products.get(pid)
        if not p or not p.active or qty <= 0:
            continue
        per_day = qty / velocity_days
        days_left = (p.stock_qty / per_day) if p.stock_qty > 0 else Decimal(0)
        if days_left < 7 or p.stock_qty <= p.low_stock_threshold:
            need = max(Decimal(1), Decimal(math.ceil(per_day * 14 - p.stock_qty)))
            restock.append({"product_id": pid, "label": p.name_fr, "name_ar": p.name_ar, "base_unit": p.base_unit,
                            "stock_qty": str(p.stock_qty), "sold_per_day": str(round(per_day, 2)),
                            "days_left": str(round(days_left, 1)), "suggested_qty": str(need)})
    restock.sort(key=lambda r: Decimal(r["days_left"]))
    add("RESTOCK", "high" if any(Decimal(r["stock_qty"]) <= 0 for r in restock) else "medium", restock,
        cover_days=14)

    # 5. dead stock: on the shelf, old enough, nothing sold for `dead_days`
    cutoff = now - timedelta(days=dead_days)
    dead = []
    for p in products.values():
        if not p.active or p.stock_qty <= 0 or p.created_at > cutoff:
            continue
        ls = last_sale.get(p.id)
        if ls is None or ls <= cutoff:
            dead.append({"product_id": p.id, "label": p.name_fr, "name_ar": p.name_ar, "base_unit": p.base_unit,
                         "stock_qty": str(p.stock_qty), "stock_value": str(p.stock_qty * p.cost),
                         "days_since_sale": (now - ls).days if ls else None})
    dead.sort(key=lambda r: Decimal(r["stock_value"]), reverse=True)
    add("DEAD_STOCK", "low", dead, days=dead_days)

    # 6. unpaid customer credits older than `overdue_days`
    od_cut = now - timedelta(days=overdue_days)
    od = []
    from ..models import Customer
    for d in db.execute(select(Debt).where(Debt.direction == "RECEIVABLE", Debt.status == "OPEN")).scalars():
        if d.created_at <= od_cut:
            c = db.get(Customer, d.customer_id) if d.customer_id else None
            od.append({"debt_id": d.id, "party_name": c.name if c else "?", "phone": c.phone if c else None,
                       "balance": str(d.balance), "days": (now - d.created_at).days})
    od.sort(key=lambda r: r["days"], reverse=True)
    add("OVERDUE_CREDIT", "high" if any(r["days"] > 60 for r in od) else "medium", od, days=overdue_days,
        total=str(sum((Decimal(r["balance"]) for r in od), ZERO)))

    # 7. register open/close discrepancies (last 30 days)
    reg = []
    for r in db.execute(select(RegisterSession).where(RegisterSession.status == "CLOSED",
                                                      RegisterSession.closed_at >= now - timedelta(days=30))
                        .order_by(RegisterSession.id.desc())).scalars():
        if (r.diff_cash or ZERO) != 0 or (r.diff_mobile or ZERO) != 0:
            w = db.get(User, r.closed_by) if r.closed_by else None
            reg.append({"register_id": r.id, "closed_at": r.closed_at.isoformat(), "closed_by": w.name if w else None,
                        "diff_cash": str(r.diff_cash or ZERO), "diff_mobile": str(r.diff_mobile or ZERO)})
    add("REGISTER_DIFF", "high", reg)

    order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda x: order[x["severity"]])
    return {"period": {"key": period or "day", "from": d_from.isoformat(), "to": d_to.isoformat()},
            "top_by_qty": top_qty, "top_by_profit": top_profit,
            "hours": hour_list, "peak_hours": peak, "diagnostics": alerts}


# --------------------------------------------------------------------------- bilingual daily Excel (.xlsx)
import io
import zipfile
from xml.sax.saxutils import escape
from fastapi.responses import Response
from ..models import Customer


def _col_ref(col_idx: int) -> str:
    s = ""
    while col_idx > 0:
        col_idx, rem = divmod(col_idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _build_xlsx(sheets: list[tuple[str, list[list[str | int | float]]]]) -> bytes:
    """Generate a valid XLSX workbook using sharedStrings so Excel & Google Sheets display all cells cleanly."""
    shared_strings: list[str] = []
    shared_index: dict[str, int] = {}

    def str_idx(text: str) -> int:
        if text not in shared_index:
            shared_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_index[text]

    wb_sheets = []
    sheet_files: dict[str, bytes] = {}
    for idx, (raw_title, rows) in enumerate(sheets, start=1):
        clean_title = "".join(c for c in raw_title if c not in "[]:*?/\\").strip()
        title = (clean_title or f"Sheet{idx}")[:31]
        wb_sheets.append(f'<sheet name="{escape(title)}" sheetId="{idx}" r:id="rId{idx}"/>')

        max_cols = max((len(r) for r in rows), default=1)
        last_col = _col_ref(max(1, max_cols))
        last_row = max(1, len(rows))
        dim_ref = f"A1:{last_col}{last_row}"

        xml_rows = []
        for r_idx, row in enumerate(rows, start=1):
            cells = []
            for c_idx, val in enumerate(row, start=1):
                if val is None or val == "":
                    continue
                ref = f"{_col_ref(c_idx)}{r_idx}"
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    cells.append(f'<c r="{ref}"><v>{val}</v></c>')
                else:
                    si = str_idx(str(val))
                    cells.append(f'<c r="{ref}" t="s"><v>{si}</v></c>')
            xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<dimension ref="{dim_ref}"/>'
            '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
            f'<sheetData>{"".join(xml_rows)}</sheetData>'
            '</worksheet>'
        )
        sheet_files[f"xl/worksheets/sheet{idx}.xml"] = sheet_xml.encode("utf-8")

    ss_items = [f'<si><t xml:space="preserve">{escape(s)}</t></si>' for s in shared_strings]
    shared_strings_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        f'{"".join(ss_items)}'
        '</sst>'
    )

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>',
    ]
    rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>',
        '</Relationships>',
    ]
    wb_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for idx in range(1, len(sheets) + 1):
        content_types.append(
            f'<Override PartName="/xl/worksheets/sheet{idx}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        wb_rels.append(
            f'<Relationship Id="rId{idx}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{idx}.xml"/>'
        )
    wb_rels.append(
        '<Relationship Id="rIdStyles" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    wb_rels.append(
        '<Relationship Id="rIdSharedStrings" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
        'Target="sharedStrings.xml"/>'
    )
    wb_rels.append("</Relationships>")
    content_types.append("</Types>")

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(wb_sheets)}</sheets>'
        '</workbook>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '</styleSheet>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "".join(content_types).encode("utf-8"))
        zf.writestr("_rels/.rels", "".join(rels).encode("utf-8"))
        zf.writestr("xl/workbook.xml", workbook_xml.encode("utf-8"))
        zf.writestr("xl/_rels/workbook.xml.rels", "".join(wb_rels).encode("utf-8"))
        zf.writestr("xl/styles.xml", styles_xml.encode("utf-8"))
        zf.writestr("xl/sharedStrings.xml", shared_strings_xml.encode("utf-8"))
        for arcname, payload in sheet_files.items():
            zf.writestr(arcname, payload)
    return buf.getvalue()


@router.get("/reports/daily-excel")
def daily_excel(
    period: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(security.require_roles(security.OWNER, security.WORKER, security.DDS)),
):
    """Export a bilingual French + Arabic Excel workbook (.xlsx) for daily, weekly, or custom date ranges."""
    d_from, d_to = resolve_period(period, date_from, date_to)
    a, b = range_bounds(d_from, d_to)
    per = _period(db, d_from, d_to)
    bal = balances(db)

    invs = list(
        db.execute(
            select(Invoice)
            .where(Invoice.created_at >= a, Invoice.created_at < b)
            .order_by(Invoice.id.asc())
        ).scalars()
    )
    debts = list(db.execute(select(Debt).where(Debt.status == "OPEN")).scalars())
    low_prods = list(
        db.execute(
            select(Product).where(Product.active == True, Product.stock_qty <= Product.low_stock_threshold)  # noqa: E712
        ).scalars()
    )
    regs = list(
        db.execute(
            select(RegisterSession)
            .where(RegisterSession.opened_at >= a, RegisterSession.opened_at < b)
            .order_by(RegisterSession.id.asc())
        ).scalars()
    )

    range_label = d_from.isoformat() if d_from == d_to else f"{d_from.isoformat()} -> {d_to.isoformat()}"
    summary_rows: list[list[str | int | float]] = [
        ["Indicateur / المؤشر", "Valeur / القيمة"],
        ["Période (Du -> Au) / الفترة (من -> إلى)", range_label],
        ["Généré par / أعدّه", f"{user.name} ({user.role})"],
        ["Factures validées / الفواتير المكتملة", int(per["invoices"])],
        ["Factures annulées / الفواتير الملغاة", int(per["voided"])],
        ["Chiffre d'affaires (Ventes) / إجمالي المبيعات", float(Decimal(per["revenue"]))],
        ["Entrées caisse - Ventes / مقبوضات المبيعات", float(Decimal(per["cash_in_from_sales"]))],
        ["Entrées caisse - Remboursements dettes / تحصيلات الديون", float(Decimal(per["cash_in_from_debt_repayments"]))],
        ["Dépenses / المصروفات", float(Decimal(per["expenses"]))],
        ["Solde Espèces actuel / رصيد النقد الحالي", float(bal["CASH"])],
        ["Solde Mobile Money actuel / رصيد الموبايل موني الحالي", float(bal["MOBILE"])],
        ["Créances clients ouvertes / ديون العملاء المستحقة", float(sum((x.balance for x in debts if x.direction == "RECEIVABLE"), ZERO))],
        ["Dettes fournisseurs ouvertes / ديون الموردين المستحقة", float(sum((x.balance for x in debts if x.direction == "PAYABLE"), ZERO))],
        ["", ""],
        ["CAISSE / الصندوق", ""],
        ["Ouverture Espèces / رصيد فتح النقد", float(regs[-1].opening_cash) if regs else 0.0],
        ["Fermeture Espèces comptée / النقد المعدود عند الإغلاق", float(regs[-1].counted_cash) if regs and regs[-1].counted_cash is not None else ""],
        ["Écart Espèces / فرق النقد", float(regs[-1].diff_cash) if regs and regs[-1].diff_cash is not None else ""],
        ["Écart Mobile Money / فرق الموبايل موني", float(regs[-1].diff_mobile) if regs and regs[-1].diff_mobile is not None else ""],
        ["", ""],
        ["STOCK BAS / RUPTURE / نواقص المخزون", ""],
    ]
    for p_item in low_prods:
        summary_rows.append([
            f"{p_item.name_fr} ({p_item.base_unit})",
            float(p_item.stock_qty),
        ])

    sales_rows: list[list[str | int | float]] = [
        [
            "Date / التاريخ",
            "N° Reçu / رقم الإيصال",
            "Statut / الحالة",
            "Paiement / الدفع",
            "Articles / الأصناف",
            "Montant / المبلغ",
        ]
    ]
    for inv in invs:
        items_desc = ", ".join(f"{ln.label} x{ln.base_qty}" for ln in inv.lines)
        sales_rows.append([
            inv.created_at.astimezone(local_tz()).strftime("%Y-%m-%d %H:%M"),
            inv.receipt_no,
            inv.status,
            inv.payment_method,
            items_desc,
            float(inv.total),
        ])

    sales_rows.append(["", "", "", "", "", ""])
    sales_rows.append(["CRÉDITS CLIENTS OUVERTS / ديون العملاء", "Téléphone / الهاتف", "Solde restant / المتبقي", "", "", ""])
    for d_item in debts:
        if d_item.direction == "RECEIVABLE":
            cust = db.get(Customer, d_item.customer_id) if d_item.customer_id else None
            sales_rows.append([
                cust.name if cust else f"Client #{d_item.customer_id}",
                cust.phone if cust and cust.phone else "",
                float(d_item.balance),
                "",
                "",
                "",
            ])

    xlsx_bytes = _build_xlsx([
        ("Resume & Caisse", summary_rows),
        ("Ventes & Credits", sales_rows),
    ])
    filename = (
        f"Rapport_{d_from.isoformat()}.xlsx"
        if d_from == d_to
        else f"Rapport_{d_from.isoformat()}_au_{d_to.isoformat()}.xlsx"
    )
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
