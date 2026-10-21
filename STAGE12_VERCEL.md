# Stage 12 — FÌLÀ by Deji Vercel storefront

The Figma-inspired HTML/CSS/images are intentionally unchanged.
A production Vercel deployment fetches catalog, auth and draft orders from:
`https://fila-by-deji-api.onrender.com/api/v1`
Local Ubuntu (`http://127.0.0.1:5500`) continues to use `http://127.0.0.1:8000/api/v1`.

## Create the storefront project
1. Ensure the Vercel app integration has access to the intended Vercel team and the GitHub repository `koladimeji01/fila-by-deji`. If Vercel returns 403 on the team, reconnect the app with team access before asking for deployment.
2. In Vercel, choose **Add New → Project → Import Git Repository** for `koladimeji01/fila-by-deji`.
3. Name it `fila-by-deji`. Set **Root Directory** to the repository root `.`, not `backend`. The committed `vercel.json` forces a Node static copy build with output directory `dist`.
4. Do not configure a paid plan just to test the frontend. Do **not** add any Supabase URL/password, JWT secret or Redis credentials to Vercel; the static site needs none of them.
5. Deploy and copy the **actual production domain** Vercel assigns, for example `https://YOUR-PROJECT.vercel.app`. Do not assume the domain before inspecting it.

## Connect Render CORS (essential)
Open the existing Render service `fila-by-deji-api` → **Environment**, and set:
```dotenv
CORS_ORIGINS=https://YOUR-ACTUAL-VERCEL-PRODUCTION-DOMAIN
```
This must be a literal HTTPS origin with no trailing slash, wildcard or path.
Save/deploy the Render service, then verify:
`https://fila-by-deji-api.onrender.com/api/v1/health`
and `https://fila-by-deji-api.onrender.com/api/v1/products`.

## Test
From Ubuntu repo root:
```bash
git pull origin main
npm run test:site
```
Build output `dist/` includes only 10 storefront HTML files, CSS, JavaScript and images. Backend, databases and local .env are excluded.
Confirm home/collection images, mobile layout, login, registration and draft orders against the live API. Stripe/Paystack payments are **not** implemented; reservations are temporary and do not mean paid/confirmed.
For local dev still run `python3 -m http.server 5500` from the repository root, not dist.
