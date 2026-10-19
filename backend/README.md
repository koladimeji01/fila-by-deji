# FÌLÀ by Deji — FastAPI backend (foundation)

This backend is **in development** and must not yet be used to accept live payments or fulfill orders.

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
