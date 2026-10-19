# FÌLÀ by Deji — Editorial storefront

A redesigned, responsive fashion storefront for FÌLÀ by Deji, built with **HTML, CSS and vanilla JavaScript**. The visual language combines Yoruba cultural identity, warm gold, forest green, contemporary typography and spacious product photography.

## Pages

- `index.html` — editorial homepage, signature caps, brand story and collection categories
- `collection.html` — searchable collection with category filters and sorting (three products shown in Figma)
- `details.html?product=premium` — Royal Agbada Cap details, sizes, quantity, add to bag
- `details.html?product=ceremonial` — Ceremonial Fila
- `details.html?product=classic` — Traditional Aso-oke Fila
- `cart.html` — bag review, quantities and subtotal
- `about.html` — brand story
- `contact.html` — contact enquiry preparation (no emails or messages are sent)

## Run locally

Use VS Code Live Server, or from the project root run:

```powershell
python -m http.server 5500
```

Open <http://127.0.0.1:5500/index.html>.

## Images

The original Figma file is [FÌLÀ by Deji](https://www.figma.com/design/px6gx3buqM8Uj2pqgGByXB/fila-by-deji). Save the original photographs at:

- `assets/hero.png`
- `assets/ceremonial.png`
- `assets/classic.png`
- `assets/premium.png`

The website uses these original images, not external replacements. Until the image files are added, the website displays attractive branded placeholders instead of broken images. The existing `download-assets.ps1` script contains **temporary Figma URLs obtained on 19 October 2026**, which may expire around 26 October 2026. Once downloaded, **commit the actual image files to the repository** so hosting services can serve them permanently.

## Cart and checkout

The cart uses `localStorage` key `fila_by_deji_cart_v1` and retains size variations (32, 35, 39, 41). The prototype prices are ₦10,000 per cap as shown in Figma. The catalog is not an inventory system; stock levels, shipping, and prices need business confirmation.

**This is a frontend showcase, not a production shop.** No live order submission, checkout, payment processing, accounts or customer service backend has been configured. The checkout action is disabled and the contact form only prepares a local, copyable message. Connect a secure backend/payment provider and verified business contact details before accepting real orders.

## Structure

```
index.html
collection.html
details.html
cart.html
about.html
contact.html
css/style.css
js/app.js
assets/favicon.svg
download-assets.ps1
README.md
```

All navigation is relative to the project root, ready for GitHub Pages, Netlify or Vercel static hosting.