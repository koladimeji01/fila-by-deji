# Stage 7 — Temporary stock holds and admin-only inventory (Ubuntu)

This stage does **not** accept money or confirm orders. A *reservation* is a temporary
15-minute hold, not a sale. A *draft* reserves nothing. You need verified physical
stock values before demonstrating reservations. The Figma website is unchanged
except for safe controls on **My orders**.

## 1. Update your existing project

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
git pull origin main
cd backend
source .venv/bin/activate
```

Stop if Git reports uncommitted changes or merge conflicts; do **not** run reset/clean.

## 2. Backup and migrate

Stop the running API first with **Ctrl+C** in its terminal. Only migrate a database
when the server is stopped. For local SQLite:

```bash
cp -n fila_local.db fila_local.stage6.backup.db
python -m alembic upgrade head
python -m app.seed
python -m app.inventory show
pytest -q
```

This adds `users.is_admin` default false and `orders.reserved_until`. The schema
upgrade **does not** reset customers, existing drafts, or stock levels.

## 3. Create an operator account (only if you want the admin API)

Register a separate account through your local frontend or Swagger docs. Use a
long unique password. From the backend directory, grant it operator rights
**locally**, replacing the email with the one you registered:

```bash
python -m app.admin grant --email your-operator@example.com
```

There is **no registration parameter** that creates admin users. Never run this
against production unless you control the database and the destination account.
To revoke later:

```bash
python -m app.admin revoke --email your-operator@example.com
```

## 4. Set physically verified AVAILABLE stock

```bash
python -m app.inventory show
python -m app.inventory set premium 39 5
```

`set` changes the **currently available** units, not total owned. For instance,
if two units are held and there are seven physical units, set *available* to five.
Never invent stock counts just to publish your store.

## 5. Start both local servers

Terminal one (backend directory with venv active):

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal two (repository root):

```bash
python3 -m http.server 5500 --bind 127.0.0.1
```

Open http://127.0.0.1:5500/orders.html, sign in, create a draft via Checkout,
then select **Hold stock for 15 minutes** on My orders. You may hold at most one
selection at a time; cancelling releases held stock. On expiry, held stock is
returned by the next relevant API request or an operator cleanup run.

For admin API testing, open http://127.0.0.1:8000/docs and authorize using your
operator account token:

- `GET /api/v1/admin/inventory`: see currently AVAILABLE quantities
- `PUT /api/v1/admin/inventory/premium/39` with `{ "available_quantity": 5 }`
- `GET /api/v1/admin/orders`: view customer order states (operator only)
- `POST /api/v1/admin/reservations/release-expired`: cleanup expired holds

Local operator sweep from backend folder:

```bash
python -m app.expire
```

## Before real money or deployment

- Use PostgreSQL and test concurrent reservations against it (SQLite is local only).
- Run expiry cleanup at least hourly (15-minute TTL will not be punctual without
  a dedicated scheduler). Reduce sweep interval before going live.
- Add API throttling, abuse prevention, admin account MFA, operational audit logs,
  price/stock reconciliation, inventory adjustments, email verification, shipping,
  and payment-provider verified webhooks with idempotency.
- **No route** can mark a draft or reservation as `paid`, `confirmed`, or shipped.
- No card details, delivery address, or payment secrets are collected yet.
