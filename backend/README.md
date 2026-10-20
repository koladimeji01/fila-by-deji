# FÌLÀ by Deji — FastAPI backend (Stage 7)

This backend is **in development** and must not yet be used to accept live payments or fulfill orders.

## Stage 7 additions

- `POST /api/v1/orders/{id}/reserve`: 15-minute temporary hold, atomic per-size
  decrement, single active hold per customer, server-side repricing.
- `POST /api/v1/orders/{id}/cancel`: cancel draft or hold and restore inventory
  exactly once. Expired holds restore stock automatically on relevant API reads
  or `python -m app.expire` cleanup.
- `GET /api/v1/admin/inventory`, `PUT /api/v1/admin/inventory/{product_id}/{size}`,
  `GET /api/v1/admin/orders`, and admin expiry cleanup require a database-backed
  `is_admin` role. `python -m app.admin grant --email ...` only via authorized
  operator terminal. Public signup does **not** grant administrative privileges.
- All legacy orders remain drafts after the additive Alembic `0003_holds` migration.
- **None of these operations accepts payments or creates confirmed sales.**

See [`../STAGE7_UBUNTU.md`](../STAGE7_UBUNTU.md) for Ubuntu instructions.

## What works

- Health check and restricted CORS
- Customer registration with Argon2 password hashing
- JWT login and authenticated profile endpoint
- Product catalog sourced from the database, seeded from Figma mockup (3 styles at ₦10,000)
- Draft orders with server-side product/price validation, requested size and quantity
- Each customer sees only their own drafts; draft lines snapshot the name and price
- Schema migrations with Alembic, SQLite for local development, PostgreSQL for production
- Automated authentication, authorization, pricing, and validation tests

A draft order is **not an accepted or paid order**, doesn't reserve stock, and cannot be submitted for payment with this API. There is intentionally no payment endpoint, inventory decrement, or order fulfillment workflow yet.

## Windows PowerShell setup

From the repository root:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated secret into `JWT_SECRET_KEY` in `.env`. Do **not** commit `.env` to GitHub.

```powershell
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Try `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/api/v1/products`.

## API reference

| Method | Route | Authentication |
| --- | --- | --- |
| GET | `/api/v1/health` | public |
| POST | `/api/v1/auth/register` | public |
| POST | `/api/v1/auth/login` | public |
| GET | `/api/v1/auth/me` | bearer token |
| GET | `/api/v1/products` | public |
| GET | `/api/v1/products/{product_id}` | public |
| POST | `/api/v1/orders/drafts` | bearer token |
| GET | `/api/v1/orders` | bearer token |
| GET | `/api/v1/orders/{order_id}` | bearer token |

Register body: `{"name":"Ada Example","email":"ada@example.com","password":"a-long-unique-password"}`.

Login body: `{"email":"ada@example.com","password":"a-long-unique-password"}`.

Draft order body (size required): `{"items":[{"product_id":"premium","size":"39","quantity":2}]}`.

The API **ignores all browser prices**. Prices are looked up in PostgreSQL/SQLite and stored as integer kobo. The response returns integer `*_ngn` amounts. Customer-provided totals, customer IDs, and order states are rejected. Only the server calculates totals.

## Automated tests

```powershell
pytest -q
```

Tests use an isolated temporary SQLite database, never production data.

## Before a public launch

- Deploy PostgreSQL, set `APP_ENV=production`, production `DATABASE_URL` and a long random `JWT_SECRET_KEY` in host secrets (never GitHub)
- Set `CORS_ORIGINS` to the exact **HTTPS** frontend domain
- Implement rate limiting, lockout/anti-abuse protections, password reset and email verification
- Build stock-by-size and shipping/tax calculation, customer address data policy and retention
- Select a payment provider (e.g. Paystack), implement server-side payment initialization, signed webhooks, reconciliation and idempotency before orders can be paid
- Implement admin access controls, order fulfillment, cancellation/refund policy, logs and backups
- Connect frontend `js/app.js` to `/api/v1` and introduce login/register flows

Currently only the database and API foundations are implemented. No third-party payment credentials are needed yet.

## Stage 6: Inventory and order history (Ubuntu)

With your existing `.venv` activated, run `python -m alembic upgrade head` **before restarting the API**. This creates `product_inventory`, preserving existing draft orders and user records. Every product/size begins with zero available stock, deliberately; enter real counts using `python -m app.inventory set premium 39 5` (substitute the verified actual count), then `python -m app.inventory show`. Seeding with `python -m app.seed` creates any missing rows but **never resets counts**.

Product responses now advertise only `available_sizes` with a positive count; creating a new draft validates the quantity and size against available stock and returns HTTP `409` for unavailable selections. Drafts **do not** reserve stock and may be duplicated. The order history route accepts `GET /api/v1/orders?limit=20&offset=0`, requires a bearer token, and returns only the authenticated customer's drafts. Auth and order responses include `Cache-Control: no-store`. Stock management is an operator-only local CLI, not a publicly exposed API.

In the frontend, signed-in customers can visit `orders.html`. No real payment, delivery, shipment, or fulfillment is performed. Full operator instructions are in the repository root `STAGE6_UBUNTU.md`.
