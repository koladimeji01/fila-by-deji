# FÌLÀ by Deji — Business Administration

This is the standalone **staff-only** administration frontend. It lives in `admin-site/` within the FÌLÀ GitHub repository but deploys as a **separate Vercel project**, independent of the customer storefront.

## Live project

- Business portal: https://fila-by-deji-admin.vercel.app
- Alternate verified domain: https://fila-deji-business.vercel.app
- Customer storefront: https://fila-by-deji.vercel.app
- Vercel project: `fila-by-deji-admin`
- Git source: `koladimeji01/fila-by-deji`, branch `main`, root directory `admin-site`
- Backend: `https://fila-by-deji-api.onrender.com/api/v1`

Both admin URLs are now verified and assigned to the standalone administration project. Use `fila-by-deji-admin.vercel.app` as the primary staff portal. The production sign-in and sign-up page is reachable without a Vercel team login. **Vercel SSO protection remains enabled for preview deployments**, while every business-data API still requires a valid backend administrator role. The static portal also uses `noindex`, no-cache and a restrictive Content Security Policy.

## Business functions

- Create staff account from the sign-in page (name, email, password and password confirmation). This uses `/api/v1/auth/register`, which creates a **non-admin account**. It does not grant access or notify the business owner automatically.
- Administrator-only sign-in; the backend checks `users.is_admin` on each business endpoint
- Operations overview; totals are not sales revenue
- **Add a new product** through the Product Catalogue panel. Enter product name, category, description, price, a public HTTPS image URL, available quantities for sizes 32/35/39/41, and choose whether to publish. The backend generates a unique ID, creates all four inventory rows atomically and requires administrator authorization.
- Edit **existing** catalog names, categories, descriptions, prices and visibility
- View and set exact available stock by size
- Review unpaid customer enquiries and temporary holds
- Save delivery quotes on eligible draft enquiries
- Report on the latest 100 entries (not full historical totals), plus CSV export
- View the verified staff identity and end the browser session

The three original catalog photographs remain unchanged and are shipped from GitHub. New catalog photographs may be hosted publicly on a reliable image host; paste a direct public **HTTPS link ending in .jpg, .jpeg, .png or .webp**. The backend validates the URL but does not download the image. The admin panel does **not yet upload a file directly**; a Supabase Storage public bucket (none was configured when this was built) or another hosted image service can provide URLs once set up. Confirm you own or have permission to use each photo and test that it loads in the storefront. New products can be saved as **hidden drafts** until the image and stock are ready. The dashboard does **not** accept payments. No secrets or direct Supabase browser credentials are bundled.

## Backend and access

The production Render CORS origins include:

```text
https://fila-by-deji.vercel.app,https://fila-by-deji-assets.vercel.app,https://fila-by-deji-admin.vercel.app,https://fila-deji-business.vercel.app
```

New team members can create an account from the business portal. The same underlying account can be used for customer sign-in, but it **cannot** view the business dashboard until an authorized operator verifies the applicant and explicitly grants `users.is_admin=true` using the privileged operator procedure in `backend/app/admin.py`. There is no public self-approval endpoint or automated email/approval queue. The new staff member must contact the business owner for access. This workflow has not verified or automatically promoted any existing production administrator account.

## Build and test

```sh
cd admin-site
npm run build
node --check js/admin.js
```

The build emits only the approved admin HTML, JS, CSS and brand assets into `dist/`. The storefront build never includes this admin site. Backend tests run under GitHub Actions. Payment processing and confirmed orders are intentionally outside this phase.
