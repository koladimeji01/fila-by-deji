# FÌLÀ by Deji — FastAPI API (Stage 8)

This backend is **still under development**. Customers can sign up, authenticate, browse a seeded catalog, create draft orders, view their order history and temporarily hold available stock. Admin-only APIs can manage *available* inventory. **There is no payment, delivery or order confirmation API.**

## Local Ubuntu setup

From the `backend` directory with Python 3.11+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp -n .env.example .env
# Replace the JWT_SECRET_KEY placeholder with a unique, randomly generated secret.
python -m alembic upgrade head
python -m app.seed
python -m app.doctor
pytest -q
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` and `/api/v1/products`. Run the frontend on port 5500 separately. Never commit `.env`, a database backup, or real passwords. For a step-by-step migration, see [`../STAGE8_UBUNTU.md`](../STAGE8_UBUNTU.md).

## API overview

- Public: `GET /api/v1/health`, `GET /api/v1/products`, `GET /api/v1/products/{id}`, `POST /api/v1/auth/register`, `POST /api/v1/auth/login`.
- Authenticated: `GET /api/v1/auth/me`, `POST /api/v1/orders/drafts`, `GET /api/v1/orders`, `GET /api/v1/orders/{id}`, `POST /api/v1/orders/{id}/reserve`, `POST /api/v1/orders/{id}/cancel`.
- Admin only: `GET /api/v1/admin/inventory`, `PUT /api/v1/admin/inventory/{id}/{size}`, `GET /api/v1/admin/orders`, `POST /api/v1/admin/reservations/release-expired`.

A **draft** does not reserve stock. A **reservation** reduces available per-size inventory for 15 minutes; cancellation and expiry restore stock once, with transactional conditional writes. Order totals are recalculated by the server. The app never accepts client-supplied prices or payment status. The original seeded prices and sizes are placeholders pending merchant verification.

## Stage 8 security and operations

- `python -m app.doctor` checks DB connectivity, Alembic revision (`0003_holds`), required tables/columns, plus Redis connectivity in production. It is **read-only** and refuses mismatched schemas.
- The API rate-limits sensitive POST/PUT routes by source IP, returning `429` and a `Retry-After` header. Local development uses an in-process counter; **production requires shared Redis**, either via a TLS `rediss://` URL or Render's **private-network** `redis://red-...:6379` URL with `RATE_LIMIT_ALLOW_RENDER_PRIVATE_REDIS=true` explicitly enabled. The private option must only be used when Render's API and Key Value share a workspace and region. If Redis fails, protected endpoints fail closed with `503`.
- CORS is restricted to configured origins, including the new rate-limit responses. Auth/order/admin APIs use `Cache-Control: no-store`; headers also include `nosniff`, `DENY` frames, and `no-referrer`.
- `scripts/sweep-expired.sh` can be run by Ubuntu cron every minute; a production deployment must provide an **independent** hosted scheduler and monitoring. Expiration also occurs lazily during relevant API requests.
- `APP_ENV=production` requires PostgreSQL with psycopg, HTTPS frontend CORS origins, a 32+-character JWT secret and shared TLS Redis. Production API documentation is off.

## Production limitations

This is a **pre-deployment hardening increment**, not production-readiness certification. Rate limiting is per reported connection IP: ensure proxy headers are trusted only from an authorized reverse proxy, and add email/account-specific defenses to reduce shared-IP collateral damage. Additional work includes secure hosting and backups, concurrency tests on PostgreSQL, admin MFA, email confirmation/password recovery, logs/auditing, privacy/data retention, validated shipping, and signed payment webhooks/idempotency. Payments and fulfillment remain disabled.

## Stage 9 — Deployment preparations

A non-root `Dockerfile`, secret-excluding `.dockerignore`, protected production entrypoint (`scripts/start-api.sh`), and CI workflow are now included. Production configuration refuses database URLs without PostgreSQL TLS, public Redis URLs without TLS, wildcard CORS and malformed/non-HTTPS frontend origins. No production services have been provisioned. Read [Stage 9 Ubuntu guide](../STAGE9_UBUNTU.md) before deploying. Do not use the Dockerfile to accept real payments until the launch blockers are addressed.
