# FÌLÀ by Deji

A responsive Yoruba cap storefront based on the [original Figma design](https://www.figma.com/design/px6gx3buqM8Uj2pqgGByXB/fila-by-deji?node-id=0-1). The frontend is HTML, CSS and vanilla JavaScript; the API uses FastAPI and SQLAlchemy.

**Status: development / pre-deployment review. No payments or confirmed sales.** Do not launch as a paid store without completing the outstanding controls listed below.

## Pages

- Home: `index.html`
- Collection and filtering: `collection.html`
- Product details and size selection: `details.html?product=premium`
- Shopping bag: `cart.html`
- Draft checkout, **no payment**: `checkout.html`
- Customer login / registration: `login.html`, `register.html`
- Private draft orders and temporary holds: `orders.html`
- Brand story and contact: `about.html`, `contact.html`

## Original brand assets

The repository includes the original Figma cap photos as `assets/ceremonial.jpg`, `assets/classic.jpg`, `assets/premium.jpg`, the `assets/hero.png` artwork, and `assets/fila-logo.png`. Product prices and stock are loaded from the API—not hardcoded in the live catalog.

The historical `download-assets.*` scripts use expiring Figma asset links. Existing repository assets do **not** need redownloading.

## Run locally on Ubuntu

First, create and configure `backend/.env` based on `backend/.env.example`. Generate a random `JWT_SECRET_KEY` using:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Never commit the real `.env` or the local SQLite database.

Backend terminal:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m app.seed
python -m app.doctor
pytest -q
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal (from the repository root):

```bash
python3 -m http.server 5500 --bind 127.0.0.1
```

Open http://127.0.0.1:5500 and API documentation at http://127.0.0.1:8000/docs. Enter only **verified** cap stock quantities using `python -m app.inventory show` and `python -m app.inventory set <product> <size> <available_quantity>`.

## Ordering and limitations

Registration and login use Argon2/JWT; the backend validates product prices and stock. Customers can save drafts, temporarily hold stock for 15 minutes, cancel and view only their own orders. A draft does not reserve stock; a hold reserves available inventory but does **not** create a paid order.

Security preparation includes CORS restrictions, request throttling, migration preflight and a stock-expiry sweep script. See [backend/README.md](backend/README.md) and [STAGE8_UBUNTU.md](STAGE8_UBUNTU.md).

**Before deployment for real orders:** managed PostgreSQL and Redis, tested backups/restore, job scheduler, admin MFA/audit logs, password recovery and email verification, verified inventory and shipping policies, provider-signed payment webhooks/idempotency, and live deployment validation. Do not collect payment credentials or claim orders are paid.

## Audit

See [AUDIT_REPORT_2026-10-20.md](AUDIT_REPORT_2026-10-20.md) for defects fixed, automated test coverage, and outstanding launch blockers. Figma layout and brand assets were preserved during the code audit.
