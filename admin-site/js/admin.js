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
  // Product editing is deliberately limited to existing records and verified imagery.
  const inputField=(labelText,value,{multiline=false,maxLength=150}={})=>{
    const wrap=node('label','admin-form-field');
    const title=node('span','',labelText);
    const field=node(multiline?'textarea':'input');
    if(!multiline)field.type='text';
    field.required=true;field.maxLength=maxLength;
    field.value=value??'';
    wrap.append(title,field);
    return {wrap,field};
  };
  async function loadProducts(){
    const products=await apiRequest('/admin/products',{authorize:true});
    if(!Array.isArray(products))throw new Error('Unexpected product response.');
    const list=$a('admin-product-list');
    list.replaceChildren();
    for(const product of products){
      const form=node('form','admin-product-card');
      const title=node('div','admin-product-card__heading');
      title.append(node('h3','',product.name),node('span','admin-status-pill',product.is_active?'Visible':'Archived'));
      form.append(title);
      const fields=[
        inputField('Product name',product.name,{maxLength:150}),
        inputField('Category',product.category,{maxLength:50}),
        inputField('Description',product.description,{multiline:true,maxLength:2000})
      ];
      for(const f of fields)form.append(f.wrap);
      const priceWrap=node('label','admin-form-field');
      priceWrap.append(node('span','','Price in naira (₦)'));
      const price=node('input');
      price.type='number';price.required=true;price.min='100';price.max='10000000';price.step='1';
      price.value=String(product.price_ngn);
      priceWrap.append(price);form.append(priceWrap);
      const visibility=node('label','admin-product-checkbox');
      const active=node('input');active.type='checkbox';active.checked=product.is_active;
      visibility.append(active,node('span','','Show this cap in the customer collection'));
      form.append(visibility);
      const actions=node('div','admin-product-card__actions');
      const save=node('button','button button--gold admin-small-button','Save product');
      save.type='submit';
      actions.append(save);form.append(actions);
      form.addEventListener('submit',async event=>{
        event.preventDefault();
        if(!form.reportValidity())return;
        const amount=Number(price.value);
        if(!Number.isSafeInteger(amount)||amount<100||amount>10000000){
          feedback('Price must be a whole number between ₦100 and ₦10,000,000.','notice');return;
        }
        const payload={
          name:fields[0].field.value.trim(),
          category:fields[1].field.value.trim(),
          description:fields[2].field.value.trim(),
          price_ngn:amount,
          is_active:active.checked
        };
        if(!payload.name||!payload.category||!payload.description){
          feedback('Complete every product field.','notice');return;
        }
        if(!window.confirm('Save live catalogue changes for '+product.name+'?'))return;
        save.disabled=true;
        try{
          await apiRequest('/admin/products/'+encodeURIComponent(product.id),{
            method:'PUT',authorize:true,body:payload
          });
          await Promise.all([loadProducts(),loadInventory(),refreshOverview()]);
          feedback('Product updated. The customer collection will reflect the latest details.','success');
        }catch(error){feedback('Product update failed: '+error.message,'error');save.disabled=false;}
      });
      list.append(form);
    }
    if(!products.length)list.append(node('p','admin-muted','No products are configured.'));
  }
  let reportRows=[];
  const csvSafe=value=>{
    let str=String(value??'');
    if(/^\s*[=+@-]/.test(str))str="'"+str;
    return '"'+str.replace(/"/g,'""')+'"';
  };
  async function loadReports(){
    const orders=await apiRequest('/admin/orders?limit=100&offset=0',{authorize:true});
    if(!Array.isArray(orders))throw new Error('Unexpected report response.');
    reportRows=orders;
    const statusCount=new Map();
    const capCount=new Map();
    for(const order of orders){
      const state=order.status||'unknown';
      statusCount.set(state,(statusCount.get(state)||0)+1);
      for(const item of order.items||[]){
        const name=item.product_name||item.product_id||'Cap';
        capCount.set(name,(capCount.get(name)||0)+Number(item.quantity||0));
      }
    }
    const quoted=orders.filter(o=>o.shipping_quote_ngn!==null&&o.shipping_quote_ngn!==undefined).length;
    const stats=$a('admin-report-stats');stats.replaceChildren();
    const metrics=[
      ['Latest recorded entries',orders.length],
      ['Active unpaid enquiries',statusCount.get('draft')||0],
      ['Stock holds (not paid)',statusCount.get('reserved')||0],
      ['Delivery quotes on entries',quoted],
      ['Cancelled entries',statusCount.get('cancelled')||0],
      ['Expired entries',statusCount.get('expired')||0],
    ];
    for(const [label,value] of metrics){
      const card=node('article','admin-stat');
      card.append(node('span','',label),node('strong','',value));stats.append(card);
    }
    const note=$a('admin-report-note');
    note.textContent='Report covers the latest '+orders.length+
      ' recorded entries (maximum 100), not lifetime totals. No payments or revenue are recorded.';
    const list=$a('admin-report-by-product');list.replaceChildren();
    list.append(node('h3','','Cap quantities in these entries'));
    if(!capCount.size)list.append(node('p','admin-muted','No cap selections to report yet.'));
    for(const [name,count] of [...capCount].sort((a,b)=>b[1]-a[1])){
      const row=node('div','admin-report-row');
      row.append(node('span','',name),node('strong','',count+' selected'));list.append(row);
    }
  }
  function exportReports(){
    if(!reportRows.length){feedback('No report entries to export.','notice');return;}
    const columns=['Created at','Reference','Customer','Email','Status','Destination','Items subtotal NGN','Delivery quote NGN'];
    const lines=[columns.map(csvSafe).join(',')];
    for(const order of reportRows){
      const values=[order.created_at,order.id,order.customer_name,order.customer_email,
        order.status,order.delivery_destination,order.total_ngn,order.shipping_quote_ngn];
      lines.push(values.map(csvSafe).join(','));
    }
    const blob=new Blob(['\uFEFF'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'});
    const url=URL.createObjectURL(blob);
    const a=node('a');a.href=url;a.download='fila-operations-'+new Date().toISOString().slice(0,10)+'.csv';
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    feedback('Exported the latest '+reportRows.length+' entries. Keep customer information confidential.','success');
  }
  async function loadStaff(){
    const staff=await apiRequest('/auth/me',{authorize:true});
    $a('admin-staff-name').textContent=staff.name||'—';
    $a('admin-staff-email').textContent=staff.email||'—';
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
    }catch(error){feedback('Unable to load enquiries: '+error.message,'error');throw error;}
    finally{loading=false;button.disabled=false;}
  }
  async function loadDashboard(){
    const allowed=await verified();if(!allowed)return;
    feedback('Loading inventory and enquiries…');
    offset=0;$a('admin-order-list').replaceChildren();
    const results=await Promise.allSettled([loadProducts(),loadInventory(),loadOrders(),loadReports(),loadStaff()]);
    const failures=results.filter(result=>result.status==='rejected');
    if(failures.length){
      feedback('Some sections could not load. Please refresh. '+failures.map(x=>x.reason?.message||'Service error').join('; '),'error');
    }else{
      feedback('Staff access verified. Operational information is up to date.','success');
    }
    return true;
  }
  document.addEventListener('DOMContentLoaded',()=>{
    if(document.body.dataset.page!=='admin')return;
    $a('admin-refresh').addEventListener('click',loadDashboard);
    $a('admin-more-orders').addEventListener('click',loadOrders);
    $a('admin-export-report').addEventListener('click',exportReports);
    const signOut=()=>{
      storeToken('');
      $a('admin-content').hidden=true;
      $a('admin-login').hidden=false;
      $a('admin-login-form').reset();
      reportRows=[];
      $a('admin-report-stats').replaceChildren();
      $a('admin-product-list').replaceChildren();
      $a('admin-staff-name').textContent='—';
      $a('admin-staff-email').textContent='—';
      feedback('Signed out of the staff dashboard.','notice');
    };
    $a('admin-signout').addEventListener('click',signOut);
    $a('admin-settings-signout').addEventListener('click',signOut);
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
        const granted=await loadDashboard();
        if(!granted){
          storeToken('');
          state.textContent='This account is not authorized to manage FÌLÀ. Contact the owner.';
          return;
        }
        form.reset();state.textContent='';
      }catch(error){
        storeToken('');$a('admin-content').hidden=true;$a('admin-login').hidden=false;
        state.textContent='Sign-in failed: '+error.message;
      }finally{submit.disabled=false;}
    });
    if(token())loadDashboard();
    else {$a('admin-login').hidden=false;feedback('Sign in as verified staff to continue.','notice');}
  });
})();
