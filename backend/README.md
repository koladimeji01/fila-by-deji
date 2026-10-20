# FÌLÀ by Deji — FastAPI backend

**Development API, not a live payment processor.**

## Implemented

- Customer registration/login and private profile (Argon2 password hashing, JWT).
- API-backed product catalog with per-size availability, current prices read from the database.
- Server-validated drafts and 15-minute stock holds. A **draft** does not decrement stock; a **reservation** temporarily decrements available stock and is released on expiry/cancellation.
- Customer-only order history and operator-only stock/order endpoints.
- Migrations `0001_initial`, `0002_inventory`, `0003_holds`; the API now checks schema readiness at startup (except isolated tests).
- Rate limits: development memory counters, Redis TLS required in production; restricted CORS and no-store headers on sensitive endpoints and product availability.
- Expiry cleanup CLI: `python -m app.expire` and `scripts/sweep-expired.sh`.

## API endpoints

| Method | Route | Access |
| --- | --- | --- |
| GET | `/api/v1/health` | Public |
| GET | `/api/v1/products`, `/api/v1/products/{id}` | Public |
| POST | `/api/v1/auth/register`, `/api/v1/auth/login` | Public, rate-limited |
| GET | `/api/v1/auth/me` | Authenticated |
| POST | `/api/v1/orders/drafts` | Authenticated |
| GET | `/api/v1/orders`, `/api/v1/orders/{id}` | Owner |
| POST | `/api/v1/orders/{id}/reserve`, `/api/v1/orders/{id}/cancel` | Owner |
| GET | `/api/v1/admin/inventory`, `/api/v1/admin/orders` | Administrator |
| PUT | `/api/v1/admin/inventory/{product_id}/{size}` | Administrator |
| POST | `/api/v1/admin/reservations/release-expired` | Administrator |

Customers cannot set order prices, invent payment status or grant themselves administrator access. Only a trusted operator should run `python -m app.admin grant --email ...` locally.

## Ubuntu setup

From the repository's `backend/` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp -n .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Replace the `JWT_SECRET_KEY` placeholder inside `.env` with the generated secret. Do not publish secrets. Then:

```bash
python -m alembic upgrade head
python -m app.seed
python -m app.doctor
pytest -q
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Local development uses SQLite only. For production, set the privately provisioned PostgreSQL URL, `APP_ENV=production`, `RATE_LIMIT_REDIS_URL=rediss://...`, a long unique JWT secret and the exact HTTPS storefront origin as `CORS_ORIGINS`.

## Still required before sales/deployment

Test real PostgreSQL concurrency and recovery; configure independent DB backups and reservation-expiry scheduler; add email verification and password resets, admin MFA, durable audit logging and anti-abuse monitoring; implement shipping, refunds and policy requirements; and integrate provider-verified payments with signed webhooks and idempotent reconciliation.

**There is intentionally no paid/confirmed/shipped order transition.** See [Stage 8 Ubuntu instructions](../STAGE8_UBUNTU.md) and [audit report](../AUDIT_REPORT_2026-10-20.md).
