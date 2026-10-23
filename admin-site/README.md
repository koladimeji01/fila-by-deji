# FÌLÀ by Deji — Business Administration

Independent staff-only frontend, stored in `admin-site/` and intended for a **separate Vercel project** at `https://fila-by-deji-admin.vercel.app`. It uses the existing Render FastAPI and Supabase database, never direct Supabase client credentials.

## Deploy

Create a new Vercel project from `koladimeji01/fila-by-deji` with **Root Directory** `admin-site` and project name `fila-by-deji-admin`. Production branch: `main`. The included `vercel.json` runs `node build.cjs`, outputs `dist`, disables indexing and prevents caching.

Only after confirming the admin domain, add its exact HTTPS origin to Render's `CORS_ORIGINS` preserving the storefront origin.

Open the site and sign in using a verified backend account with `is_admin=true`. The database currently has no such account, so an authorized operator must explicitly promote their verified account using audited administrative access; never silently promote the only account or grant admin access through a public signup form.

Payments remain disabled, and order statistics never claim sales revenue.

Note: This is a physically separate standalone app and Vercel build, currently hosted in a separate subfolder of the main GitHub repository until a new GitHub repository is provisioned and its Git integration authorized.
