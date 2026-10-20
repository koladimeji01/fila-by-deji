# Stage 5 — Ubuntu: connect website to FastAPI

## 1. Pull source

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
git pull origin main
```

## 2. Start API (terminal one)

```bash
cd backend
source .venv/bin/activate
# Do once if not already done: cp .env.example .env, set JWT_SECRET_KEY, alembic upgrade head, python -m app.seed
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs; verify http://127.0.0.1:8000/api/v1/products returns the three seeded products.

## 3. Start frontend (terminal two)

```bash
cd ~/Desktop/"Fila by Deji"/fila-by-deji
python3 -m http.server 5500 --bind 127.0.0.1
```

Open http://127.0.0.1:5500. **Both servers must be running at once**, and use `127.0.0.1` (not `localhost`) for these steps.

## 4. Test the full draft workflow

1. Open the collection page and check that the three caps load from the backend.
2. Select a cap, choose a size and add it to the shopping bag.
3. Open checkout, click **Save draft order — no payment**. You will be prompted to sign in.
4. On the login page choose **Create an account**. Register with a fresh email address and a password 12+ characters long.
5. Registration signs you in for this browser session and redirects to checkout. Click **Save draft order** again.
6. An order reference and the **server-calculated** total appear. No payment is collected, and stock isn't reserved.

## If you see 'Cannot reach FastAPI'

Check terminal one is still running. Confirm you opened the website at `http://127.0.0.1:5500`.

## Security and production restrictions

- JWT is held in browser `sessionStorage` (prototype only); never store passwords, secrets, or payment keys in browser code.
- Do **not** deploy this frontend as a live checkout; payments, rate limiting, account verification and production-grade session protection are still pending.
- For real customers, prefer secure `HttpOnly; Secure; SameSite` cookies with CSRF defenses, short sessions, and server-side logout/revocation.
- Do not trust amounts rendered in the browser: the FastAPI server is authoritative for draft totals.
- `API_BASE` is local-only. Configure production origins and an HTTPS API before deploying.