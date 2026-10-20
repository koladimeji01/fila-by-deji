# FÌLÀ by Deji

A polished, responsive, accessible frontend implementation based on the supplied Figma designs. Built with semantic **HTML5, CSS3, vanilla JavaScript**, and no build dependencies. The FÌLÀ logo follows the original Figma typography and black/yellow/charcoal signature stripes.

## Pages

- `index.html` — hero and featured collection
- `collection.html` — product grid, live search, filters
- `details.html?product=premium|classic|ceremonial` — product details, size and quantity selection
- `cart.html` — persistent shopping bag
- `checkout.html` — honest checkout preview, *not* a working payment form
- `about.html` — heritage story
- `contact.html` — non-sending enquiry composer

## Product images

Real cap imagery comes from the original Figma design, using assets under `/assets`: `hero.png`, `ceremonial.png`, `classic.png`, `premium.png`. The original Figma design is at: https://www.figma.com/design/px6gx3buqM8Uj2pqgGByXB/fila-by-deji?node-id=0-1

If the assets are not present yet, run `download-assets.ps1` on Windows or `download-assets.sh` on Unix. The scripts download **the original Figma asset URLs** and check whether each file is a valid PNG. These signed links may expire; in that case export the images anew from the original Figma document. The UI includes elegant fallback panels to avoid broken-image icons while assets are pending; never deploy for a client without the original photos.

## Run locally

Run a static server from the project root:

```sh
python -m http.server 5500
```

Then visit http://localhost:5500. No npm installation needed.

## Scope and security

This is **a frontend preview**: there is no server-side authentication, inventory system, completed orders, or live checkout/payment processing. The cart is browser-local and demonstrates interactions only. Prices in the Figma file are ₦10,000 for the three featured products. Product inventory and sizing should be confirmed before launching. Contact enquiries are only copied to the clipboard, not transmitted. Do not accept real payments or store personal customer information until a secure backend and verified payment integration are introduced.

## Accessibility

Semantic landmarks, descriptive alt text, focus indicators, reduced-motion support, keyboard navigation, responsive grids, and accessible field labels.

## Stage 6 — Stock by size and customer draft history

The backend now includes a zero-initialized inventory table and operator-only CLI to set **real, verified** stock, a new additive Alembic migration, backend stock checks for draft orders, pagination for customer history, and the authenticated `orders.html` page. Drafts remain unpaid and do **not** reserve stock. See [STAGE6_UBUNTU.md](STAGE6_UBUNTU.md) for Ubuntu update and test commands.


## Stage 7: Stock holds and operator API

See [STAGE7_UBUNTU.md](STAGE7_UBUNTU.md). Customer My orders page can temporarily hold stock for 15 minutes and cancel holds. The admin API is role-protected and the migration preserves current orders. **No payment or confirmation flow exists.**

## Stage 8 — Production preparation

See [`STAGE8_UBUNTU.md`](STAGE8_UBUNTU.md) for Ubuntu commands, schema preflight, basic API rate limiting, scheduled reservation expiry, and requirements before moving to PostgreSQL/Redis hosting. Payments are still disabled.
