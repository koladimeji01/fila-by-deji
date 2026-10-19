'use strict';

// Central catalogue. Prices and imagery come from the supplied Figma mock-up;
// availability is not verified and no live payment service is connected.
const PRODUCTS = Object.freeze([
  { id:'ceremonial', name:'Ceremonial Fila', category:'Ceremonial', label:'FOR THE OCCASION', description:'Perfect for special occasions and cultural ceremonies.', price:10000, image:'assets/ceremonial.png' },
  { id:'classic', name:'Traditional Aso-oke Fila', category:'Classic', label:'THE EVERYDAY CLASSIC', description:'Handwoven with traditional Nigerian Aso-oke fabric in vibrant colours.', price:10000, image:'assets/classic.png' },
  { id:'premium', name:'Royal Agbada Cap', category:'Premium', label:'THE ROYAL EDIT', description:'A matching cap for royal Agbada, finished with intricate embroidery.', price:10000, image:'assets/premium.png' }
]);
const SIZES = ['32','35','39','41'];
const STORAGE_KEY = 'fila_by_deji_cart_v1';
const $ = id => document.getElementById(id);
const money = n => '₦'+Number(n).toLocaleString('en-NG');
const page = document.body.dataset.page || 'home';
let cart = loadCart(), activeCategory='all', activeSize=null, selectedQty=1, toastTimer, lastFocus=null;

function findProduct(id){return PRODUCTS.find(p=>p.id===id) || null;}
function parseKey(key){
  if(typeof key !== 'string') return null;
  const parts=key.split(':');
  if(parts.length>2 || !findProduct(parts[0]) || (parts[1] && !SIZES.includes(parts[1]))) return null;
  return { product:findProduct(parts[0]),size:parts[1]||null };
}
function loadCart(){
  try {const value=JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}');
    if(value && typeof value==='object' && !Array.isArray(value)) return Object.fromEntries(Object.entries(value).filter(([k,n])=>parseKey(k)&&Number.isInteger(n)&&n>0&&n<=99));
  } catch(e){/* Storage can be unavailable. */}
  return {};
}
function saveCart(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(cart));}catch(e){} updateCart();}
function cartCount(){return Object.values(cart).reduce((a,b)=>a+b,0);}
function cartTotal(){return Object.entries(cart).reduce((total,[key,qty])=>total+(parseKey(key)?.product.price||0)*qty,0);}
function flash(message){const node=$('toast');if(!node)return;node.textContent=message;node.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.classList.remove('show'),3500);}
function productUrl(product){return 'details.html?product='+encodeURIComponent(product.id);}

// The photograph area has a branded fallback so missing local exports never show broken-image icons.
function activateImages(container=document){
  container.querySelectorAll('img[data-fallback]:not([data-image-ready])').forEach(img=>{
    img.dataset.imageReady='1';
    const holder=img.closest('.image-shell');
    img.addEventListener('error',()=>holder?.classList.add('image-missing'));
    img.addEventListener('load',()=>holder?.classList.remove('image-missing'));
    if(img.complete && img.naturalWidth===0) holder?.classList.add('image-missing');
  });
}
function makePhoto(product,extra=''){
  const shell=document.createElement('div');shell.className='image-shell '+extra;
  const fallback=document.createElement('div');fallback.className='image-placeholder';fallback.setAttribute('aria-hidden','true');
  const heading=document.createElement('strong');heading.textContent='FÌLÀ';const label=document.createElement('small');label.textContent='BY DEJI';fallback.append(heading,label);
  const img=document.createElement('img');img.src=product.image;img.alt=product.name;img.loading='lazy';img.setAttribute('data-fallback','');
  shell.append(fallback,img);activateImages(shell);return shell;
}
function makeCard(product){
  const card=document.createElement('article');card.className='product-card';
  const link=document.createElement('a');link.className='product-card__image image-shell';link.href=productUrl(product);link.setAttribute('aria-label','View '+product.name);
  const fallback=document.createElement('div');fallback.className='image-placeholder';fallback.setAttribute('aria-hidden','true');const heading=document.createElement('strong');heading.textContent='FÌLÀ';const small=document.createElement('small');small.textContent='BY DEJI';fallback.append(heading,small);
  const img=document.createElement('img');img.src=product.image;img.alt=product.name;img.loading='lazy';img.setAttribute('data-fallback','');
  const tag=document.createElement('span');tag.className='product-tag';tag.textContent=product.label;
  link.append(fallback,img,tag);
  const body=document.createElement('div');body.className='product-card__body';
  const top=document.createElement('div');top.className='product-card__top';
  const name=document.createElement('h3');name.className='product-card__name';const nameLink=document.createElement('a');nameLink.href=productUrl(product);nameLink.textContent=product.name;name.appendChild(nameLink);
  const price=document.createElement('strong');price.className='product-card__price';price.textContent=money(product.price);
  top.append(name,price);
  const description=document.createElement('p');description.className='product-card__description';description.textContent=product.description;
  const action=document.createElement('a');action.className='product-card__action';action.href=productUrl(product);action.append('Explore design ');const arrow=document.createElement('span');arrow.textContent='↗';arrow.setAttribute('aria-hidden','true');action.appendChild(arrow);
  body.append(top,description,action);card.append(link,body);activateImages(card);return card;
}
function renderProductGrid(id,products){const grid=$(id);if(!grid)return;grid.replaceChildren(...products.map(makeCard));}

function initCollection(){
  if(!$('collection-grid')) return;
  const queryCategory=new URLSearchParams(location.search).get('category');
  if(['ceremonial','classic','premium'].includes(queryCategory)) activeCategory=queryCategory;
  const search=$('collection-search');const sort=$('sort-products');
  function render(){
    const query=(search.value||'').trim().toLocaleLowerCase();
    const matched=PRODUCTS.filter(p=>(activeCategory==='all'||p.id===activeCategory)&&(`${p.name} ${p.category} ${p.description}`).toLocaleLowerCase().includes(query));
    if(sort.value==='name')matched.sort((a,b)=>a.name.localeCompare(b.name));
    if(sort.value==='price-asc')matched.sort((a,b)=>a.price-b.price);
    if(sort.value==='price-desc')matched.sort((a,b)=>b.price-a.price);
    renderProductGrid('collection-grid',matched);
    $('results-label').textContent=matched.length+' '+(matched.length===1?'design':'designs');
    $('collection-empty').hidden=matched.length!==0;
    document.querySelectorAll('[data-category]').forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.category===activeCategory)));
  }
  search.addEventListener('input',render);sort.addEventListener('change',render);
  $('category-chips').addEventListener('click',e=>{const btn=e.target.closest('[data-category]');if(!btn)return;activeCategory=btn.dataset.category;render();});
  $('clear-filters')?.addEventListener('click',()=>{search.value='';activeCategory='all';sort.value='featured';render();search.focus();});
  render();
}
function initDetails(){
  if(!$('detail-title'))return;
  const id=new URLSearchParams(location.search).get('product');
  const product=findProduct(id)||PRODUCTS[2];document.title=product.name+' | FÌLÀ by Deji';
  $('detail-title').textContent=product.name;$('detail-description').textContent=product.description;
  $('detail-category').textContent=product.label;$('detail-price').textContent=money(product.price);
  $('breadcrumb-name').textContent=product.name;$('detail-photo').src=product.image;$('detail-photo').alt=product.name;
  $('detail-photo').closest('.image-shell').classList.remove('image-missing');
  const sizes=$('detail-variations');
  SIZES.forEach(size=>{const btn=document.createElement('button');btn.type='button';btn.textContent=size;btn.className='size-option';btn.setAttribute('aria-label','Select size '+size);btn.setAttribute('aria-pressed','false');btn.addEventListener('click',()=>{activeSize=size;$('size-error').hidden=true;sizes.querySelectorAll('button').forEach(n=>{n.classList.toggle('selected',n===btn);n.setAttribute('aria-pressed',String(n===btn));});});sizes.appendChild(btn);});
  $('qty-minus').addEventListener('click',()=>{selectedQty=Math.max(1,selectedQty-1);$('detail-quantity').textContent=selectedQty;});
  $('qty-plus').addEventListener('click',()=>{selectedQty=Math.min(99,selectedQty+1);$('detail-quantity').textContent=selectedQty;});
  $('detail-add-to-cart').addEventListener('click',e=>{if(!activeSize){$('size-error').hidden=false;sizes.querySelector('button').focus();return;}changeQty(product.id+':'+activeSize,selectedQty);openCart(e.currentTarget);flash(product.name+' (size '+activeSize+') added to your bag');});
  renderProductGrid('related-grid',PRODUCTS.filter(p=>p.id!==product.id));
}
function changeQty(key,amount){if(!parseKey(key))return;const n=(cart[key]||0)+amount;if(n>99){flash('Maximum 99 pieces per size');return;}if(n<=0)delete cart[key];else cart[key]=n;saveCart();}
function removeItem(key){delete cart[key];saveCart();}
function addQuantityControls(key,quantity){
  const group=document.createElement('div');group.className='quantity-controls';
  const minus=document.createElement('button');minus.type='button';minus.textContent='−';minus.setAttribute('aria-label','Decrease quantity');minus.addEventListener('click',()=>changeQty(key,-1));
  const value=document.createElement('span');value.textContent=quantity;value.setAttribute('aria-label','Quantity '+quantity);
  const plus=document.createElement('button');plus.type='button';plus.textContent='+';plus.setAttribute('aria-label','Increase quantity');plus.addEventListener('click',()=>changeQty(key,1));
  const remove=document.createElement('button');remove.type='button';remove.className='remove-item';remove.textContent='Remove';remove.setAttribute('aria-label','Remove item');remove.addEventListener('click',()=>removeItem(key));
  group.append(minus,value,plus,remove);return group;
}
function makeCartRow(key,qty,full=false){
  const parsed=parseKey(key);if(!parsed)return null;const {product,size}=parsed;
  const item=document.createElement('article');item.className=full?'cart-page-item':'drawer-item';
  const photo=makePhoto(product,full?'cart-page-photo':'');
  const info=document.createElement('div');const name=document.createElement('h3');const link=document.createElement('a');link.href=productUrl(product);link.textContent=product.name;name.appendChild(link);
  const variation=document.createElement('p');variation.textContent=size?'Size '+size:'Size not selected';
  if(full){info.append(name,variation,addQuantityControls(key,qty));const total=document.createElement('strong');total.className='item-price';total.textContent=money(product.price*qty);item.append(photo,info,total);}
  else{const total=document.createElement('strong');total.textContent=money(product.price*qty);info.append(name,variation,total,addQuantityControls(key,qty));item.append(photo,info);}
  return item;
}
function updateCart(){
  const count=cartCount();const countLabel=$('cart-count');if(countLabel)countLabel.textContent=count>99?'99+':String(count);
  $('cart-button')?.setAttribute('aria-label','Open shopping bag, '+count+' items');
  if($('drawer-count'))$('drawer-count').textContent='('+count+')';
  if($('cart-total'))$('cart-total').textContent=money(cartTotal());
  const drawer=$('cart-items');if(drawer){drawer.replaceChildren();if(!count){const empty=document.createElement('p');empty.className='drawer-empty';const title=document.createElement('strong');title.textContent='Your bag is waiting.';empty.append(title,document.createTextNode('Find a piece that feels like you.'));drawer.appendChild(empty);}else Object.entries(cart).forEach(([key,qty])=>{const row=makeCartRow(key,qty);if(row)drawer.appendChild(row);});}
  const pageRows=$('cart-page-items');if(pageRows){pageRows.replaceChildren();if(!count){const div=document.createElement('div');div.className='cart-empty-page';const title=document.createElement('h2');title.textContent='Your bag is empty.';const intro=document.createElement('p');intro.textContent='A great look begins with one good piece.';const shop=document.createElement('a');shop.href='collection.html';shop.className='button button--dark';shop.textContent='Explore the collection →';div.append(title,intro,shop);pageRows.appendChild(div);}else Object.entries(cart).forEach(([key,qty])=>{const row=makeCartRow(key,qty,true);if(row)pageRows.appendChild(row);});}
  if($('summary-items'))$('summary-items').textContent=count;
  if($('summary-total'))$('summary-total').textContent=money(cartTotal());
}
function openCart(trigger){const drawer=$('cart-drawer');if(!drawer)return;lastFocus=trigger||document.activeElement;drawer.inert=false;drawer.classList.add('open');drawer.setAttribute('aria-hidden','false');$('overlay').hidden=false;requestAnimationFrame(()=>$('overlay').classList.add('active'));document.body.classList.add('modal-open');$('cart-button').setAttribute('aria-expanded','true');$('close-cart').focus();}
function closeCart(){const drawer=$('cart-drawer');if(!drawer||!drawer.classList.contains('open'))return;drawer.classList.remove('open');drawer.setAttribute('aria-hidden','true');drawer.inert=true;$('overlay').classList.remove('active');$('overlay').hidden=true;document.body.classList.remove('modal-open');$('cart-button').setAttribute('aria-expanded','false');if(lastFocus?.isConnected)lastFocus.focus();}
function initCart(){updateCart();$('cart-button')?.addEventListener('click',e=>openCart(e.currentTarget));$('close-cart')?.addEventListener('click',closeCart);$('overlay')?.addEventListener('click',closeCart);$('continue-shopping')?.addEventListener('click',closeCart);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeCart();closeMenu();}if(e.key!=='Tab'||!$('cart-drawer')?.classList.contains('open'))return;const focusable=[...$('cart-drawer').querySelectorAll('a[href],button:not([disabled]),input:not([disabled])')].filter(n=>n.getClientRects().length);if(!focusable.length)return;const first=focusable[0],last=focusable[focusable.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}});
}
function closeMenu(){const nav=$('site-nav');nav?.classList.remove('open');$('menu-button')?.setAttribute('aria-expanded','false');}
function initNav(){document.querySelector(`[data-nav="${page==='details'?'collection':page==='cart'?'collection':page}"]`)?.setAttribute('aria-current','page');$('menu-button')?.addEventListener('click',()=>{const nav=$('site-nav');const opened=nav.classList.toggle('open');$('menu-button').setAttribute('aria-expanded',String(opened));});$('site-nav')?.querySelectorAll('a').forEach(link=>link.addEventListener('click',closeMenu));$('current-year').textContent=new Date().getFullYear();}
function initContact(){const form=$('enquiry-form');if(!form)return;form.addEventListener('submit',e=>{e.preventDefault();if(!form.reportValidity())return;const data=new FormData(form);const name=String(data.get('name')||'').trim(), subject=String(data.get('subject')||'').trim(),message=String(data.get('message')||'').trim();if(!name||message.length<10)return;$('enquiry-output').value='From: '+name+'\nSubject: '+subject+'\n\n'+message;$('enquiry-result').hidden=false;$('enquiry-result').scrollIntoView({block:'nearest',behavior:'smooth'});});$('copy-enquiry')?.addEventListener('click',async()=>{const text=$('enquiry-output').value;try{if(!navigator.clipboard)throw Error('Unavailable');await navigator.clipboard.writeText(text);flash('Message copied to clipboard');}catch(e){$('enquiry-output').focus();$('enquiry-output').select();flash('Select and copy your message');}});}
function init(){initNav();initCart();activateImages();if(page==='home')renderProductGrid('featured-grid',PRODUCTS);if(page==='collection')initCollection();if(page==='details')initDetails();if(page==='contact')initContact();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();