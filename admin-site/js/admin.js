'use strict';
// Independently deployed admin portal; no customer storefront scripts or secrets.
const API_BASE='https://fila-by-deji-api.onrender.com/api/v1';
const ADMIN_AUTH_KEY='fila_admin_access_token_v1';
function token(){try{return sessionStorage.getItem(ADMIN_AUTH_KEY)||''}catch{return ''}}
function storeToken(v){try{if(v)sessionStorage.setItem(ADMIN_AUTH_KEY,v);else sessionStorage.removeItem(ADMIN_AUTH_KEY)}catch{}}
async function apiRequest(path,{method='GET',body,authorize=false}={}){
 const headers={'Accept':'application/json'};
 if(body!==undefined)headers['Content-Type']='application/json';
 if(authorize){const t=token();if(!t)throw new Error('Staff sign-in required');headers.Authorization='Bearer '+t;}
 const response=await fetch(API_BASE+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'omit',cache:'no-store'});
 const payload=await response.json().catch(()=>({}));
 if(!response.ok){
   if(response.status===401&&authorize)storeToken('');
   const message=typeof payload?.detail==='string'?payload.detail:(response.status===403?'Administrator privileges required':'Request failed ('+response.status+')');
   throw new Error(message);
 }
 return payload;
}
/* FÌLÀ business operations. The backend enforces admin privileges on every
   endpoint. Nothing private is embedded in the static HTML or JavaScript. */
(() => {
  const $a=id=>document.getElementById(id);
  const ngn=value=>new Intl.NumberFormat('en-NG',{style:'currency',currency:'NGN',maximumFractionDigits:0}).format(value);
  const node=(tag,cls,text)=>{
    const element=document.createElement(tag);
    if(cls)element.className=cls;
    if(text!==undefined)element.textContent=String(text);
    return element;
  };
  let offset=0,loading=false,inventoryItems=[],productNames=new Map();
  const feedback=(message,kind='')=>{
    const target=$a('admin-status');
    if(!target)return;
    target.textContent=message;
    target.className='admin-alert'+(kind?' admin-alert--'+kind:'');
  };
  async function verified(){
    if(!token()){
      feedback('Sign in with an authorized staff account to continue.','notice');
      return false;
    }
    try{
      const summary=await apiRequest('/admin/overview',{authorize:true});
      $a('admin-content').hidden=false;
      $a('admin-login').hidden=true;
      displayOverview(summary);
      return true;
    }catch(error){
      $a('admin-content').hidden=true;
      $a('admin-login').hidden=false;
      if(!token())feedback('Session expired. Sign in again to access the dashboard.','notice');
      else feedback(error.message==='Administrator privileges required'
        ? 'Access denied: this account is not authorized as FÌLÀ staff. Contact the account owner.'
        : 'Unable to verify staff access: '+error.message,'error');
      return false;
    }
  }
  function displayOverview(data){
    const mapping=[
      ['admin-active-products',data.active_products],
      ['admin-available-units',data.available_units],
      ['admin-enquiries',data.total_enquiries],
      ['admin-unquoted',data.unquoted_enquiries],
      ['admin-quoted',data.quoted_enquiries],
      ['admin-out-of-stock',data.out_of_stock_variants],
    ];
    for(const [id,value] of mapping)$a(id).textContent=Number.isInteger(value)?value:'—';
  }
  async function refreshOverview(){
    displayOverview(await apiRequest('/admin/overview',{authorize:true}));
  }
  async function loadInventory(){
    const [items,products]=await Promise.all([
      apiRequest('/admin/inventory',{authorize:true}),
      apiRequest('/products'),
    ]);
    if(!Array.isArray(items)||!Array.isArray(products))throw new Error('Unexpected inventory response.');
    inventoryItems=items;productNames=new Map(products.map(p=>[p.id,p.name]));
    const body=$a('admin-stock-rows');
    body.replaceChildren();
    for(const item of items){
      const tr=node('tr');
      tr.append(node('td','',productNames.get(item.product_id)||item.product_id));
      tr.append(node('td','',item.size));
      const col=node('td');
      const input=node('input','admin-stock-input');
      input.type='number';input.min='0';input.max='100000';input.step='1';
      input.value=String(item.available_quantity);
      input.setAttribute('aria-label','Available units for '+(productNames.get(item.product_id)||item.product_id)+' size '+item.size);
      col.append(input);tr.append(col);
      const action=node('td');
      const save=node('button','button button--dark admin-small-button','Save stock');
      save.type='button';
      save.addEventListener('click',async()=>{
        const qty=Number(input.value);
        if(input.value.trim()===''||!Number.isSafeInteger(qty)||qty<0||qty>100000){
          feedback('Enter a whole-number stock quantity between 0 and 100000.','notice');input.focus();return;
        }
        if(qty===item.available_quantity){feedback('No changes to save.');return;}
        const product=productNames.get(item.product_id)||item.product_id;
        if(!window.confirm('Change AVAILABLE stock for '+product+' size '+item.size+' from '+item.available_quantity+' to '+qty+'?'))return;
        save.disabled=true;
        try{
          await apiRequest('/admin/inventory/'+encodeURIComponent(item.product_id)+'/'+encodeURIComponent(item.size),{
            method:'PUT',authorize:true,body:{available_quantity:qty}
          });
          await Promise.all([loadInventory(),refreshOverview()]);
          feedback('Stock saved for '+product+' size '+item.size+'.','success');
        }catch(error){feedback('Stock was not updated: '+error.message,'error');save.disabled=false;}
      });
      action.append(save);tr.append(action);body.append(tr);
    }
    if(!items.length){const row=node('tr');const cell=node('td','', 'No inventory rows available.');cell.colSpan=4;row.append(cell);body.append(row);}
  }
  const statusLabel=status=>({
    draft:'Unpaid selection / enquiry',
    reserved:'Temporary hold · NOT paid',
    cancelled:'Cancelled',expired:'Expired',
  })[status]||('Status: '+status);
  function displayOrder(order){
    const card=node('article','admin-order-card');
    const head=node('div','admin-order-head');
    const name=node('h3','',order.customer_name||'Customer');
    const state=node('span','admin-status-pill',statusLabel(order.status));
    head.append(name,state);card.append(head);
    card.append(node('p','admin-muted',order.customer_email||'No email available'));
    card.append(node('p','admin-ref','Enquiry reference: '+order.id));
    const location=order.delivery_destination||'Not provided';
    card.append(node('p','','Delivery destination: '+location));
    const when=new Date(order.created_at);
    if(!Number.isNaN(when.getTime()))card.append(node('p','admin-muted','Created '+when.toLocaleString('en-NG',{dateStyle:'medium',timeStyle:'short'})));
    const lines=node('ul','admin-order-lines');
    for(const item of order.items||[]){
      lines.append(node('li','',item.product_name+' · size '+item.size+' · '+item.quantity+' × '+ngn(item.unit_price_ngn)));
    }
    card.append(lines);
    card.append(node('p','admin-order-total','Items subtotal: '+ngn(order.total_ngn)));
    if(order.shipping_quote_ngn!==null&&order.shipping_quote_ngn!==undefined){
      card.append(node('p','admin-order-total','Delivery quote: '+ngn(order.shipping_quote_ngn)+' · Estimated total: '+ngn(order.estimated_total_ngn)+' · NOT PAID'));
    }
    if(order.status==='draft'&&order.delivery_destination){
      const form=node('form','admin-quote-form');
      const label=node('label','','Delivery quote (₦)');
      const input=node('input');
      input.type='number';input.required=true;input.min='0';input.max='2000000';input.step='1';
      input.placeholder='e.g. 2500';
      input.value=order.shipping_quote_ngn===null?'':String(order.shipping_quote_ngn);
      const id='quote-'+order.id;
      input.id=id;label.htmlFor=id;
      const button=node('button','button button--gold admin-small-button','Save delivery quote');
      button.type='submit';
      form.append(label,input,button);
      form.addEventListener('submit',async event=>{
        event.preventDefault();
        const amount=Number(input.value);
        if(input.value.trim()===''||!Number.isSafeInteger(amount)||amount<0||amount>2000000){
          feedback('Enter a delivery quote between ₦0 and ₦2,000,000.','notice');input.focus();return;
        }
        if(!window.confirm('Save a delivery quote of '+ngn(amount)+' for enquiry '+order.id+'? No payment will be collected.'))return;
        button.disabled=true;
        try{
          await apiRequest('/admin/orders/'+encodeURIComponent(order.id)+'/delivery-quote',{
            method:'PUT',authorize:true,body:{shipping_amount_ngn:amount}
          });
          await refreshOverview();offset=0;$a('admin-order-list').replaceChildren();await loadOrders();
          feedback('Delivery quote saved. Customer can view the estimate in their account.','success');
        }catch(error){feedback('Quote was not saved: '+error.message,'error');button.disabled=false;}
      });
      card.append(form);
    }
    return card;
  }
  async function loadOrders(){
    if(loading)return;
    loading=true;
    const button=$a('admin-more-orders');button.disabled=true;
    try{
      const data=await apiRequest('/admin/orders?limit=20&offset='+offset,{authorize:true});
      if(!Array.isArray(data))throw new Error('Unexpected orders response.');
      if(offset===0&&data.length===0)$a('admin-order-list').append(node('p','admin-muted','No customer selections or enquiries recorded yet.'));
      for(const order of data)$a('admin-order-list').append(displayOrder(order));
      offset+=data.length;button.hidden=data.length<20;
    }catch(error){feedback('Unable to load enquiries: '+error.message,'error');}
    finally{loading=false;button.disabled=false;}
  }
  async function loadDashboard(){
    const allowed=await verified();if(!allowed)return;
    feedback('Loading inventory and enquiries…');
    offset=0;$a('admin-order-list').replaceChildren();
    try{
      await Promise.all([loadInventory(),loadOrders()]);
      feedback('Staff access verified. You are viewing live unpaid operations data.','success');
    }catch(error){feedback('Dashboard could not load all data: '+error.message,'error');}
  }
  document.addEventListener('DOMContentLoaded',()=>{
    if(document.body.dataset.page!=='admin')return;
    $a('admin-refresh').addEventListener('click',loadDashboard);
    $a('admin-more-orders').addEventListener('click',loadOrders);
    $a('admin-signout').addEventListener('click',()=>{
      storeToken('');
      $a('admin-content').hidden=true;
      $a('admin-login').hidden=false;
      $a('admin-login-form').reset();
      feedback('Signed out of the staff dashboard.','notice');
    });
    $a('admin-login-form').addEventListener('submit',async event=>{
      event.preventDefault();
      const form=$a('admin-login-form');
      if(!form.reportValidity())return;
      const submit=$a('admin-login-submit'),state=$a('admin-login-feedback');
      submit.disabled=true;state.textContent='Authenticating staff account…';
      try{
        const session=await apiRequest('/auth/login',{method:'POST',body:{
          email:$a('admin-email').value.trim(),
          password:$a('admin-password').value,
        }});
        if(!session.access_token)throw new Error('Authentication did not return a session');
        storeToken(session.access_token);
        const granted=await verified();
        if(!granted){
          storeToken('');
          state.textContent='This account is not authorized to manage FÌLÀ. Contact the owner.';
          return;
        }
        form.reset();state.textContent='';
        await loadDashboard();
      }catch(error){
        storeToken('');$a('admin-content').hidden=true;$a('admin-login').hidden=false;
        state.textContent='Sign-in failed: '+error.message;
      }finally{submit.disabled=false;}
    });
    if(token())loadDashboard();
    else {$a('admin-login').hidden=false;feedback('Sign in as verified staff to continue.','notice');}
  });
})();
