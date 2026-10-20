# Stage 8 — Database readiness, basic abuse protection, and reservation cleanup (Ubuntu)

**This is production preparation, not permission to start accepting payments.** The site still has no payment-verification, shipping, fulfilment, customer email verification, or admin MFA. Never put real database credentials in GitHub.

## 1. Update without losing your local database

Stop FastAPI using **Ctrl+C**. Open a new terminal:

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
git status --short
git pull origin main
cd backend
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

If Git refuses to pull due to local changes, stop; do not run `git reset --hard` or `git clean`. The `backend/.env` and `backend/fila_local.db` files should remain local and untracked.

## 2. Check migrations before starting the API

While FastAPI is **stopped**, back up your existing SQLite database and migrate:

```bash
cp "fila_local.db" "fila_local.backup.$(date +%Y%m%d-%H%M%S).db"
python -m alembic upgrade head
python -m app.doctor
pytest -q
```

`python -m app.doctor` must say `READY: ...`. It detects missing columns such as `orders.reserved_until`, incorrect Alembic version and an unavailable database. The Stage 8 security change itself **does not add a new schema migration**; the current schema is still `0003_holds`.

## 3. Start locally (no Redis or PostgreSQL installation necessary)

Use the same local `.env` you already have (`APP_ENV=development`, `DATABASE_URL=sqlite:///./fila_local.db`). The new `RATE_LIMIT_REDIS_URL` may be blank in **development only**.

Terminal one:

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji/backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal two:

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
python3 -m http.server 5500 --bind 127.0.0.1
```

Open http://127.0.0.1:5500 and http://127.0.0.1:8000/api/v1/products. Registration, login, drafts, stock holds and order history should continue working. Repeated excessive login attempts return `429 Too Many Requests` with `Retry-After`; wait rather than repeatedly retrying.

## 4. Optional local reservation-expiry scheduler (Ubuntu)

Run a manual cleanup first, from the backend directory:

```bash
python -m app.expire
```

A 15-minute stock hold expires at its deadline, but **stock is returned when an expiry sweep executes**. To sweep automatically while this Ubuntu machine is on, use Ubuntu cron (one-minute frequency):

```bash
sudo apt install -y cron
sudo systemctl enable --now cron
crontab -e
```

Append this line to the crontab (replace `/home/l2e` if your Ubuntu home directory differs):

```cron
* * * * * /home/l2e/Desktop/Fila\ by\ Deji/fila-by-deji/backend/scripts/sweep-expired.sh >> /tmp/fila-expiry.log 2>&1
```

Crontab shell quoting is tricky when paths contain spaces; instead, the *recommended* robust approach is to create a simple wrapper at a path without spaces:

```bash
mkdir -p "$HOME/bin"
cat > "$HOME/bin/fila-expire" <<'SH'
#!/bin/bash
exec "$HOME/Desktop/Fila by Deji/fila-by-deji/backend/scripts/sweep-expired.sh"
SH
chmod +x "$HOME/bin/fila-expire"
```

Then use **this simpler crontab line instead of the path-with-spaces example**:

```cron
* * * * * "$HOME/bin/fila-expire" >> /tmp/fila-expiry.log 2>&1
```

The script uses `flock` to prevent overlapping sweeps on the same host. Cron does **not** work while your laptop is turned off. A hosted production deployment needs its own independent scheduled job.

## 5. PostgreSQL for a future deployment

SQLite continues to hold your **existing local customers and drafts**. Stage 8 does **not** silently copy SQLite data into PostgreSQL.

When a PostgreSQL server is ready, obtain its connection URL, enable TLS as required by the provider, and store it in **private host environment variables**. Example form (illustrative placeholders only, not working credentials):

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://ACCOUNT:PASSWORD@POSTGRES_HOST:5432/FILA_DB?sslmode=require
CORS_ORIGINS=https://YOUR-REAL-FRONTEND-DOMAIN
JWT_SECRET_KEY=GENERATE_A_LONG_RANDOM_VALUE_AND_KEEP_IT_SECRET
RATE_LIMIT_REDIS_URL=rediss://REDIS_USER:REDIS_PASSWORD@REDIS_TLS_HOST:6380/0
```

**No real credentials should be committed.** Use `python -c "import secrets; print(secrets.token_urlsafe(48))"` for a unique server JWT key and copy it into the hosting provider's secrets manager. Never post it in chat. If a password contains reserved URL characters, percent-encode them. If the Postgres provider offers `sslmode=verify-full` with a trusted CA, prefer verified TLS to `require`.

Before making the API public, connect to that **new database** through a secure private terminal, run `python -m alembic upgrade head` and `python -m app.seed` once, and then `python -m app.doctor`. Seeding creates sample products with zero available stock; enter actual verified stock using admin controls. Never seed a live store with fabricated inventory.

Stage 8 requires **Redis over TLS (`rediss://`) in production** to enforce shared per-IP request throttling across workers. The app intentionally refuses `APP_ENV=production` when `RATE_LIMIT_REDIS_URL` is blank or insecure. If Redis is unavailable, protected mutations/login respond with `503` rather than accepting unlimited requests.

## 6. Remaining requirements before launch

- Arrange independent managed PostgreSQL **backups and restore tests** and a production cron/scheduled worker for expired reservations.
- Test the stock-reservation race conditions on the actual PostgreSQL service, not only SQLite.
- Configure a trusted reverse proxy correctly (client IP must be verified; **never trust arbitrary** `X-Forwarded-For`). Test NAT/shared-IP rate limits and email-based abuse limits.
- Add admin MFA, login abuse monitoring, audit logs, email verification and account recovery.
- Implement shipping, legal/policy pages, and a payment-provider integration with verified webhooks, idempotency, refunds and reconciliation. **Do not accept real payments yet.**
