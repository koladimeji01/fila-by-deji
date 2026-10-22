'use strict';
// Output only the approved static storefront files. Never deploy backend or secrets.
const { cpSync, existsSync, mkdirSync, rmSync } = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const destination = path.join(root, 'dist');
const pages = [
  'index.html', 'collection.html', 'details.html', 'cart.html', 'checkout.html',
  'about.html', 'contact.html', 'orders.html', 'login.html', 'register.html', 'profile.html',
];
const files = [
  ...pages, 'css/style.css', 'js/app.js',
  'assets/ceremonial.jpg', 'assets/classic.jpg', 'assets/premium.jpg',
  'assets/hero.png', 'assets/fila-logo.png', 'assets/fila-logo.svg',
  'assets/favicon.svg',
];

rmSync(destination, { recursive: true, force: true });
for (const relative of files) {
  const source = path.join(root, relative);
  if (!existsSync(source)) throw new Error(`Missing storefront asset: ${relative}`);
  const target = path.join(destination, relative);
  mkdirSync(path.dirname(target), { recursive: true });
  cpSync(source, target);
}
if (existsSync(path.join(destination, 'backend'))) {
  throw new Error('Backend code must not be included in the storefront build.');
}
console.log(`FÌLÀ storefront build: ${pages.length} HTML pages and ${files.length - pages.length} static assets in dist/.`);
