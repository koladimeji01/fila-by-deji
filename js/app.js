'use strict';

// Values and product photographs originate in the FÌLÀ by Deji Figma design.
// This is a frontend prototype, not a verified inventory or payment system.
// Products and prices MUST come from the FastAPI database. No hardcoded catalog.
let PRODUCTS = [];
const API_BASE = (window.FILA_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');
const AUTH_KEY = 'fila_customer_access_token_v1';
function token(){ try { return sessionStorage.getItem(AUTH_KEY) || ''; } catch { return ''; } }
function storeToken(value){ try { if(value) sessionStorage.setItem(AUTH_KEY,value); else sessionStorage.removeItem(AUTH_KEY); } catch { /* session-only fallback */ } }
function errorText(response, payload){
  if (response.status === 401) return 'Please sign in again.';
  if (typeof payload?.detail === 'string') return payload.detail;
  if (Array.isArray(payload?.detail)) return payload.detail.map(e=>e.msg||'Invalid input').join('; ');
  return `Request failed (${response.status}).`;
}
async function apiRequest(path,{method='GET',body,authorize=false}={}){
  const headers={'Accept':'application/json'};
  if(body!==undefined) headers['Content-Type']='application/json';
  if(authorize){const t=token();if(!t)throw new Error('Sign in to save a draft order.');headers.Authorization=`Bearer ${t}`;}
  const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),12000);
  try{
    const response=await fetch(`${API_BASE}${path}`,{method,headers,body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal,credentials:'omit'});
    const data=await response.json().catch(()=>({}));
    if(!response.ok){if(response.status===401&&authorize)storeToken('');throw new Error(errorText(response,data));}
    return data;
  }catch(err){if(err.name==='AbortError')throw new Error('The API took too long to respond.');if(err instanceof TypeError)throw new Error('Cannot reach FastAPI. Check that it is running on port 8000.');throw err;
  }finally{clearTimeout(timer)}
}
async function loadProducts(){
  const data=await apiRequest('/products');
  if(!Array.isArray(data)) throw new Error('The API returned an invalid catalog.');
  PRODUCTS=data.filter(p=>typeof p.id==='string'&&/^[a-z0-9_-]{1,60}$/.test(p.id)&&typeof p.name==='string'&&Number.isSafeInteger(p.price_ngn)&&p.price_ngn>=0)
    .map(p=>({id:p.id,name:p.name,category:p.category||'',description:p.description||'',price:p.price_ngn,
      // All images are shipped locally with this site: never trust a remote URL in the API response.
      image:`assets/${p.id}.jpg`,availableSizes:Array.isArray(p.available_sizes)?p.available_sizes.filter(size=>SIZES.includes(size)):[]}));
  if(!PRODUCTS.length)throw new Error('No active products were returned. Run python -m app.seed in backend/.');
}
function showCatalogError(message){
  const main=document.querySelector('main');if(!main)return;
  const el=document.createElement('div');el.className='api-alert wrap';el.setAttribute('role','alert');
  el.textContent=`Product catalog unavailable: ${message}`;
  main.prepend(el);
  document.getElementById('checkout-subtotal')?.replaceChildren(document.createTextNode('Unavailable'));
  const submit=document.getElementById('save-draft-order');if(submit)submit.disabled=true;
}
function updateAuthNavigation(){
  const controls=document.querySelector('.header-controls');if(!controls)return;
  const link=document.createElement(token()?'button':'a');link.className='header-auth-link';
  if(token()){link.type='button';link.textContent='Sign out';link.addEventListener('click',()=>{storeToken('');updateAuthNavigation();toast('Signed out of this browser session.');});}
  else{link.href='login.html';link.textContent='Sign in';}
  controls.querySelector('.header-auth-link')?.remove();
  controls.querySelector('.header-orders-link')?.remove();
  if(token()){
    const orders=document.createElement('a');orders.href='orders.html';orders.className='header-orders-link';
    orders.textContent='My drafts';controls.prepend(orders);
  }
  controls.prepend(link);
}
function safeNext(){const next=new URLSearchParams(location.search).get('next');return ['checkout.html','cart.html','index.html','collection.html','orders.html'].includes(next)?next:'checkout.html';}
async function initAuth(){
 const form=$('customer-auth-form');if(!form)return;
 const feedback=$('auth-feedback'),submit=$('auth-submit');
 const login=page==='login';
 const next=safeNext();
 const opposite=$('auth-switch');if(opposite)opposite.href=`${login?'register':'login'}.html?next=${encodeURIComponent(next)}`;
 form.addEventListener('submit',async event=>{
   event.preventDefault();if(!form.reportValidity())return;
   submit.disabled=true; feedback.textContent='Connecting securely to the local API…';feedback.className='form-feedback';
   const email=$('auth-email').value.trim();const password=$('auth-password').value;
   try{
     if(!login){await apiRequest('/auth/register',{method:'POST',body:{name:$('auth-name').value.trim(),email,password}});}
     const result=await apiRequest('/auth/login',{method:'POST',body:{email,password}});
     if(typeof result.access_token!=='string'||!result.access_token)throw new Error('No access token returned.');
     storeToken(result.access_token);form.reset();updateAuthNavigation();feedback.textContent='Signed in successfully. Redirecting…';
     location.assign(next);
   }catch(err){feedback.textContent=err.message||'Unable to sign in.';feedback.className='form-feedback auth-error';}
   finally{submit.disabled=false;}
 });
}
function initDraftCheckout(){
 const btn=$('save-draft-order'),feedback=$('draft-feedback');if(!btn||!feedback)return;
 let justSaved=false;
 btn.addEventListener('click',async()=>{
   if(justSaved)return;
   const entries=Object.entries(cart).filter(([key])=>productForCart(key));
   if(!entries.length){feedback.textContent='Your shopping bag is empty.';return;}
   if(entries.some(([,n])=>n>10)){feedback.textContent='Reduce each cap/size quantity to 10 or fewer before saving a draft.';return;}
   if(!token()){location.assign('login.html?next=checkout.html');return;}
   btn.disabled=true;feedback.textContent='Saving your draft order…';
   try{
     const body={items:entries.map(([key,n])=>({product_id:productForCart(key).product.id,size:productForCart(key).size,quantity:n}))};
     const order=await apiRequest('/orders/drafts',{method:'POST',body,authorize:true});
     feedback.textContent=`Draft saved. Reference: ${order.id}. Server-calculated subtotal: ${money(order.total_ngn)}. This is not a paid or accepted order. `;const link=document.createElement('a');link.href='orders.html';link.textContent='View my draft orders';feedback.append(link);
     feedback.className='draft-feedback draft-success';
     justSaved=true;btn.textContent='Draft saved ✓';toast('Draft order saved to your account. No payment taken.');
   }catch(err){feedback.textContent=`Could not save draft: ${err.message}`;feedback.className='draft-feedback auth-error';}
   finally{if(!justSaved)btn.disabled=false;}
 });
}

const SIZES=['32','35','39','41'];
const CART_KEY='fila_by_deji_cart_v1';
const money=(amount)=>new Intl.NumberFormat('en-NG',{style:'currency',currency:'NGN',minimumFractionDigits:0,maximumFractionDigits:0}).format(amount);
const $=(id)=>document.getElementById(id);
const page=document.body.dataset.page;
const icons={arrow:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M4 12h16m-7-7 7 7-7 7"/></svg>'};
let cart=readCart(),quantity=1,selectedSize=null,filter='all',toastId;

function productById(id){return PRODUCTS.find(p=>p.id===id)}
function productForCart(key){const [id,size,...rest]=key.split(':');if(rest.length||!SIZES.includes(size))return null;const product=productById(id);return product?{product,size}:null}
function readCart(){try{const data=JSON.parse(localStorage.getItem(CART_KEY)||'{}');if(!data||typeof data!=='object'||Array.isArray(data))return {};return Object.fromEntries(Object.entries(data).filter(([key,n])=>/^[a-z0-9_-]{1,60}:(32|35|39|41)$/.test(key)&&Number.isInteger(n)&&n>0&&n<=99))}catch{return {}}}
function saveCart(){try{localStorage.setItem(CART_KEY,JSON.stringify(cart))}catch{}updateBadges()}
function countItems(){return Object.values(cart).reduce((s,n)=>s+n,0)}
function updateBadges(){document.querySelectorAll('[data-cart-count]').forEach(el=>{const n=countItems();el.textContent=n>99?'99+':String(n)})}
function toast(text){const el=$('toast');if(!el)return;clearTimeout(toastId);el.textContent=text;el.classList.add('is-visible');toastId=setTimeout(()=>el.classList.remove('is-visible'),3700)}
function makeImage(src,alt,eager=false){const img=document.createElement('img');img.src=src;img.alt=alt;img.loading=eager?'eager':'lazy';img.decoding='async';img.addEventListener('error',()=>img.classList.add('image-unavailable'),{once:true});return img}
function productCard(p){const link=document.createElement('a');link.className='product-card';link.href=`details.html?product=${encodeURIComponent(p.id)}`;link.setAttribute('aria-label',`View ${p.name} details, ${money(p.price)}`);
 const visual=document.createElement('div');visual.className='product-card__media';visual.append(makeImage(p.image,p.name));const badge=document.createElement('span');badge.className='product-badge';badge.textContent=p.availableSizes.length?p.category:'Currently unavailable';visual.append(badge);
 const body=document.createElement('div');body.className='product-card__body';const heading=document.createElement('h3');heading.textContent=p.name;const para=document.createElement('p');para.textContent=p.description;const bottom=document.createElement('div');bottom.className='product-card__bottom';const price=document.createElement('strong');price.textContent=money(p.price);const arrow=document.createElement('span');arrow.className='product-card__arrow';arrow.innerHTML=icons.arrow;arrow.setAttribute('aria-hidden','true');bottom.append(price,arrow);body.append(heading,para,bottom);link.append(visual,body);return link}
function renderGrid(id,data){const grid=$(id);if(grid)grid.replaceChildren(...data.map(productCard))}
function initNavigation(){const toggle=$('menu-toggle'),nav=$('site-navigation');toggle?.addEventListener('click',()=>{let open=nav.classList.toggle('is-open');toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-label',open?'Close navigation':'Open navigation')});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&nav?.classList.contains('is-open')){nav.classList.remove('is-open');toggle.setAttribute('aria-expanded','false');toggle.focus()}});
 document.querySelectorAll('[data-nav]').forEach(a=>{if(a.dataset.nav===page)a.setAttribute('aria-current','page')});$('year')&&($('year').textContent=String(new Date().getFullYear()));document.querySelectorAll('img:not(.product-card__media img)').forEach(img=>img.addEventListener('error',()=>img.classList.add('image-unavailable'),{once:true}))}
function renderCollection(){const q=($('search-input')?.value||'').trim().toLowerCase();const data=PRODUCTS.filter(p=>(filter==='all'||p.id===filter)&&`${p.name} ${p.category} ${p.description}`.toLowerCase().includes(q));renderGrid('collection-products',data);$('collection-empty').hidden=data.length>0;$('results-count').textContent=`${data.length} ${data.length===1?'style':'styles'}`;document.querySelectorAll('[data-filter]').forEach(b=>{const on=b.dataset.filter===filter;b.classList.toggle('is-selected',on);b.setAttribute('aria-pressed',String(on))})}
function initCollection(){$('search-input')?.addEventListener('input',renderCollection);document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;renderCollection()}));$('clear-filters')?.addEventListener('click',()=>{filter='all';$('search-input').value='';renderCollection()});renderCollection()}
function initDetails(){const id=new URLSearchParams(location.search).get('product');const product=productById(id)||PRODUCTS[2];$('product-title').textContent=product.name;$('product-description').textContent=product.description;$('product-price').textContent=money(product.price);$('product-category').textContent=`${product.category.toUpperCase()} COLLECTION`;$('crumb-product').textContent=product.name;document.title=`${product.name} | FÌLÀ by Deji`;const photo=$('product-photo');photo.src=product.image;photo.alt=product.name;
 const options=SIZES.map(size=>{const btn=document.createElement('button');btn.type='button';btn.className='size-option';btn.textContent=size;btn.disabled=!product.availableSizes.includes(size);btn.setAttribute('aria-pressed','false');btn.setAttribute('aria-label',`Choose cap size ${size}${btn.disabled?' — out of stock':''}`);btn.addEventListener('click',()=>{selectedSize=size;$('selected-size').textContent=`Size ${size} selected`;$('size-error').hidden=true;document.querySelectorAll('.size-option').forEach(b=>b.setAttribute('aria-pressed',String(b===btn)))});return btn});$('size-options').replaceChildren(...options);
 if(!product.availableSizes.length){$('selected-size').textContent='This cap is currently out of stock.';$('add-to-bag').disabled=true;}
 const updateQty=delta=>{quantity=Math.min(10,Math.max(1,quantity+delta));$('quantity-display').textContent=String(quantity)};$('minus-quantity').addEventListener('click',()=>updateQty(-1));$('plus-quantity').addEventListener('click',()=>updateQty(1));$('add-to-bag').addEventListener('click',()=>{if(!selectedSize){$('size-error').hidden=false;options[0].focus();return}const key=`${product.id}:${selectedSize}`;cart[key]=Math.min(10,(cart[key]||0)+quantity);saveCart();toast(`${quantity} × ${product.name} added to your bag`);$('add-to-bag').textContent='Added to bag ✓';setTimeout(()=>{const btn=$('add-to-bag');if(btn)btn.innerHTML='Add to bag'},1700)});renderGrid('related-products',PRODUCTS.filter(p=>p.id!==product.id))}
function updateCart(key,delta){const num=(cart[key]||0)+delta;if(num<=0)delete cart[key];else cart[key]=Math.min(num,10);saveCart();renderBag();renderCheckout()}
function renderBag(){const list=$('bag-items');if(!list)return;list.replaceChildren();const items=Object.entries(cart);$('bag-items-count').textContent=`${countItems()} ${countItems()===1?'item':'items'}`;$('bag-empty').hidden=items.length>0;
 for(const [key,qty] of items){const selection=productForCart(key);if(!selection)continue;const {product:p,size}=selection;const row=document.createElement('article');row.className='bag-line';const img=makeImage(p.image,p.name);const main=document.createElement('div');const top=document.createElement('div');top.className='bag-line__top';const info=document.createElement('div');const h=document.createElement('h3');h.textContent=p.name;const sizeP=document.createElement('p');sizeP.textContent=`Size ${size} · ${p.category}`;info.append(h,sizeP);const price=document.createElement('strong');price.className='bag-line__price';price.textContent=money(p.price*qty);top.append(info,price);
 const bottom=document.createElement('div');bottom.className='bag-line__bottom';const controls=document.createElement('div');controls.className='mini-quantity';const minus=document.createElement('button');minus.type='button';minus.textContent='−';minus.setAttribute('aria-label',`Remove one ${p.name} size ${size}`);minus.addEventListener('click',()=>updateCart(key,-1));const number=document.createElement('span');number.textContent=qty;const plus=document.createElement('button');plus.type='button';plus.textContent='+';plus.setAttribute('aria-label',`Add one ${p.name} size ${size}`);plus.addEventListener('click',()=>updateCart(key,1));controls.append(minus,number,plus);const remove=document.createElement('button');remove.className='remove-line';remove.type='button';remove.textContent='Remove';remove.addEventListener('click',()=>{delete cart[key];saveCart();renderBag()});bottom.append(controls,remove);main.append(top,bottom);row.append(img,main);list.append(row)}
 const total=Object.entries(cart).reduce((sum,[key,q])=>sum+(productForCart(key)?.product.price||0)*q,0);$('summary-subtotal').textContent=money(total);$('summary-total').textContent=money(total);const checkout=$('checkout-link');if(checkout){checkout.setAttribute('aria-disabled',String(items.length===0));checkout.onclick=e=>{if(!countItems())e.preventDefault()}}}
function renderCheckout(){const node=$('checkout-items');if(!node)return;node.replaceChildren();let total=0;for(const [key,qty] of Object.entries(cart)){const sel=productForCart(key);if(!sel)continue;total+=sel.product.price*qty;const line=document.createElement('div');line.className='checkout-line';const text=document.createElement('span');text.textContent=`${sel.product.name} × ${qty}`;const small=document.createElement('small');small.textContent=`Size ${sel.size}`;text.append(small);const price=document.createElement('strong');price.textContent=money(sel.product.price*qty);line.append(text,price);node.append(line)}if(!node.childElementCount){const empty=document.createElement('p');empty.textContent='No caps selected yet.';node.append(empty)}$('checkout-subtotal').textContent=money(total)}
async function copyText(text){if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);return}const el=document.createElement('textarea');el.value=text;el.style.position='fixed';el.style.opacity='0';document.body.append(el);el.select();const success=document.execCommand('copy');el.remove();if(!success)throw Error('clipboard unavailable')}
function renderOrderItem(item){
 const li=document.createElement('li');li.className='history-line';
 const title=document.createElement('span');title.textContent=`${item.product_name} · Size ${item.size} · Qty ${item.quantity}`;
 const price=document.createElement('strong');price.textContent=money(item.line_total_ngn);
 li.append(title,price);return li;
}
async function initOrders(){
 const list=$('orders-list'),feedback=$('orders-feedback'),more=$('load-more-orders');
 if(!list||!feedback||!more)return;
 if(!token()){location.assign('login.html?next=orders.html');return;}
 let offset=0, loading=false;
 const load=async()=>{
   if(loading)return;loading=true;more.disabled=true;feedback.textContent='Loading your draft history…';
   try{
     const records=await apiRequest(`/orders?limit=20&offset=${offset}`,{authorize:true});
     if(!Array.isArray(records))throw new Error('Unexpected order history response.');
     if(offset===0&&records.length===0){feedback.textContent='You have no draft orders yet.';}
     else feedback.textContent='Your saved draft orders. No payments have been collected.';
     for(const order of records){
       const card=document.createElement('article');card.className='history-card';
       const heading=document.createElement('div');heading.className='history-card__heading';
       const name=document.createElement('h2');name.textContent=`Draft ${String(order.id).slice(0,8).toUpperCase()}`;
       const date=document.createElement('time');const d=new Date(order.created_at);date.textContent=Number.isNaN(d.getTime())?'':d.toLocaleString('en-NG',{dateStyle:'medium',timeStyle:'short'});
       heading.append(name,date);
       const ref=document.createElement('p');ref.className='history-ref';ref.textContent=`Reference: ${order.id}`;
       const items=document.createElement('ul');items.className='history-items';
       for(const item of order.items||[])items.append(renderOrderItem(item));
       const foot=document.createElement('div');foot.className='history-card__foot';
       const label=document.createElement('span');label.textContent='Draft only · no stock reserved';
       const total=document.createElement('strong');total.textContent=money(order.total_ngn);foot.append(label,total);
       card.append(heading,ref,items,foot);list.append(card);
     }
     offset+=records.length;more.hidden=records.length<20;
   }catch(err){
     feedback.textContent=`Could not load orders: ${err.message}`;
     if(!token()){location.assign('login.html?next=orders.html');return;}
     more.hidden=false;
   }finally{loading=false;more.disabled=false;}
 };
 more.addEventListener('click',load);await load();
}
function initContact(){const form=$('enquiry-form');form?.addEventListener('submit',async event=>{event.preventDefault();if(!form.reportValidity())return;const name=$('enquiry-name').value.trim(),topic=$('enquiry-subject').value,msg=$('enquiry-message').value.trim();if(!name||!msg)return;const text=`Hello FÌLÀ by Deji,\n\nMy name is ${name}.\nSubject: ${topic}\n\n${msg}`;try{await copyText(text);$('enquiry-feedback').textContent='Your enquiry was copied. Paste it into your preferred messaging app to send.';toast('Enquiry copied — not sent.')}catch{$('enquiry-feedback').textContent='Could not copy automatically. Please select and copy your message above.'}})}
async function init(){
  initNavigation();updateBadges();updateAuthNavigation();
  if(['home','collection','details','cart','checkout'].includes(page)){
    try{await loadProducts();}
    catch(err){showCatalogError(err.message);return;}
  }
  if(page==='home')renderGrid('home-products',PRODUCTS);
  if(page==='collection')initCollection();
  if(page==='details')initDetails();
  if(page==='cart')renderBag();
  if(page==='checkout'){renderCheckout();initDraftCheckout();}
  if(page==='contact')initContact();
  if(page==='orders')await initOrders();
  if(page==='login'||page==='register')initAuth();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
