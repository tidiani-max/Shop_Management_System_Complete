# PROJECT_PROGRESS

## Done
- [x] backend/: FastAPI + SQLite(WAL) + SQLAlchemy 2 + Alembic (0001 schema, 0002 immutability triggers)
- [x] Roles DDS_ADMIN / OWNER / WORKER enforced server-side; Argon2id; separate Owner Admin Password (+lockout)
- [x] Multi-unit inventory, exact Decimal; unified invoice engine (Catalog + Direct), REC-YYYY-00001
- [x] Void with reason + admin password + stock/cash reversal + hash-chained audit log; invoices immutable (API + DB triggers)
- [x] Finance: Cash/Mobile ledger, debts, expenses, register open/close, USB backup/restore
- [x] Frontend wired to /api/v1 (login/quick-switch/PIN, setup, recovery, dashboard, POS, Vente Directe, receipts+print, stock/receive, money, debts, reports, alerts, team, settings, DDS admin); fonts bundled locally (offline)
- [x] Electron main/preload, electron-builder, PyInstaller spec; npm run dist:win / dist:mac
- [x] QA: tsc OK, vite build OK, pytest 40 passed, frozen server smoke test, electron-builder dir build (see qa/QA_REPORT.md)

## Remaining / known limits
- [ ] Build .exe on Windows / .dmg on macOS (cannot cross-compile); first real-machine click-through + thermal printer test
- [ ] Owner dashboard period selector is visual only; no dedicated UI button for counter price override (API supports it)
