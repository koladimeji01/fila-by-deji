'use strict';

// Values and product photographs originate in the FÌLÀ by Deji Figma design.
// This is a frontend prototype, not a verified inventory or payment system.
// Products and prices MUST come from the FastAPI database. No hardcoded catalog.
let PRODUCTS = [];
// The unchanged Ubuntu development site uses local FastAPI; HTTPS storefronts use Render.
const IS_LOCAL_PREVIEW = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
const API_BASE = (window.FILA_API_BASE_URL ||
  (IS_LOCAL_PREVIEW ? 'http://127.0.0.1:8000/api/v1' : 'https://fila-by-deji-api.onrender.com/api/v1')
).replace(/\/$/, '');
const AUTH_KEY = 'fila_customer_access_token_v1';
function token(){ try { return sessionStorage.getItem(AUTH_KEY) || ''; } catch { return ''; } }
function storeToken(value){ try { if(value) sessionStorage.setItem(AUTH_KEY,value); else sessionStorage.removeItem(AUTH_KEY); } catch { /* session-only fallback */ } }
function errorText(response, payload){
  // Return actionable authentication errors, including incorrect login credentials.
  if (response.status === 401 && !payload?.detail) return 'Authentication required. Please sign in again.';
  if (typeof payload?.detail === 'string') return payload.detail;
  if (Array.isArray(payload?.detail)) return payload.detail.map(e=>e.msg||'Invalid input').join('; ');
  return `Request failed (${response.status}).`;
}
async function apiRequest(path,{method='GET',body,authorize=false}={}){
  const headers={'Accept':'application/json'};
  if(body!==undefined) headers['Content-Type']='application/json';
  if(authorize){const t=token();if(!t)throw new Error('Sign in to save your selection for later.');headers.Authorization=`Bearer ${t}`;}
  // Render's free instances can take time to wake up. Only retry safe GETs;
  // never replay registration, login, saved-selection, reservation or inventory writes.
  const attempts=method==='GET'?2:1;
  for(let attempt=0;attempt<attempts;attempt++){
    const controller=new AbortController();
    const timeoutMs=method==='GET'&&!IS_LOCAL_PREVIEW?(attempt===0?65000:20000):15000;
    const timer=setTimeout(()=>controller.abort(),timeoutMs);
    try{
      const response=await fetch(`${API_BASE}${path}`,{
        method,headers,body:body===undefined?undefined:JSON.stringify(body),
        signal:controller.signal,credentials:'omit'
      });
      const data=await response.json().catch(()=>({}));
      if(!response.ok){
        if(method==='GET'&&response.status>=500&&attempt+1<attempts){
          await new Promise(resolve=>setTimeout(resolve,1500));
          continue;
        }
        if(response.status===401&&authorize){storeToken('');updateAuthNavigation();}
        throw new Error(errorText(response,data));
      }
      return data;
    }catch(err){
      const transient=err?.name==='AbortError'||err instanceof TypeError;
      if(method==='GET'&&transient&&attempt+1<attempts){
        await new Promise(resolve=>setTimeout(resolve,1500));
        continue;
      }
      if(err?.name==='AbortError')throw new Error('The FÌLÀ API is taking longer than expected to respond. Please try again.');
      if(err instanceof TypeError)throw new Error('Cannot reach the FÌLÀ API. Check your connection and try again.');
      throw err;
    }finally{clearTimeout(timer);}
  }
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
  // The home page has an overlay navigation; messages before the hero obscure it.
  // Show catalog problems next to the actual product grid instead.
  const grid=page==='home'?document.getElementById('home-products'):
             page==='collection'?document.getElementById('collection-products'):null;
  const el=document.createElement('div');
  el.className=grid?'api-alert':'api-alert wrap';
  el.setAttribute('role','alert');
  el.textContent=`Product catalog unavailable: ${message}`;
  const retry=document.createElement('button');
  retry.type='button';retry.className='button button--dark';
  retry.textContent='Try again';
  retry.addEventListener('click',()=>window.location.reload());
  el.append(document.createElement('br'),retry);
  if(grid)grid.before(el);else main.prepend(el);
  document.getElementById('checkout-subtotal')?.replaceChildren(document.createTextNode('Unavailable'));
  const submit=document.getElementById('save-draft-order');if(submit)submit.disabled=true;
}
function updateAuthNavigation(){
  const link=document.querySelector('.account-link');
  if(!link)return;
  const signedIn=Boolean(token());
  link.href=signedIn?'profile.html':'login.html';
  link.setAttribute('aria-label',signedIn?'View your account profile':'Sign in to your account');
  const label=link.querySelector('.account-label');
  if(label)label.textContent=signedIn?'Profile':'Sign in';
  if(page==='profile'&&signedIn)link.setAttribute('aria-current','page');
  else link.removeAttribute('aria-current');
}
function safeNext(){const next=new URLSearchParams(location.search).get('next');return ['checkout.html','cart.html','index.html','collection.html','orders.html','profile.html'].includes(next)?next:'index.html';}
async function initAuth(){
 const form=$('customer-auth-form');if(!form)return;
 const feedback=$('auth-feedback'),submit=$('auth-submit');
 const login=page==='login';
 const next=safeNext();
 const opposite=$('auth-switch');if(opposite)opposite.href=`${login?'register':'login'}.html?next=${encodeURIComponent(next)}`;
 form.addEventListener('submit',async event=>{
   event.preventDefault();if(!form.reportValidity())return;
   submit.disabled=true; feedback.textContent='Signing you in…';feedback.className='form-feedback';
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
   if(!entries.length){feedback.textContent='Your shopping bag is empty.';return;}if(entries.length!==Object.keys(cart).length){feedback.textContent='Some saved caps are no longer available. Remove them from your bag before continuing.';return;}if(entries.some(([key])=>!productForCart(key).product.availableSizes.includes(productForCart(key).size))){feedback.textContent='A cap size in your bag is unavailable. Return to your bag and remove it.';return;}
   if(entries.some(([,n])=>n>10)){feedback.textContent='Reduce each cap/size quantity to 10 or fewer before saving for later.';return;}
   if(!token()){location.assign('login.html?next=checkout.html');return;}
   btn.disabled=true;feedback.textContent='Saving your selection for later…';
   try{
     const body={items:entries.map(([key,n])=>({product_id:productForCart(key).product.id,size:productForCart(key).size,quantity:n}))};
     const order=await apiRequest('/orders/drafts',{method:'POST',body,authorize:true});
     feedback.textContent=`Saved for later. Reference: ${order.id}. Server-calculated subtotal: ${money(order.total_ngn)}. No payment has been taken and stock is not reserved. `;const link=document.createElement('a');link.href='orders.html';link.textContent='View saved selections';feedback.append(link);
     feedback.className='draft-feedback draft-success';
     justSaved=true;btn.textContent='Saved for later ✓';toast('Selection saved to your account. No payment taken.');
   }catch(err){feedback.textContent=`Could not save selection: ${err.message}`;feedback.className='draft-feedback auth-error';}
   finally{if(!justSaved)btn.disabled=false;}
 });
}

const SIZES=['32','35','39','41'];
const CART_KEY='fila_by_deji_cart_v1';
const SAVED_KEY='fila_by_deji_saved_for_later_v1';
const money=(amount)=>new Intl.NumberFormat('en-NG',{style:'currency',currency:'NGN',minimumFractionDigits:0,maximumFractionDigits:0}).format(amount);
const $=(id)=>document.getElementById(id);
const page=document.body.dataset.page;
const icons={arrow:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M4 12h16m-7-7 7 7-7 7"/></svg>'};
let cart=readCart(),quantity=1,selectedSize=null,filter='all',toastId;

function productById(id){return PRODUCTS.find(p=>p.id===id)}
function productForCart(key){const [id,size,...rest]=key.split(':');if(rest.length||!SIZES.includes(size))return null;const product=productById(id);return product?{product,size}:null}
function readCart(){try{const data=JSON.parse(localStorage.getItem(CART_KEY)||'{}');if(!data||typeof data!=='object'||Array.isArray(data))return {};return Object.fromEntries(Object.entries(data).filter(([key,n])=>/^[a-z0-9_-]{1,60}:(32|35|39|41)$/.test(key)&&Number.isInteger(n)&&n>0&&n<=99))}catch{return {}}}
function saveCart(){try{localStorage.setItem(CART_KEY,JSON.stringify(cart))}catch{}updateBadges()}
function readSaved(){try{
  const data=JSON.parse(localStorage.getItem(SAVED_KEY)||'{}');
  if(!data||typeof data!=='object'||Array.isArray(data))return {};
  return Object.fromEntries(Object.entries(data).filter(([key,n])=>/^[a-z0-9_-]{1,60}:(32|35|39|41)$/.test(key)&&Number.isInteger(n)&&n>0&&n<=99));
}catch{return {}}}
let savedForLater=readSaved();
function saveSaved(){try{localStorage.setItem(SAVED_KEY,JSON.stringify(savedForLater))}catch{}}
function saveBagItemForLater(key){
  const amount=cart[key];if(!amount)return;
  savedForLater[key]=Math.min(99,(savedForLater[key]||0)+amount);
  delete cart[key];saveSaved();saveCart();renderBag();
  toast('Saved for later on this device. No stock reserved.');
}
function moveSavedItemToBag(key){
  const amount=savedForLater[key];if(!amount)return;
  const sel=productForCart(key);
  if(!sel||!sel.product.availableSizes.includes(sel.size)){toast('This size is unavailable. Keep it saved for later.');return;}
  const space=10-(cart[key]||0);
  if(space<=0){toast('Your bag already has the maximum quantity for this size.');return;}
  const moved=Math.min(amount,space);
  cart[key]=(cart[key]||0)+moved;
  if(amount===moved)delete savedForLater[key];else savedForLater[key]-=moved;
  saveSaved();saveCart();renderBag();
  toast('Moved into your shopping bag.');
}
function renderSavedForLater(){
  const target=$('saved-local-items');if(!target)return;
  target.replaceChildren();
  const entries=Object.entries(savedForLater);
  const count=$('saved-local-count');if(count)count.textContent=`${entries.length} ${entries.length===1?'style':'styles'}`;
  const empty=$('saved-local-empty');if(empty)empty.hidden=entries.length>0;
  for(const [key,qty] of entries){
    const sel=productForCart(key);const item=document.createElement('article');item.className='saved-local-card';
    if(sel)item.append(makeImage(sel.product.image,sel.product.name));
    const content=document.createElement('div');content.className='saved-local-card__content';
    const title=document.createElement('h3');title.textContent=sel?.product.name||'Previously saved cap';
    const subtitle=document.createElement('p');subtitle.textContent=sel?`Size ${sel.size} · Qty ${qty} · ${money(sel.product.price*qty)}`:`Qty ${qty} · Not currently in the collection`;
    const actions=document.createElement('div');actions.className='saved-local-actions';
    if(sel){
      const move=document.createElement('button');move.type='button';move.className='button button--dark';move.textContent='Move to bag';
      move.disabled=!sel.product.availableSizes.includes(sel.size);
      move.addEventListener('click',()=>moveSavedItemToBag(key));actions.append(move);
    }
    const remove=document.createElement('button');remove.type='button';remove.className='remove-line';remove.textContent='Remove';
    remove.addEventListener('click',()=>{delete savedForLater[key];saveSaved();renderSavedForLater()});actions.append(remove);
    content.append(title,subtitle,actions);item.append(content);target.append(item);
  }
}
function countItems(){return Object.values(cart).reduce((s,n)=>s+n,0)}
function updateBadges(){document.querySelectorAll('[data-cart-count]').forEach(el=>{const n=countItems();el.textContent=n>99?'99+':String(n)})}
function toast(text){const el=$('toast');if(!el)return;clearTimeout(toastId);el.textContent=text;el.classList.add('is-visible');toastId=setTimeout(()=>el.classList.remove('is-visible'),3700)}
function makeImage(src,alt,eager=false){const img=document.createElement('img');img.src=src;img.alt=alt;img.loading=eager?'eager':'lazy';img.decoding='async';img.addEventListener('error',()=>img.classList.add('image-unavailable'),{once:true});return img}
function productCard(p){const link=document.createElement('a');link.className='product-card';link.href=`details.html?product=${encodeURIComponent(p.id)}`;link.setAttribute('aria-label',`View ${p.name} details, ${money(p.price)}`);
 const visual=document.createElement('div');visual.className='product-card__media';visual.append(makeImage(p.image,p.name));const badge=document.createElement('span');badge.className='product-badge';badge.textContent=p.availableSizes.length?p.category:'Currently unavailable';visual.append(badge);
 const body=document.createElement('div');body.className='product-card__body';const heading=document.createElement('h3');heading.textContent=p.name;const para=document.createElement('p');para.textContent=p.description;const bottom=document.createElement('div');bottom.className='product-card__bottom';const price=document.createElement('strong');price.textContent=money(p.price);const arrow=document.createElement('span');arrow.className='product-card__arrow';arrow.innerHTML=icons.arrow;arrow.setAttribute('aria-hidden','true');bottom.append(price,arrow);body.append(heading,para,bottom);link.append(visual,body);return link}
function renderGrid(id,data){const grid=$(id);if(grid)grid.replaceChildren(...data.map(productCard))}
async function initProfile(){
  if(!token()){location.replace('login.html?next=profile.html');return;}
  const signout=$('profile-signout');
  signout?.addEventListener('click',()=>{
    storeToken('');updateAuthNavigation();
    location.replace('login.html');
  });
  const status=$('profile-status');
  try{
    const user=await apiRequest('/auth/me',{authorize:true});
    if(!user||typeof user.name!=='string'||typeof user.email!=='string')throw new Error('Account information is unavailable.');
    $('profile-name').textContent=user.name;
    $('profile-email').textContent=user.email;
    $('profile-avatar').textContent=(user.name.trim().charAt(0)||'F').toUpperCase();
    $('profile-title').textContent=user.name;
    $('profile-greeting').textContent='Your details, your favourites, all in one place.';
    status.textContent='Your account information is up to date.';
  }catch(err){
    if(!token()){location.replace('login.html?next=profile.html');return;}
    status.textContent=`Unable to load profile: ${err.message}`;
    status.classList.add('auth-error');
  }
}
function initNavigation(){const toggle=$('menu-toggle'),nav=$('site-navigation');toggle?.addEventListener('click',()=>{let open=nav.classList.toggle('is-open');toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-label',open?'Close navigation':'Open navigation')});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&nav?.classList.contains('is-open')){nav.classList.remove('is-open');toggle.setAttribute('aria-expanded','false');toggle.focus()}});
 document.querySelectorAll('[data-nav]').forEach(a=>{if(a.dataset.nav===page)a.setAttribute('aria-current','page')});$('year')&&($('year').textContent=String(new Date().getFullYear()));document.querySelectorAll('img:not(.product-card__media img)').forEach(img=>img.addEventListener('error',()=>img.classList.add('image-unavailable'),{once:true}))}
function renderCollection(){const q=($('search-input')?.value||'').trim().toLowerCase();const data=PRODUCTS.filter(p=>(filter==='all'||p.id===filter)&&`${p.name} ${p.category} ${p.description}`.toLowerCase().includes(q));renderGrid('collection-products',data);$('collection-empty').hidden=data.length>0;$('results-count').textContent=`${data.length} ${data.length===1?'style':'styles'}`;document.querySelectorAll('[data-filter]').forEach(b=>{const on=b.dataset.filter===filter;b.classList.toggle('is-selected',on);b.setAttribute('aria-pressed',String(on))})}
function initCollection(){$('search-input')?.addEventListener('input',renderCollection);document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;renderCollection()}));$('clear-filters')?.addEventListener('click',()=>{filter='all';$('search-input').value='';renderCollection()});renderCollection()}
function initDetails(){const id=new URLSearchParams(location.search).get('product');const product=productById(id);if(!product){showCatalogError('This cap could not be found. Please return to the collection.');document.querySelector('.product-layout')?.remove();document.getElementById('related-products')?.replaceChildren();return;}$('product-title').textContent=product.name;$('product-description').textContent=product.description;$('product-price').textContent=money(product.price);$('product-category').textContent=`${product.category.toUpperCase()} COLLECTION`;$('crumb-product').textContent=product.name;document.title=`${product.name} | FÌLÀ by Deji`;const photo=$('product-photo');photo.src=product.image;photo.alt=product.name;
 const options=SIZES.map(size=>{const btn=document.createElement('button');btn.type='button';btn.className='size-option';btn.textContent=size;btn.disabled=!product.availableSizes.includes(size);btn.setAttribute('aria-pressed','false');btn.setAttribute('aria-label',`Choose cap size ${size}${btn.disabled?' — out of stock':''}`);btn.addEventListener('click',()=>{selectedSize=size;$('selected-size').textContent=`Size ${size} selected`;$('size-error').hidden=true;document.querySelectorAll('.size-option').forEach(b=>b.setAttribute('aria-pressed',String(b===btn)))});return btn});$('size-options').replaceChildren(...options);
 if(!product.availableSizes.length){$('selected-size').textContent='This cap is currently out of stock.';$('add-to-bag').disabled=true;}
 const updateQty=delta=>{quantity=Math.min(10,Math.max(1,quantity+delta));$('quantity-display').textContent=String(quantity)};$('minus-quantity').addEventListener('click',()=>updateQty(-1));$('plus-quantity').addEventListener('click',()=>updateQty(1));$('add-to-bag').addEventListener('click',()=>{if(!selectedSize){$('size-error').hidden=false;options.find(option=>!option.disabled)?.focus();return}const key=`${product.id}:${selectedSize}`;const previous=cart[key]||0;cart[key]=Math.min(10,previous+quantity);saveCart();const added=cart[key]-previous;toast(added?`${added} × ${product.name} added to your bag`:'Maximum quantity of 10 reached for this size.');$('add-to-bag').textContent='Added to bag ✓';setTimeout(()=>{const btn=$('add-to-bag');if(btn)btn.innerHTML='Add to bag'},1700)});renderGrid('related-products',PRODUCTS.filter(p=>p.id!==product.id))}
function updateCart(key,delta){const num=(cart[key]||0)+delta;if(num<=0)delete cart[key];else cart[key]=Math.min(num,10);saveCart();renderBag();renderCheckout()}
function renderBag(){const list=$('bag-items');if(!list)return;list.replaceChildren();const items=Object.entries(cart);const visibleCount=items.reduce((sum,[,qty])=>sum+qty,0);$('bag-items-count').textContent=`${visibleCount} ${visibleCount===1?'item':'items'}`;$('bag-empty').hidden=items.length>0;
 for(const [key,qty] of items){const selection=productForCart(key);if(!selection){const row=document.createElement('article');row.className='bag-line';const label=document.createElement('div');label.textContent='A previously saved cap is no longer in the collection.';const remove=document.createElement('button');remove.className='remove-line';remove.type='button';remove.textContent='Remove unavailable item';remove.addEventListener('click',()=>{delete cart[key];saveCart();renderBag();});row.append(label,remove);list.append(row);continue;}const {product:p,size}=selection;const row=document.createElement('article');row.className='bag-line';const img=makeImage(p.image,p.name);const main=document.createElement('div');const top=document.createElement('div');top.className='bag-line__top';const info=document.createElement('div');const h=document.createElement('h3');h.textContent=p.name;const sizeP=document.createElement('p');sizeP.textContent=`Size ${size} · ${p.category}`;info.append(h,sizeP);const price=document.createElement('strong');price.className='bag-line__price';price.textContent=money(p.price*qty);top.append(info,price);
 const bottom=document.createElement('div');bottom.className='bag-line__bottom';const controls=document.createElement('div');controls.className='mini-quantity';const minus=document.createElement('button');minus.type='button';minus.textContent='−';minus.setAttribute('aria-label',`Remove one ${p.name} size ${size}`);minus.addEventListener('click',()=>updateCart(key,-1));const number=document.createElement('span');number.textContent=qty;const plus=document.createElement('button');plus.type='button';plus.textContent='+';plus.setAttribute('aria-label',`Add one ${p.name} size ${size}`);plus.addEventListener('click',()=>updateCart(key,1));controls.append(minus,number,plus);const remove=document.createElement('button');remove.className='remove-line';remove.type='button';remove.textContent='Remove';remove.addEventListener('click',()=>{delete cart[key];saveCart();renderBag()});const saveLater=document.createElement('button');saveLater.className='save-later-action';saveLater.type='button';saveLater.textContent='Save for later';saveLater.addEventListener('click',()=>saveBagItemForLater(key));bottom.append(controls,saveLater,remove);main.append(top,bottom);row.append(img,main);list.append(row)}
 const total=Object.entries(cart).reduce((sum,[key,q])=>sum+(productForCart(key)?.product.price||0)*q,0);$('summary-subtotal').textContent=money(total);$('summary-total').textContent=money(total);const checkout=$('checkout-link');if(checkout){const unavailable=items.some(([key,n])=>{const item=productForCart(key);return n>10||!item||!item.product.availableSizes.includes(item.size)});checkout.setAttribute('aria-disabled',String(items.length===0||unavailable));checkout.onclick=e=>{if(!items.length||unavailable){e.preventDefault();toast('Remove unavailable caps or sizes before checking out.')}};const notice=$('bag-availability-notice');if(notice){notice.hidden=!unavailable;notice.textContent=unavailable?'Some bag items are unavailable or exceed the 10-per-size limit. Remove or reduce them to continue.':'';}}
 renderSavedForLater();}
function renderCheckout(){const node=$('checkout-items');if(!node)return;node.replaceChildren();let total=0;for(const [key,qty] of Object.entries(cart)){const sel=productForCart(key);if(!sel)continue;total+=sel.product.price*qty;const line=document.createElement('div');line.className='checkout-line';const text=document.createElement('span');text.textContent=`${sel.product.name} × ${qty}`;const small=document.createElement('small');small.textContent=`Size ${sel.size}`;text.append(small);const price=document.createElement('strong');price.textContent=money(sel.product.price*qty);line.append(text,price);node.append(line)}if(!node.childElementCount){const empty=document.createElement('p');empty.textContent='No caps selected yet.';node.append(empty)}$('checkout-subtotal').textContent=money(total)}
function renderOrderItem(item){
 const li=document.createElement('li');li.className='history-line';
 const title=document.createElement('span');title.textContent=`${item.product_name} · Size ${item.size} · Qty ${item.quantity}`;
 const price=document.createElement('strong');price.textContent=money(item.line_total_ngn);
 li.append(title,price);return li;
}
// Customer draft/hold management. Only API-calculated prices and states are authoritative.
async function initOrders(){
 const list=$('orders-list'),feedback=$('orders-feedback'),more=$('load-more-orders');
 if(!list||!feedback||!more)return;
 if(!token()){location.assign('login.html?next=orders.html');return;}
 let offset=0,loading=false;
 const labelFor=(order)=>{
   if(order.status==='reserved'){
     let timestamp=order.reserved_until||'';
     // SQLite can return timezone-naive UTC timestamps; interpret as UTC.
     if(timestamp&&!/(Z|[+-]\d\d:?\d\d)$/.test(timestamp))timestamp+='Z';
     const date=new Date(timestamp);
     return `Stock temporarily held${Number.isNaN(date.getTime())?'':` until ${date.toLocaleString('en-NG',{dateStyle:'medium',timeStyle:'short'})}`} · NOT paid`;
   }
   return {draft:'Saved for later · stock not reserved',expired:'Hold expired · stock released',cancelled:'Cancelled'}[order.status]||'Not a paid order';
 };
 const updateOrder=async(order,action,button)=>{
   if(action==='reserve'&&!window.confirm('Temporarily hold this selection for 15 minutes? No payment will be taken.'))return;
   button.disabled=true;
   feedback.textContent=action==='reserve'?'Checking available stock…':'Cancelling your selection…';
   try{
     const changed=await apiRequest(`/orders/${encodeURIComponent(order.id)}/${action}`,{method:'POST',authorize:true});
     list.replaceChildren();offset=0;await load();
     feedback.textContent=action==='reserve'?'Stock held for 15 minutes. This is not an accepted or paid order.':'Selection cancelled. Reserved stock has been released.';
     toast(`Order ${changed.status}. No payment taken.`);
   }catch(err){feedback.textContent=`Unable to ${action}: ${err.message}`;button.disabled=false;}
 };
 const load=async()=>{
   if(loading)return;loading=true;more.disabled=true;feedback.textContent='Loading saved selections…';
   try{
     const records=await apiRequest(`/orders?limit=20&offset=${offset}`,{authorize:true});
     if(!Array.isArray(records))throw new Error('Unexpected order history response.');
     feedback.textContent=offset===0&&records.length===0?'You have no saved selections yet.':'Saved selections and temporary holds only. No payments have been taken.';
     for(const order of records){
       const card=document.createElement('article');card.className='history-card';
       const heading=document.createElement('div');heading.className='history-card__heading';
       const name=document.createElement('h2');name.textContent=`Selection ${String(order.id).slice(0,8).toUpperCase()}`;
       const date=document.createElement('time');const d=new Date(order.created_at);
       date.textContent=Number.isNaN(d.getTime())?'':d.toLocaleString('en-NG',{dateStyle:'medium',timeStyle:'short'});
       heading.append(name,date);
       const ref=document.createElement('p');ref.className='history-ref';ref.textContent=`Reference: ${order.id}`;
       const items=document.createElement('ul');items.className='history-items';
       for(const item of order.items||[])items.append(renderOrderItem(item));
       const foot=document.createElement('div');foot.className='history-card__foot';
       const label=document.createElement('span');label.textContent=labelFor(order);
       const total=document.createElement('strong');total.textContent=money(order.total_ngn);foot.append(label,total);
       card.append(heading,ref,items,foot);
       if(['draft','reserved'].includes(order.status)){
         const actions=document.createElement('div');actions.className='history-actions';
         if(order.status==='draft'){
           const hold=document.createElement('button');hold.type='button';hold.className='button button--gold';hold.textContent='Hold stock for 15 minutes';
           hold.addEventListener('click',()=>updateOrder(order,'reserve',hold));actions.append(hold);
         }
         const cancel=document.createElement('button');cancel.type='button';cancel.className='button button--dark';cancel.textContent='Cancel selection';
         cancel.addEventListener('click',()=>updateOrder(order,'cancel',cancel));actions.append(cancel);card.append(actions);
       }
       list.append(card);
     }
     offset+=records.length;more.hidden=records.length<20;
   }catch(err){feedback.textContent=`Could not load selections: ${err.message}`;more.hidden=false;
     if(!token()){location.assign('login.html?next=orders.html');return;}
   }finally{loading=false;more.disabled=false;}
 };
 more.addEventListener('click',load);await load();
}
function initContact(){
  const form=$('enquiry-form');
  form?.addEventListener('submit',event=>{
    event.preventDefault();
    if(!form.reportValidity())return;
    const name=$('enquiry-name').value.trim();
    const topic=$('enquiry-subject').value;
    const message=$('enquiry-message').value.trim();
    const feedback=$('enquiry-feedback');
    if(!name||!message){feedback.textContent='Please enter your name and message.';return;}
    const text=`Hello FÌLÀ by Deji,\n\nMy name is ${name}.\nSubject: ${topic}\n\n${message}`;
    if(event.submitter?.value==='email'){
      const subject=encodeURIComponent(`FÌLÀ by Deji — ${topic}`);
      const body=encodeURIComponent(text);
      feedback.textContent='Opening your email app. Review the message and press Send there.';
      window.location.href=`mailto:filabydeji@gmail.com?subject=${subject}&body=${body}`;
    }else{
      feedback.textContent='Opening WhatsApp. Review your message and tap Send in WhatsApp.';
      window.location.assign(`https://wa.me/2348067422794?text=${encodeURIComponent(text)}`);
    }
  });
}
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
  if(page==='profile')await initProfile();
  if(page==='login'||page==='register')initAuth();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
