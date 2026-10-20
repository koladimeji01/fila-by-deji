# Stage 6 — Inventory and My Drafts (Ubuntu)

Work inside your existing project, **not a new clone**. Save a backup of the local development database before you migrate.

## 1. Update the code

Open a terminal:

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
git pull origin main
```

If Git reports local changes, stop and share the message rather than discarding them.

## 2. Backup and migrate your existing local database

```bash
cd backend
source .venv/bin/activate
cp -n fila_local.db "fila_local.backup.db"  # Only if this DB exists
python -m alembic upgrade head
python -m app.seed
python -m app.inventory show
```

This adds per-size stock rows without deleting customers, products, or drafts. Existing and newly seeded sizes start at **zero** until you set actual quantities. **Do not make up stock**; verify how many caps of each size you physically have.

## 3. Set actual physical stock

For example **only if you really have 5 Royal Agbada caps in size 39**:

```bash
python -m app.inventory set premium 39 5
python -m app.inventory show
```

Possible product IDs: `premium`, `classic`, `ceremonial`. Sizes: `32`, `35`, `39`, `41`. The set command **overwrites** that one stock count; it does not add to it. You may set a count to 0 to remove a size from the available list.

This CLI is intended for the local operator terminal only; there is **no public inventory-management endpoint**.

## 4. Run tests and start your API

```bash
python -m pytest -q
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep that terminal open. In **another** terminal:

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
python3 -m http.server 5500 --bind 127.0.0.1
```

Open `http://127.0.0.1:5500/`. Sign in, browse a cap, choose an in-stock size, save a draft, and open **My drafts** in the top bar (or `http://127.0.0.1:5500/orders.html`). Only your drafts are visible.

## What is *not* live yet

- A draft does **not** reserve stock or confirm an order; repeated drafts can request the same remaining stock.
- No customer-facing payment, shipping, fulfillment, or admin dashboard is enabled.
- This is not a production-ready shop. Before accepting orders we'll add atomic stock reservation/confirmation, payment-provider verification, shipping calculations, production admin permissions, abuse controls, backups, and deployment hardening.

If a command errors, share its output (but never share `.env`, database content, passwords, or tokens).
