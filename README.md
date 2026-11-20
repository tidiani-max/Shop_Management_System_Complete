# Shop Management System offline desktop app

One laptop, 100 % offline. **Electron** window → bundled **FastAPI + SQLite (WAL)** server on `127.0.0.1` → your existing **React 19 + Vite + Tailwind 4** UI (French LTR / Arabic RTL unchanged).

```
frontend/   React UI (wired to /api/v1)          backend/   FastAPI, SQLAlchemy 2, Alembic, tests
electron/   main.js + preload.js                 scripts/   build-backend.js (PyInstaller)
qa/         QA_REPORT.md (real test output)      PROJECT_PROGRESS.md
```

## Where the shop data lives
The SQLite database (`shop.db`) is stored in the OS user-data folder, **never inside the app**, so updating / reinstalling never wipes records:
Windows `%APPDATA%\Shop Management\` · macOS `~/Library/Application Support/Shop Management/` (also holds `server.log`, `backups/`).
Uninstalling does not delete it (`deleteAppDataOnUninstall: false`).

## Roles (enforced by the backend, never only by the UI)
| Role | Can do |
|---|---|
| `DDS_ADMIN` | Platform support: overview, user password reset, audit log, backup. **No access to sales/finance/products.** |
| `OWNER` | Everything for the shop: products/prices, workers, finance, debts, reports, backup/restore. |
| `WORKER` | POS, Vente Directe, own sales history, customer selection, receiving arriving stock (if permitted), credit sales (if permitted). **No** reports, workers, finance, price/cost edits, invoice deletion. |

Fast user switching on the shared laptop: sidebar → *Changer d’utilisateur* (back to login with one-tap user chips; optional 4–8 digit PIN per user).

### The Owner Admin Password (the mandatory security rule)
Set at first-run setup, **different from the login password**, stored as an Argon2id hash. Required server-side for:
* **voiding / cancelling an invoice** (also needs a written reason → stock and cash reversed automatically → immutable audit entry),
* **overriding a catalog price at sale time**,
* **changing a product price / cost / units** (workers are refused outright, `403 WORKER_FORBIDDEN`),
* **restoring a backup**.
Completed invoices can never be edited or deleted: the API refuses (`403` for workers, `409 INVOICE_IMMUTABLE` for everyone) **and** SQLite triggers reject any direct `UPDATE`/`DELETE`. The audit log, ledger and stock movements are append-only too (hash-chained audit log, verifiable). 5 wrong admin passwords → 5 min lock.

## Multi-unit inventory ("Unité / Carton / Boîte / Paquet / Pièce / Litre / Kg / custom")
Each product has a **base unit** (what is sold on the shelf) and extra units with a factor, e.g. base *Paquet*, `Carton=12`. Receiving 5 Cartons → +60 Paquets; selling 2 Paquets → −2. Chains work too (`Boîte=10`, `Carton=120` with base *Pièce*). All quantities/money are exact `Decimal` (stored as text) no float drift (0.1 L × 3 is exactly 0.3 L).
In the product form type the extra units as `Carton=12, Boîte=6`.

## Sell first, catalog gradually
* **Catalog sale**: tap products in the POS, pick the unit in the cart.
* **Vente Directe**: button *Vente directe* label (default **Article Divers**), quantity, unit/litre/piece, price. No product needed, no stock touched.
* Both use the same invoice engine → sequential `REC-2026-00001`, exact date/time, worker name, itemised lines, total; print on **58 mm / 80 mm thermal** or **A4**, or *Download* as PDF (Electron native print / save-PDF).

## Finance
Cash and Mobile Money (Orange / Moov / Wave) are separate ledger accounts. Credit sales create a customer debt; **repayments move cash but are never counted as revenue** (revenue = completed invoices only). Supplier debts, expenses, daily cash-register open/close with expected-vs-counted difference.

## Backup / restore (USB)
Settings → *Sauvegarder maintenant* → pick the USB folder → consistent copy `shop-backup-YYYYMMDD-HHMMSS.db` (SQLite online backup, safe while running). *Restaurer* needs the Owner Admin Password; a safety copy is made first.

## Build the installer
Prerequisites: Node 20+, Python 3.11+. **Build on the OS you target** (PyInstaller does not cross-compile): `.exe` on Windows, `.dmg` on macOS.

```bash
# 1. once
npm run setup                                   # installs frontend + electron deps
python -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt     # Windows: backend\.venv\Scripts\pip ...

# 2. Windows installer  ->  release/Shop Management Setup 1.0.0.exe
npm run dist:win
# 2. macOS installer    ->  release/Shop Management-1.0.0.dmg
npm run dist:mac
```
`dist:*` = build React → copy into backend → PyInstaller freeze (`backend/shop-server.spec`) → electron-builder. First launch creates the DB, runs Alembic migrations, and writes `DDS_ADMIN_CREDENTIALS.txt` (random platform-admin password) into the data folder note it, then delete the file (or set env `DDS_ADMIN_PASSWORD` before first launch).

## Develop
```bash
cd backend && python -m uvicorn app.main:app --port 8765 --reload     # API  (docs at /docs)
npm run dev:frontend                                                   # UI on :8443 / :5173 -> API :8765
npm run test:backend                                                   # pytest
```
`npm start` runs Electron against the Python sources (set `PYTHON=` to choose the interpreter).

## First run
Open the app → *Créer une boutique* → shop, owner, login password, **admin password**. Save the owner recovery code. Then add workers (each gets an `EMP-####` id + one-time password + recovery code) and products or just start selling with *Vente directe*.

## Known limits
* The period selector on the owner dashboard is visual only (dashboard shows *today*); Reports has real date pickers.
* Phone-SMS recovery cannot work offline: recovery uses the recovery code printed at account creation.
* Price override at the counter is supported by the API (`unit_price` + `admin_password`) but has no dedicated UI button yet.
