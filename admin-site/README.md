# FÌLÀ by Deji — Business Administration

This is the standalone **staff-only** administration frontend. It lives in `admin-site/` within the FÌLÀ GitHub repository but deploys as a **separate Vercel project**, independent of the customer storefront.

## Live project

- Business portal: https://fila-deji-business.vercel.app
- Customer storefront: https://fila-by-deji.vercel.app
- Vercel project: `fila-by-deji-admin`
- Git source: `koladimeji01/fila-by-deji`, branch `main`, root directory `admin-site`
- Backend: `https://fila-by-deji-api.onrender.com/api/v1`

The former proposed `fila-by-deji-admin.vercel.app` alias was already assigned to another Vercel project, so `fila-deji-business.vercel.app` is the verified project domain. The Vercel admin project has **SSO protection enabled for all deployments**, plus `noindex`, no-cache and a restrictive Content Security Policy.

## Business functions

- Administrator-only sign-in; the backend checks `users.is_admin` on each business endpoint
- Operations overview; totals are not sales revenue
- Edit **existing** catalog names, categories, descriptions, prices and visibility
- View and set exact available stock by size
- Review unpaid customer enquiries and temporary holds
- Save delivery quotes on eligible draft enquiries
- Report on the latest 100 entries (not full historical totals), plus CSV export
- View the verified staff identity and end the browser session

Products' image files must be committed and deployed from the storefront repository. The dashboard does **not** upload images, create products or accept payments. No secrets or direct Supabase browser credentials are bundled.

## Backend and access

The production Render CORS origins include:

```text
https://fila-by-deji.vercel.app,https://fila-by-deji-assets.vercel.app,https://fila-deji-business.vercel.app
```

Sign in only with an already registered account that has been explicitly granted the admin role through an authorized operator. Customer sign-ups never grant admin privileges. There is currently no verified production administrator account configured through this workflow; account promotion requires explicit owner verification and should not be performed automatically.

## Build and test

```sh
cd admin-site
npm run build
node --check js/admin.js
```

The build emits only the approved admin HTML, JS, CSS and brand assets into `dist/`. The storefront build never includes this admin site. Backend tests run under GitHub Actions. Payment processing and confirmed orders are intentionally outside this phase.
