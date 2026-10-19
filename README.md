# FÌLÀ by Deji — Website (Stage 2)

A responsive **HTML, CSS, and vanilla JavaScript** implementation of these original Figma screens:

- **Homepage:** Landing page `1:1118` → `index.html`
- **Collection:** Collection page `1:1306` → `collection.html`
- **Product Details:** Details page `1:1558` → `details.html?product=premium`

Figma file: https://www.figma.com/design/px6gx3buqM8Uj2pqgGByXB/fila-by-deji

## 1. Get the exact Figma imagery

The package includes code, styles, and a local-asset download script, but **not the original Figma photos or social SVG icons**. Those files must be downloaded once. Open the *fila-by-deji* folder in VS Code, open PowerShell in that folder, and run:

```powershell
.\download-assets.ps1
```

The script saves these seven Figma assets into `assets/`:

- `hero.png`
- `ceremonial.png`
- `classic.png`
- `premium.png`
- `facebook.svg`
- `instagram.svg`
- `twitter.svg`

Temporary Figma asset links were retrieved on **October 19, 2026** and typically expire **within seven days**. If a URL has expired, the images must be exported again from Figma and saved locally with these exact filenames. **Do not upload to a live host until these assets are present.**

## 2. Run in VS Code

Install the VS Code **Live Server** extension, right-click `index.html`, choose **Open with Live Server**. The site usually opens at `http://127.0.0.1:5500/`.

Or from a terminal in the *fila-by-deji* folder:

```powershell
python -m http.server 5500
```

Visit these pages:

- `http://127.0.0.1:5500/index.html` — Homepage
- `http://127.0.0.1:5500/collection.html` — Collection
- `http://127.0.0.1:5500/details.html?product=premium` — Royal Agbada Cap details
- `http://127.0.0.1:5500/details.html?product=classic` — Traditional Aso-oke Fila details
- `http://127.0.0.1:5500/details.html?product=ceremonial` — Ceremonial Fila details

## 3. What works in Stage 2

- Homepage's **View Full Collection** and nav **Collection** link open the real collection page
- Desktop: 4-column, 6-row collection grid based on the original Figma (24 sample cards, intentionally reusing the three designs shown)
- Responsive grid: 2 columns on most phones, 1 on the narrowest screens
- Live collection search and category filter with clear and empty states
- Product cards open a full **Details** page
- Size variations **32 / 35 / 39 / 41**, with a required selection before adding
- Size-aware cart: adding the same cap in two sizes produces separate cart rows
- Quantity updates and subtotals in **naira (₦)**
- Cart saved in the browser using localStorage, shared between the pages
- Accessible back links, keyboard focus, and Escape-to-close cart
- Footer and social icon designs are from Figma; social icons are decorative until verified URLs are supplied

### Important limits

**This is a frontend prototype, not an operational ecommerce store.** Prices and the sample three designs are taken from the Figma mockup. Stock levels have not been verified. The cart is local to the browser; payments, checkout, accounts, the About/Contact pages, and order processing are not yet integrated. The 24 Collection cards intentionally repeat the three designed items; this is how the Figma screen is arranged, not 24 different products.

Until actual contact/social links are supplied, the footer links that aren't implemented show an informative notice, rather than sending customers to made-up addresses.

## 4. Files

```
fila-by-deji/
├── index.html
├── collection.html
├── details.html
├── css/style.css
├── js/app.js
├── assets/favicon.svg
├── download-assets.ps1
└── README.md
```

## 5. Next stage

Build the Figma **Cart page** and **Checkout page** and connect navigation. Later we can add a secure backend and a supported payment provider after agreeing on requirements. Do not accept real orders or card payments until backend validations and security measures are in place.