# QA REPORT

Generated on the build machine (Linux, Node 22, Python 3.12). All outputs below are the real command outputs.

## Summary
| Check | Result |
|---|---|
| `npx tsc --noEmit` (frontend) | PASS, exit 0 |
| `npm run build` (frontend) | PASS, exit 0 |
| `pytest` (backend) | PASS, **40 passed** |
| Frozen backend (PyInstaller) started like Electron does, `/api/v1/health`, SPA, migrations, `/setup` | PASS |
| `electron-builder --linux dir` with the frozen backend as `extraResources` | PASS (`resources/app.asar` + `resources/backend`) |

## Requirements covered by tests
* **Multi-unit conversions**: 5 Cartons of 12 Paquets -> +60, sell 2 -> 58; Carton -> Boîte -> Pièce chain (2 Cartons = 240 Pièces, -3 Boîtes, -5 Pièces); Litre with fractions exact (0.1 x 3, 0.25); Kg / custom unit; unknown unit rejected; insufficient stock rejected with no side effects. (`tests/test_units.py`)
* **Sequential receipt numbering across Direct and Catalog sales** (`REC-<year>-00001..00005`), idempotent retries, gapless after void, 58/80/A4 printable HTML. (`tests/test_receipts.py`)
* **Strict backend blocks**: worker cannot edit price/cost (incl. with admin password), cannot create/delete products, cannot delete/edit/patch invoices (403), owner cannot either (409), SQLite triggers reject direct UPDATE/DELETE on invoices, lines, ledger, audit log; void needs admin password + reason, reverses stock and cash, writes audit; price override needs admin password; admin-password and login lockouts; role boundaries; DDS_ADMIN has no sales/finance access; Argon2id hashes. (`tests/test_security.py`)
* **Finance**: Cash/Mobile separate; credit sale + repayment not double counted as revenue; void of credit sale refunds repayments and cancels debt; supplier payables; weighted-average cost/profit; register open/close difference; backup export + restore round-trip, bad backup rejected, download. (`tests/test_finance.py`)

## Not verified here (needs a real machine)
* Launching the Electron GUI window (no display in the build sandbox) and native print dialogs / physical 58 mm thermal output.
* Building the actual `.exe` (needs Windows) and `.dmg` (needs macOS); the Linux `dir` target above validates the same configuration.
* A visual click-through of every screen in a browser: the frontend was type-checked and built, and the API it calls is covered by the tests, but screens were not exercised in a real browser.

## `npx tsc --noEmit`
```
$ npx tsc --noEmit
exit code: 0
```

## `npm run build`
```
$ npm run build

> figma-make-app@1.0.0 build
> vite build

(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:32:27). Use `import.meta.dirname` instead
  - JSON import "./.figma/make/site.json" without import attributes (vite.config.ts:7:31). Add `with { type: 'json' }`
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.
vite v8.3.8 building client environment for production...
transforming...
✓ 2095 modules transformed.
rendering chunks...
computing gzip size...
dist/robots.txt                                                     0.02 kB │ gzip:   0.04 kB
dist/index.html                                                     1.04 kB │ gzip:   0.46 kB
dist/assets/noto-sans-arabic-symbols-400-normal-BbP0vlM-.woff2      4.71 kB
dist/assets/noto-sans-arabic-symbols-700-normal-D40a2DlB.woff2      4.74 kB
dist/assets/noto-sans-arabic-symbols-500-normal-DHLLsnZT.woff2      4.75 kB
dist/assets/noto-sans-arabic-symbols-600-normal-BLWpRi3R.woff2      4.76 kB
dist/assets/noto-sans-arabic-symbols-700-normal-Ct3Gyvbr.woff       6.12 kB
dist/assets/noto-sans-arabic-symbols-600-normal-Ch3HzCxt.woff       6.18 kB
dist/assets/noto-sans-arabic-symbols-400-normal-BJzmBRSy.woff       6.18 kB
dist/assets/noto-sans-arabic-symbols-500-normal-BxLqRJGm.woff       6.18 kB
dist/assets/noto-sans-arabic-latin-ext-400-normal-CW3XQ4Yj.woff2    6.52 kB
dist/assets/noto-sans-arabic-latin-ext-700-normal-wF0ZdkCd.woff2    6.52 kB
dist/assets/noto-sans-arabic-latin-ext-500-normal-CpD3jfIL.woff2    6.53 kB
dist/assets/noto-sans-arabic-latin-ext-600-normal-6_GPoF44.woff2    6.62 kB
dist/assets/dm-sans-latin-ext-400-normal-BtiwyxMk.woff2             7.36 kB
dist/assets/dm-sans-latin-ext-600-normal-4vooXBpG.woff2             7.42 kB
dist/assets/dm-sans-latin-ext-500-normal-BJfUCQsA.woff2             7.43 kB
dist/assets/dm-sans-latin-ext-700-normal-CJIcxD6K.woff2             7.45 kB
dist/assets/noto-sans-arabic-math-700-normal-DhwRdyuq.woff2         7.75 kB
dist/assets/noto-sans-arabic-math-400-normal-BxrVu-ji.woff2         7.76 kB
dist/assets/noto-sans-arabic-math-600-normal-C2PaYQVA.woff2         7.78 kB
dist/assets/noto-sans-arabic-math-500-normal-CPBZimiT.woff2         7.82 kB
dist/assets/noto-sans-arabic-latin-ext-700-normal-DX5dIs2j.woff     8.41 kB
dist/assets/noto-sans-arabic-latin-ext-400-normal-D4Wl3hq7.woff     8.43 kB
dist/assets/noto-sans-arabic-latin-ext-500-normal-BAH5x22p.woff     8.48 kB
dist/assets/noto-sans-arabic-latin-ext-600-normal-Be-B9uOG.woff     8.49 kB
dist/assets/noto-sans-arabic-math-700-normal-C3IT52xG.woff          9.82 kB
dist/assets/noto-sans-arabic-math-400-normal-BiWGKoY7.woff          9.93 kB
dist/assets/noto-sans-arabic-math-600-normal-BQnKH7M_.woff          9.93 kB
dist/assets/noto-sans-arabic-math-500-normal-D2rXSvcI.woff          9.95 kB
dist/assets/dm-sans-latin-ext-400-normal-BjWJ59Pq.woff              9.97 kB
dist/assets/dm-sans-latin-ext-700-normal-BLI3TTWz.woff             10.01 kB
dist/assets/dm-sans-latin-ext-600-normal-DRtaDpgU.woff             10.02 kB
dist/assets/dm-sans-latin-ext-500-normal-DR84L5F-.woff             10.06 kB
dist/assets/noto-sans-arabic-latin-700-normal-D41hNJFR.woff2       10.62 kB
dist/assets/noto-sans-arabic-latin-600-normal-BUFr-ZM9.woff2       10.74 kB
dist/assets/noto-sans-arabic-latin-400-normal-CjsIS08k.woff2       10.74 kB
dist/assets/noto-sans-arabic-latin-500-normal-8boVNgww.woff2       10.79 kB
dist/assets/noto-sans-arabic-latin-700-normal-DST6Nu2E.woff        13.42 kB
dist/assets/noto-sans-arabic-latin-400-normal-lr8cikIT.woff        13.62 kB
dist/assets/noto-sans-arabic-latin-600-normal-D8ZQ8Cfs.woff        13.62 kB
dist/assets/noto-sans-arabic-latin-500-normal-GCsE6TXV.woff        13.67 kB
dist/assets/dm-sans-latin-600-normal-Aqo67rzb.woff2                14.14 kB
dist/assets/dm-sans-latin-400-normal-CW0RaeGs.woff2                14.20 kB
dist/assets/dm-sans-latin-500-normal-B9HHJjqV.woff2                14.30 kB
dist/assets/dm-sans-latin-700-normal-DvUfVpUG.woff2                14.34 kB
dist/assets/dm-sans-latin-600-normal-BmdmIIQ2.woff                 18.32 kB
dist/assets/dm-sans-latin-400-normal-BwCSEQnW.woff                 18.35 kB
dist/assets/dm-sans-latin-700-normal-CUSSCpQX.woff                 18.50 kB
dist/assets/dm-sans-latin-500-normal-Dr3UlScf.woff                 18.52 kB
dist/assets/noto-sans-arabic-arabic-400-normal-AAMxebZb.woff2      48.84 kB
dist/assets/noto-sans-arabic-arabic-700-normal-3CqrwsiZ.woff2      50.22 kB
dist/assets/noto-sans-arabic-arabic-500-normal-DPISWLls.woff2      53.12 kB
dist/assets/noto-sans-arabic-arabic-600-normal-JPxwL-XU.woff2      53.26 kB
dist/assets/noto-sans-arabic-arabic-400-normal-hsqIUL9Q.woff       79.08 kB
dist/assets/noto-sans-arabic-arabic-700-normal-DXnsSW3z.woff       81.06 kB
dist/assets/noto-sans-arabic-arabic-500-normal-CoaTbVwZ.woff       84.28 kB
dist/assets/noto-sans-arabic-arabic-600-normal-JLzruTOp.woff       84.98 kB
dist/assets/index-BbG1Vf9T.css                                     81.39 kB │ gzip:  15.72 kB
dist/assets/index-Cl1BJrHy.js                                     335.07 kB │ gzip: 100.71 kB

✓ built in 986ms
exit code: 0
```

## `pytest -v`
```
$ python -m pytest -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0 -- /home/claude/venv/bin/python
cachedir: .pytest_cache
rootdir: /home/claude/proj/backend
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 40 items

tests/test_finance.py::test_cash_and_mobile_money_tracked_separately PASSED [  2%]
tests/test_finance.py::test_credit_sale_and_repayment_are_not_double_counted_as_revenue PASSED [  5%]
tests/test_finance.py::test_credit_sale_requires_customer PASSED         [  7%]
tests/test_finance.py::test_voiding_credit_sale_cancels_debt_and_refunds_repayments PASSED [ 10%]
tests/test_finance.py::test_manual_debt_and_supplier_payable PASSED      [ 12%]
tests/test_finance.py::test_weighted_average_cost_and_profit PASSED      [ 15%]
tests/test_finance.py::test_daily_register_open_close_reconciliation PASSED [ 17%]
tests/test_finance.py::test_backup_export_and_restore_roundtrip PASSED   [ 20%]
tests/test_finance.py::test_restore_rejects_non_backup_file PASSED       [ 22%]
tests/test_finance.py::test_backup_download_and_worker_blocked PASSED    [ 25%]
tests/test_receipts.py::test_sequential_numbers_across_direct_and_catalog PASSED [ 27%]
tests/test_receipts.py::test_direct_sale_needs_no_product_and_touches_no_stock PASSED [ 30%]
tests/test_receipts.py::test_direct_sale_requires_price PASSED           [ 32%]
tests/test_receipts.py::test_mixed_invoice_and_receipt_fields PASSED     [ 35%]
tests/test_receipts.py::test_idempotent_client_ref_no_duplicate PASSED   [ 37%]
tests/test_receipts.py::test_void_keeps_numbering_gapless_forward PASSED [ 40%]
tests/test_receipts.py::test_printable_receipt_sizes PASSED              [ 42%]
tests/test_security.py::test_worker_cannot_modify_product_price_or_cost PASSED [ 45%]
tests/test_security.py::test_worker_cannot_create_or_delete_products PASSED [ 47%]
tests/test_security.py::test_owner_price_change_needs_admin_password PASSED [ 50%]
tests/test_security.py::test_worker_cannot_set_cost_through_stock_receive PASSED [ 52%]
tests/test_security.py::test_worker_cannot_delete_or_edit_invoices PASSED [ 55%]
tests/test_security.py::test_even_owner_cannot_delete_invoice PASSED     [ 57%]
tests/test_security.py::test_database_triggers_block_direct_tampering PASSED [ 60%]
tests/test_security.py::test_void_flow_requires_admin_password_reason_and_reverses_everything PASSED [ 62%]
tests/test_security.py::test_price_override_needs_admin_password_and_is_audited PASSED [ 65%]
tests/test_security.py::test_admin_password_lockout_after_repeated_failures PASSED [ 67%]
tests/test_security.py::test_worker_role_boundaries PASSED               [ 70%]
tests/test_security.py::test_worker_sees_only_own_sales PASSED           [ 72%]
tests/test_security.py::test_dds_admin_has_no_access_to_sales_or_finance PASSED [ 75%]
tests/test_security.py::test_credit_sale_permission_enforced PASSED      [ 77%]
tests/test_security.py::test_passwords_hashed_with_argon2id_and_never_returned_again PASSED [ 80%]
tests/test_security.py::test_login_lockout_and_recovery PASSED           [ 82%]
tests/test_security.py::test_audit_chain_is_verifiable PASSED            [ 85%]
tests/test_units.py::test_receive_5_cartons_of_12_packs_then_sell_2_packs PASSED [ 87%]
tests/test_units.py::test_carton_to_boite_to_piece_chain PASSED          [ 90%]
tests/test_units.py::test_litre_with_fractions_is_exact PASSED           [ 92%]
tests/test_units.py::test_kg_custom_unit_and_unknown_unit_rejected PASSED [ 95%]
tests/test_units.py::test_insufficient_stock_blocks_and_changes_nothing PASSED [ 97%]
tests/test_units.py::test_invalid_factor_and_too_precise_quantity PASSED [100%]

============================= 40 passed in 44.57s ==============================
```

## Frozen backend smoke test
```
shop-server --port 8788 (SHOP_DATA_DIR=/tmp/frozen_data)
GET /api/v1/health   -> {"status":"ok","version":"1.0.0"}
GET /                -> 200 (React app served)
GET /api/v1/setup/status -> {"initialized":false,...}
POST /api/v1/setup   -> token + OWNER user (Argon2id, migrations applied)
data dir: DDS_ADMIN_CREDENTIALS.txt shop.db shop.db-shm shop.db-wal
```
