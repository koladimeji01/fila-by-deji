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

- Create staff account from the sign-in page (name, email, password and password confirmation). This uses `/api/v1/staff/register`, which creates a **non-admin account and a pending staff application**. It does not grant access automatically.
- Existing customer accounts can select **Request staff access** from the admin sign-in page; this creates a pending request without duplicate registration.
- Staff managers can review pending applications, **approve**, **reject**, or **revoke operational access** using the Staff Management section. Applications and access changes are tracked in an audit table.
- Staff approvals require a distinct database-backed `can_manage_staff` permission, preserved for the pre-existing administrators during migration. Newly approved staff get `is_admin=true` but `can_manage_staff=false`.
- Administrator-only sign-in; the backend checks `users.is_admin` on each business endpoint
- Operations overview; totals are not sales revenue
- **Stage 10 notifications centre:** a staff-only inbox highlights new untouched enquiries from the past 14 days, active low/out-of-stock cap sizes (3 or fewer available units), and pending staff requests (visible only to managers). The unread badge and cards refresh on dashboard load or **Refresh alerts**. Staff can mark individual alerts or all current alerts as read; this preference is saved per staff account in a private table. Notifications resolve when enquiries are followed up, stock recovers, or staff applications are reviewed. There are **no email, SMS, or push notifications** in this stage. For performance, feeds include up to 25 staff applications, 25 enquiries, and 40 low-stock size variants; they are not a comprehensive audit feed.

- **Add a new product** through the Product Catalogue panel. Enter product name, category, description, price, a public HTTPS image URL, available quantities for sizes 32/35/39/41, and choose whether to publish. The backend generates a unique ID, creates all four inventory rows atomically and requires administrator authorization.
- Edit **existing** catalog names, categories, descriptions, prices and visibility
- View and set exact available stock by size
- **Stage 9 inventory monitoring:** choose a 2, 3, 5, or 10 unit threshold and review alerts for low-stock and sold-out sizes of **published** caps. The alert count uses live **available** stock after temporary holds. It is shown on dashboard refresh and is not an automatic push/email notification.
- **Staff adjustment history:** manual stock changes are audited with old/new available quantities, size, staff identity and a required reason category (Restock, Stock Count Correction, Damaged / Unavailable, Other). Recent 30 entries appear on the dashboard. Identical writes do not create duplicate audits. Customer holds, cancellations and expirations do not count as staff edits.
- Review unpaid customer enquiries and temporary holds
- Track enquiries through **New**, **Contacted**, **Awaiting Reply**, and **Closed Follow-up** stages with an internal note, last-updated timestamp, and search/filter tools. Filters apply only to currently loaded enquiries.
- The follow-up metadata lives in a private `enquiry_followups` table. Customer orders, paid state, inventory, and shipping quotes are never changed by these notes. No customer-facing messaging is sent.
- Save delivery quotes on eligible draft enquiries
- **Stage 8 operational analytics:** choose 7, 30, or 90 Lagos-calendar days, view daily enquiry bars, distinct customers, selected cap quantities, delivery quotes and the most requested products. These are **not sales or revenue**.
- Download an admin-authenticated CSV for that exact date range. CSV values are protected from spreadsheet formula injection; internal staff notes are excluded. Reporting is capped at 5,000 newest entries, and the UI explicitly warns about partial results and disables incomplete exports.
- View the verified staff identity and end the browser session

The original three catalog photographs remain unchanged and are shipped from GitHub. **New product photos can be uploaded directly from a device** (JPEG, PNG or WebP, maximum 5 MB), or supplied via a public HTTPS image URL. Uploaded photos are validated, resized to at most 1600 px and converted to WebP by the secured FastAPI backend. A single transaction saves the product, its stock sizes and compressed image to the private `product_photos` table in Supabase Postgres. The public image route only serves photos on published products; drafts stay private. Uploaded images use database space, so for a large catalog a dedicated private-upload/public-read object-storage service would be a future scalability upgrade. The existing URL method remains supported. Never upload photos you do not own or have permission to use. The dashboard does **not** accept payments. No database credentials or Supabase service keys are bundled in the browser.

## Backend and access

The production Render CORS origins include:

```text
https://fila-by-deji.vercel.app,https://fila-by-deji-assets.vercel.app,https://fila-by-deji-admin.vercel.app,https://fila-deji-business.vercel.app
```

New team members register from the business portal. The backend creates a **pending** `staff_applications` record. Existing customer accounts can also request approval using their current credentials. A **staff manager** sees only staff requests and existing admin accounts, not every registered customer. The owner should verify the staff applicant's identity before approving. An approval grants operational administrator access but **never** staff-management permission. Revoking access blocks existing JWTs immediately because roles are read from the database on every API request; it does not delete the user's customer account. Owner-level staff managers cannot be revoked through this panel, and users cannot change their own status. The `staff_access_audit` table retains review history. The dashboard does not currently send an email when applications arrive—staff managers should review the Staff section. No existing customer account was automatically promoted by this feature.

## Build and test

```sh
cd admin-site
npm run build
node --check js/admin.js
```

The build emits only the approved admin HTML, JS, CSS and brand assets into `dist/`. The storefront build never includes this admin site. Backend tests run under GitHub Actions. Payment processing and confirmed orders are intentionally outside this phase.


## Reporting limits and safeguards

Reports are calculated from actual database orders and order-item snapshots, not from browser state or estimated sales. Daily date boundaries use `Africa/Lagos`; an empty period displays zeros. A busy window exceeding **5,000** enquiries is marked partial and cannot be exported as if complete; select a shorter period. CSV downloads contain customers' names and emails, so restrict access to authorized staff and handle the file securely. No payment status or revenue is inferred from order subtotals or shipping quotations. The existing unpaid customer enquiry workflow is unchanged.
