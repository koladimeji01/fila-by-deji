'use strict';

// Figma product information. The collection design repeats these three sample
// products; repeated cards do not represent additional inventory or SKUs.
const PRODUCTS = [
  { id: 'ceremonial', name: 'Ceremonial Fila', category: 'Ceremonial', description: 'Perfect for special occasions and cultural ceremonies.', price: 10000, image: 'assets/ceremonial.png' },
  { id: 'classic', name: 'Traditional Aso-oke Fila', category: 'Classic', description: 'Handwoven with traditional Nigerian Aso-oke fabric in vibrant colors.', price: 10000, image: 'assets/classic.png' },
  { id: 'premium', name: 'Royal Agbada Cap', category: 'Premium', description: 'Matching cap for royal Agbada with intricate embroidery.', price: 10000, image: 'assets/premium.png' }
];
const VARIATIONS = ['32', '35', '39', '41'];
const STORAGE_KEY = 'fila_by_deji_cart_v1';
const formatMoney = amount => `₦${Number(amount).toLocaleString('en-NG')}`;
const byId = id => document.getElementById(id);
const page = document.body.dataset.page || 'home';
let cart = loadCart();
let activeProduct = null;
let selectedSize = null;
let activeCategory = 'all';
let toastTimeout;
let lastTrigger = null;

function resolveCartKey(key) {
  const [id, size, extra] = key.split(':');
  if (extra !== undefined || (size && !VARIATIONS.includes(size))) return null;
  const product = PRODUCTS.find(p => p.id === id);
  return product ? { product, size: size || null } : null;
}
function loadCart() {
  try {
    const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      return Object.fromEntries(Object.entries(data).filter(([key, qty]) => resolveCartKey(key) && Number.isInteger(qty) && qty > 0 && qty <= 99));
    }
  } catch { /* Browser storage may be unavailable or invalid. */ }
  return {};
}
function saveCart() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cart)); } catch { /* Session cart still works. */ }
  renderCart();
}
function flash(message) {
  const toast = byId('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => toast.classList.remove('show'), 3300);
}
function detailsUrl(product) { return `details.html?product=${encodeURIComponent(product.id)}`; }
function productCard(product, linkToDetails = false) {
  const el = document.createElement(linkToDetails ? 'a' : 'button');
  if (linkToDetails) el.href = detailsUrl(product);
  else el.type = 'button';
  el.className = `product-card product-card--${product.id}`;
  el.setAttribute('aria-label', `View ${product.name}, ${formatMoney(product.price)}`);
  const visual = document.createElement('div');
  visual.className = 'product-card__visual';
  const image = document.createElement('img');
  image.src = product.image;
  image.alt = product.name;
  image.loading = 'lazy';
  visual.appendChild(image);
  const badge = document.createElement('span');
  badge.className = 'product-card__badge';
  badge.textContent = product.category;
  visual.appendChild(badge);
  const body = document.createElement('div');
  body.className = 'product-card__body';
  for (const [tag, cls, value] of [
    ['h3', 'product-card__title', product.name],
    ['p', 'product-card__description', product.description],
    ['strong', 'product-card__price', formatMoney(product.price)]
  ]) {
    const node = document.createElement(tag);
    node.className = cls;
    node.textContent = value;
    body.appendChild(node);
  }
  el.append(visual, body);
  if (!linkToDetails) el.addEventListener('click', () => openProduct(product, el));
  return el;
}
function renderHomepage() {
  const grid = byId('products-grid');
  if (!grid) return;
  grid.replaceChildren();
  for (let row = 0; row < 3; row++) PRODUCTS.forEach(product => grid.appendChild(productCard(product)));
}
function collectionProducts() {
  const query = (byId('collection-search')?.value || '').trim().toLocaleLowerCase();
  const sampleOrder = Array.from({ length: 6 }, () => [PRODUCTS[0], PRODUCTS[1], PRODUCTS[2], PRODUCTS[2]]).flat();
  return sampleOrder.filter(product =>
    (activeCategory === 'all' || product.id === activeCategory) &&
    `${product.name} ${product.category} ${product.description}`.toLocaleLowerCase().includes(query)
  );
}
function renderCollection() {
  const grid = byId('collection-grid');
  if (!grid) return;
  const products = collectionProducts();
  grid.replaceChildren(...products.map(product => productCard(product, true)));
  const empty = byId('collection-empty');
  if (empty) empty.hidden = products.length > 0;
  const resultLabel = byId('results-label');
  if (resultLabel) resultLabel.textContent = `${products.length} product cards shown`;
  document.querySelectorAll('[data-category]').forEach(button => {
    const checked = button.dataset.category === activeCategory;
    button.setAttribute('aria-pressed', String(checked));
    button.classList.toggle('selected', checked);
  });
}
function initCollection() {
  if (!byId('collection-grid')) return;
  renderCollection();
  byId('collection-search')?.addEventListener('input', renderCollection);
  const filters = byId('collection-filters');
  byId('filter-toggle')?.addEventListener('click', () => {
    filters.hidden = !filters.hidden;
    byId('filter-toggle').setAttribute('aria-expanded', String(!filters.hidden));
  });
  filters?.querySelectorAll('[data-category]').forEach(button => button.addEventListener('click', () => {
    activeCategory = button.dataset.category;
    filters.hidden = true;
    byId('filter-toggle').setAttribute('aria-expanded', 'false');
    renderCollection();
  }));
  byId('search-clear')?.addEventListener('click', () => {
    byId('collection-search').value = '';
    byId('collection-search').focus();
    renderCollection();
  });
}
function initDetails() {
  const title = byId('detail-title');
  if (!title) return;
  const requestedId = new URLSearchParams(location.search).get('product');
  activeProduct = PRODUCTS.find(product => product.id === requestedId) || PRODUCTS[2];
  document.title = `${activeProduct.name} | FÌLÀ by Deji`;
  title.textContent = activeProduct.name;
  byId('detail-description').textContent = activeProduct.description;
  byId('detail-price').textContent = formatMoney(activeProduct.price);
  byId('detail-photo').src = activeProduct.image;
  byId('detail-photo').alt = activeProduct.name;
  byId('detail-photo').parentElement.className = `detail-photo-frame detail-photo-frame--${activeProduct.id}`;
  byId('detail-variations').replaceChildren(...VARIATIONS.map(size => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'size-option';
    button.textContent = size;
    button.setAttribute('aria-pressed', 'false');
    button.setAttribute('aria-label', `Select size ${size}`);
    button.addEventListener('click', () => {
      selectedSize = size;
      byId('size-error').hidden = true;
      document.querySelectorAll('.size-option').forEach(el => {
        const isSelected = el === button;
        el.setAttribute('aria-pressed', String(isSelected));
        el.classList.toggle('selected', isSelected);
      });
    });
    return button;
  }));
  const suggestions = byId('related-grid');
  [PRODUCTS[0], PRODUCTS[1], PRODUCTS[2], PRODUCTS[2]].forEach(product => suggestions.appendChild(productCard(product, true)));
  byId('detail-add-to-cart').addEventListener('click', event => {
    if (!selectedSize) {
      const error = byId('size-error');
      error.hidden = false;
      byId('detail-variations').querySelector('button').focus();
      return;
    }
    changeQty(`${activeProduct.id}:${selectedSize}`, 1);
    openCart(event.currentTarget);
    flash(`${activeProduct.name}, size ${selectedSize}, added to your cart.`);
  });
}
function setOverlay(open) {
  const overlay = byId('overlay');
  if (!overlay) return;
  overlay.hidden = !open;
  document.body.classList.toggle('modal-open', open);
}
function closePanels() {
  const drawer = byId('cart-drawer');
  const dialog = byId('product-dialog');
  const wasOpen = !!drawer?.classList.contains('open') || !!dialog?.classList.contains('open');
  drawer?.classList.remove('open');
  drawer?.setAttribute('aria-hidden', 'true');
  drawer?.setAttribute('inert', '');
  byId('cart-button')?.setAttribute('aria-expanded', 'false');
  dialog?.classList.remove('open');
  dialog?.setAttribute('aria-hidden', 'true');
  setOverlay(false);
  if (wasOpen && lastTrigger?.isConnected) lastTrigger.focus();
}
function openCart(trigger = byId('cart-button')) {
  const drawer = byId('cart-drawer');
  if (!drawer) return;
  lastTrigger = trigger;
  byId('product-dialog')?.classList.remove('open');
  byId('product-dialog')?.setAttribute('aria-hidden', 'true');
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  drawer.removeAttribute('inert');
  byId('cart-button')?.setAttribute('aria-expanded', 'true');
  setOverlay(true);
  byId('close-cart')?.focus();
}
function openProduct(product, trigger) {
  const dialog = byId('product-dialog');
  if (!dialog) { window.location.href = detailsUrl(product); return; }
  activeProduct = product;
  lastTrigger = trigger;
  byId('dialog-image').src = product.image;
  byId('dialog-image').alt = product.name;
  byId('dialog-title').textContent = product.name;
  byId('dialog-category').textContent = product.category;
  byId('dialog-description').textContent = product.description;
  byId('dialog-price').textContent = formatMoney(product.price);
  const fullDetails = byId('full-details-link');
  if (fullDetails) fullDetails.href = detailsUrl(product);
  dialog.classList.add('open');
  dialog.setAttribute('aria-hidden', 'false');
  setOverlay(true);
  byId('close-product')?.focus();
}
function renderCart() {
  const count = Object.values(cart).reduce((sum, quantity) => sum + quantity, 0);
  const countText = count > 99 ? '99+' : String(count);
  byId('cart-count') && (byId('cart-count').textContent = countText);
  byId('cart-button')?.setAttribute('aria-label', `Open shopping cart, ${count} items`);
  const list = byId('cart-items');
  if (!list) return;
  list.replaceChildren();
  let total = 0;
  if (!count) {
    const message = document.createElement('p');
    message.className = 'cart-empty';
    message.textContent = 'Your cart is empty. Explore the collection to add a cap.';
    list.appendChild(message);
  }
  Object.entries(cart).forEach(([key, qty]) => {
    const selection = resolveCartKey(key);
    if (!selection) return;
    const { product, size } = selection;
    total += product.price * qty;
    const item = document.createElement('article');
    item.className = 'cart-item';
    const img = document.createElement('img'); img.src = product.image; img.alt = product.name;
    const info = document.createElement('div'); info.className = 'cart-item__info';
    const heading = document.createElement('h3'); heading.textContent = product.name;
    const variation = document.createElement('p'); variation.textContent = size ? `Size ${size}` : 'Size not selected';
    const price = document.createElement('p'); price.textContent = formatMoney(product.price * qty);
    const controls = document.createElement('div'); controls.className = 'quantity-controls';
    const minus = document.createElement('button'); minus.type = 'button'; minus.textContent = '−'; minus.setAttribute('aria-label', `Remove one ${product.name}`); minus.addEventListener('click', () => changeQty(key, -1));
    const amount = document.createElement('span'); amount.textContent = String(qty);
    const plus = document.createElement('button'); plus.type = 'button'; plus.textContent = '+'; plus.setAttribute('aria-label', `Add one ${product.name}`); plus.addEventListener('click', () => changeQty(key, 1));
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'remove-item'; remove.textContent = 'Remove'; remove.addEventListener('click', () => { delete cart[key]; saveCart(); });
    controls.append(minus, amount, plus, remove);
    info.append(heading, variation, price, controls);
    item.append(img, info);
    list.appendChild(item);
  });
  const totalLabel = byId('cart-total');
  if (totalLabel) totalLabel.textContent = formatMoney(total);
}
function changeQty(key, delta) {
  if (!resolveCartKey(key)) return;
  const updated = (cart[key] || 0) + delta;
  if (updated > 99) return flash('Maximum 99 of each cap variation per cart.');
  if (updated > 0) cart[key] = updated;
  else delete cart[key];
  saveCart();
}
function initPanels() {
  renderCart();
  byId('cart-button')?.addEventListener('click', () => openCart());
  byId('close-cart')?.addEventListener('click', closePanels);
  byId('continue-shopping')?.addEventListener('click', closePanels);
  byId('close-product')?.addEventListener('click', closePanels);
  byId('overlay')?.addEventListener('click', closePanels);
  byId('add-to-cart')?.addEventListener('click', () => {
    if (!activeProduct) return;
    // Homepage quick-view doesn't include a size selector in the Figma design.
    // Direct customers to the real details/variation screen before adding.
    window.location.href = detailsUrl(activeProduct);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closePanels();
    if (event.key !== 'Tab' || !document.body.classList.contains('modal-open')) return;
    const dialog = byId('cart-drawer')?.classList.contains('open') ? byId('cart-drawer') : byId('product-dialog');
    if (!dialog) return;
    const focusables = [...dialog.querySelectorAll('button:not([disabled]),a[href],input:not([disabled])')].filter(el => el.getClientRects().length);
    if (!focusables.length) return;
    if (event.shiftKey && document.activeElement === focusables[0]) { event.preventDefault(); focusables[focusables.length - 1].focus(); }
    else if (!event.shiftKey && document.activeElement === focusables[focusables.length - 1]) { event.preventDefault(); focusables[0].focus(); }
  });
}
function initNavigation() {
  byId('account-button')?.addEventListener('click', () => flash('The Account screen will be connected in a future stage.'));
  byId('account-avatar')?.addEventListener('click', () => flash('The Account screen will be connected in a future stage.'));
  byId('menu-button')?.addEventListener('click', () => {
    const nav = byId('site-nav');
    const open = nav.classList.toggle('open');
    byId('menu-button').setAttribute('aria-expanded', String(open));
  });
  byId('site-nav')?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    byId('site-nav').classList.remove('open');
    byId('menu-button').setAttribute('aria-expanded', 'false');
  }));
  document.querySelectorAll('[data-story-link],[data-contact-link],[data-unavailable-link]').forEach(link => link.addEventListener('click', event => {
    event.preventDefault();
    flash('This page is included in the Figma design and will be built in a later stage.');
  }));
}
function init() {
  initPanels();
  initNavigation();
  if (page === 'home') renderHomepage();
  if (page === 'collection') initCollection();
  if (page === 'details') initDetails();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();