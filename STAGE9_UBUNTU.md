# Stage 9 — Prepare FÌLÀ by Deji for hosting (Ubuntu)

**Status:** deployment configuration and CI are prepared. No managed PostgreSQL/Redis instance or live website has been created by this change. Do not accept real money yet.

## What this stage adds

- `backend/Dockerfile` — API container using Python 3.13 and a non-root Linux account.
- `backend/.dockerignore` — keeps `.env`, local databases, tests, and virtual environments out of the image.
- `backend/scripts/start-api.sh` — refuses to run without `APP_ENV=production`; checks schema and Redis readiness before serving requests. It does **not** silently run migrations.
- `.github/workflows/backend-ci.yml` — automated Python tests and JavaScript syntax checks on GitHub.
- `backend/.env.production.example` — **public placeholder template only**, not credentials.
- Stronger production environment validation: PostgreSQL TLS (`sslmode=require` or stronger), encrypted Redis, and a precise HTTPS CORS origin.

## Step 1 — Update on Ubuntu

Stop FastAPI using `Ctrl + C`, then:

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
git status --short
git pull origin main
cd backend
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m alembic current
python -m app.doctor
pytest -q
```

Do **not** delete `fila_local.db` or replace your existing `.env`. No new Alembic migration was added in Stage 9. Your Ubuntu development setup still uses SQLite and does not require Redis.

Expected local automated result at time of writing: **65 passed**. The `backend-ci.yml` workflow will run after GitHub receives this update; check the Actions tab for its *actual* status.

## Step 2 — Optional: build the API container on Ubuntu

Only if Docker is already installed:

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
docker build -f backend/Dockerfile -t fila-by-deji-api:stage9 backend
```

Building an image does **not** start a production database or deploy the website. The production container intentionally refuses to start without real hosted services and private configuration.

## Step 3 — Choose and create hosting services

To host the site, you will need:

1. **Managed PostgreSQL** database (for example, Supabase PostgreSQL or Render PostgreSQL); allow TLS connections.
2. **Managed Redis with TLS** (`rediss://`) for shared API rate limits. Redis is not the product database.
3. **Backend web service** (for example Render) using `backend/Dockerfile`; if your platform asks for a root directory, use `backend`. Set the health route to `/api/v1/health`.
4. **HTTPS static website hosting** (e.g. Vercel or Netlify) for the existing HTML/CSS/JS site; configure the frontend's API base URL with the final HTTPS backend domain.
5. **Independent scheduled job** to release expired reservations at least once per minute. The service can run `python -m app.expire` with a connection to the *same* production PostgreSQL database. Do not rely on your laptop's cron for hosted orders.

Hosting may require a paid plan, particularly managed databases, Redis, background jobs and backups. Check provider pricing before creating resources. Never give a provider more permissions than it needs.

## Step 4 — Configure production secrets privately

Use your hosting service's environment/secret controls, **not GitHub source files**. All values below are examples; never reuse placeholder values:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://DB_USER:URL_ENCODED_PASSWORD@DB_HOST:5432/DB_NAME?sslmode=require
RATE_LIMIT_REDIS_URL=rediss://REDIS_USER:URL_ENCODED_PASSWORD@REDIS_HOST:6380/0
JWT_SECRET_KEY=GENERATE_A_UNIQUE_RANDOM_SECRET_PRIVATELY
CORS_ORIGINS=https://YOUR-EXACT-WEBSITE-DOMAIN.example
ACCESS_TOKEN_MINUTES=30
```

Generate a separate production JWT secret locally with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`, then paste it **privately** into the host's secret field. Never paste the value into ChatGPT or GitHub. PostgreSQL passwords with `@`, `/`, `#` or `:` must be URL-encoded in `DATABASE_URL`. Follow the provider's TLS/CA guidance; when possible prefer `sslmode=verify-full` with verified certificates rather than `sslmode=require`.

## Step 5 — Initialize a new, empty production database

Before starting the API, run these commands **once**, inside a trusted job/container with the real production environment loaded:

```bash
python -m alembic upgrade head
python -m app.seed
python -m app.doctor
```

Do not place `alembic upgrade head` in a startup command that runs on every API replica. `app.seed` creates the three *sample* Figma products with **zero** available inventory; confirm real stock and prices before launch. You must explicitly decide whether any SQLite test data should migrate; **it is not transferred automatically**.

## Step 6 — Host and verify without accepting payments

- Confirm `/api/v1/health` and `/api/v1/products` over HTTPS.
- Configure `CORS_ORIGINS` to the actual storefront HTTPS origin (no trailing path).
- Configure the frontend's API base URL: add an early configuration script before `js/app.js` to set `window.FILA_API_BASE_URL = 'https://YOUR-BACKEND-URL/api/v1'`, or use an approved equivalent. Never leave localhost in the deployed frontend.
- Verify login, wrong-password rate limits, private order history, stock holds and their expiry, admin access denial for customers, and mobile layout.
- Do **not** mark orders paid or collect money. Shipping, policies, confirmation, payment verification, email recovery/verification, admin MFA, and provider webhook checks remain future stages.

### Known blockers before a real customer launch

Production behind a reverse proxy needs correct, *verified* client-IP handling for abuse limits. The startup command currently refuses to blindly trust `X-Forwarded-For`; if all requests arrive from the proxy's IP, many customers can share one limit. Configure trusted proxy handling and test it before opening public registration. The inventory reservation concurrency logic must also be exercised on real PostgreSQL, and PostgreSQL backups must be restored in a staging test.
