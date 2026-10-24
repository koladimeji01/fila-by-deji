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
async function uploadProductWithPhoto(details, file){
  const access=token();
  if(!access)throw new Error('Staff sign-in required');
  const payload=new FormData();
  payload.append('details',JSON.stringify(details));
  payload.append('photo',file,file.name);
  const response=await fetch(API_BASE+'/admin/products/with-photo',{
    method:'POST',headers:{Authorization:'Bearer '+access,Accept:'application/json'},
    body:payload,credentials:'omit',cache:'no-store'
  });
  const body=await response.json().catch(()=>({}));
  if(!response.ok){
    if(response.status===401)storeToken('');
    const error=typeof body?.detail==='string'?body.detail:
      (response.status===413?'The selected photo is too large.':
       response.status===403?'Administrator privileges required':
       'Photo upload failed ('+response.status+')');
    throw new Error(error);
  }
  return body;
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
  let offset=0,loading=false,inventoryItems=[],productNames=new Map(),loadedOrders=[];
  const feedback=(message,kind='')=>{
    const target=$a('admin-status');
    if(!target)return;
    target.textContent=message;
    target.className='admin-alert'+(kind?' admin-alert--'+kind:'');
  };
  // Registration never gives anyone staff privileges. /auth/register creates a
  // regular user; administrator access is explicitly granted outside this form.
  function showAuthPanel(mode){
    const signup=mode==='signup';
    $a('admin-login').hidden=signup;
    $a('admin-signup').hidden=!signup;
    $a('admin-content').hidden=true;
    $a('admin-login-feedback').textContent='';
    $a('admin-signup-feedback').textContent='';
    feedback(signup
      ? 'New accounts require approval by the FÌLÀ business administrator before dashboard access.'
      : 'Sign in with an approved staff account to continue.','notice');
    $a(signup?'admin-signup-name':'admin-email').focus();
  }
  async function submitSignup(event){
    event.preventDefault();
    const form=$a('admin-signup-form');
    if(!form.reportValidity())return;
    const name=$a('admin-signup-name').value.trim().replace(/\s+/g,' ');
    const email=$a('admin-signup-email').value.trim();
    const password=$a('admin-signup-password').value;
    const confirmation=$a('admin-signup-confirm').value;
    const status=$a('admin-signup-feedback');
    if(name.length<2){
      status.textContent='Please enter your full name (at least two characters).';
      $a('admin-signup-name').focus();return;
    }
    if(password.length<12 || password.length>128){
      status.textContent='Your password must be between 12 and 128 characters.';
      $a('admin-signup-password').focus();return;
    }
    if(password!==confirmation){
      status.textContent='Passwords do not match. Please check both fields.';
      $a('admin-signup-confirm').focus();return;
    }
    const submit=$a('admin-signup-submit');
    submit.disabled=true;
    status.textContent='Creating your account…';
    try{
      const account=await apiRequest('/staff/register',{
        method:'POST',body:{name,email,password}
      });
      if(!account?.id)throw new Error('Registration could not be confirmed.');
      // Never store a token or assume the new account is an administrator.
      form.reset();
      showAuthPanel('login');
      $a('admin-email').value=email;
      $a('admin-login-feedback').textContent=
        'Staff request submitted. A staff manager can now review it in the Staff Management dashboard.';
      feedback('Staff request submitted. Your account is pending staff-manager approval.','success');
    }catch(error){
      status.textContent='Unable to create account: '+error.message;
    }finally{
      submit.disabled=false;
    }
  }
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
      ['admin-active-holds',data.active_stock_holds],
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
  function toggleProductCreator(show){
    const form=$a('admin-create-product');
    form.hidden=!show;
    $a('admin-open-add-product').setAttribute('aria-expanded',String(show));
    if(show){
      form.scrollIntoView({behavior:'smooth',block:'start'});
      $a('admin-new-name').focus({preventScroll:true});
    }else{
      $a('admin-open-add-product').focus();
    }
  }
  let currentPhotoPreviewUrl=null;
  function clearPhotoPreview(){
    if(currentPhotoPreviewUrl)URL.revokeObjectURL(currentPhotoPreviewUrl);
    currentPhotoPreviewUrl=null;
    $a('admin-photo-preview').removeAttribute('src');
    $a('admin-photo-preview').hidden=true;
    $a('admin-photo-preview-wrap').hidden=true;
    $a('admin-photo-filename').textContent='';
  }
  function updatePhotoSource(){
    const device=$a('admin-photo-device').checked;
    $a('admin-photo-device-panel').hidden=!device;
    $a('admin-photo-url-panel').hidden=device;
    $a('admin-new-photo-file').required=device;
    $a('admin-new-photo-file').disabled=!device;
    $a('admin-new-image').required=!device;
    $a('admin-new-image').disabled=device;
    $a('admin-create-feedback').textContent='';
  }
  function previewDevicePhoto(){
    clearPhotoPreview();
    const photo=$a('admin-new-photo-file').files?.[0];
    if(!photo)return;
    const acceptable=['image/jpeg','image/png','image/webp'];
    if(!acceptable.includes(photo.type)||photo.size>5*1024*1024||photo.size===0){
      $a('admin-create-feedback').textContent='Choose a JPG, PNG or WebP file no larger than 5 MB.';
      $a('admin-new-photo-file').value='';
      return;
    }
    currentPhotoPreviewUrl=URL.createObjectURL(photo);
    $a('admin-photo-preview').src=currentPhotoPreviewUrl;
    $a('admin-photo-preview').hidden=false;
    $a('admin-photo-filename').textContent=photo.name;
    $a('admin-photo-preview-wrap').hidden=false;
  }
  async function createProduct(event){
    event.preventDefault();
    const form=$a('admin-create-product');
    if(!form.reportValidity())return;
    const status=$a('admin-create-feedback');
    status.textContent='';
    const fields={
      name:$a('admin-new-name').value.trim(),
      category:$a('admin-new-category').value.trim(),
      description:$a('admin-new-description').value.trim(),
      price_ngn:Number($a('admin-new-price').value),
      image_url:$a('admin-new-image').value.trim(),
      is_active:$a('admin-new-publish').checked,
      stock_by_size:{},
    };
    if(fields.name.length<2 || fields.category.length<2 || fields.description.length<5){
      status.textContent='Enter a meaningful name, category and description.';return;
    }
    if(!Number.isSafeInteger(fields.price_ngn) || fields.price_ngn<100 || fields.price_ngn>10000000){
      status.textContent='Price must be a whole number from ₦100 to ₦10,000,000.';return;
    }
    const fromDevice=$a('admin-photo-device').checked;
    let devicePhoto=null;
    if(fromDevice){
      devicePhoto=$a('admin-new-photo-file').files?.[0];
      if(!devicePhoto || !['image/jpeg','image/png','image/webp'].includes(devicePhoto.type) ||
         devicePhoto.size===0 || devicePhoto.size>5*1024*1024){
        status.textContent='Select a JPG, PNG or WebP photo from your device (5 MB maximum).';
        return;
      }
      delete fields.image_url;
    }else{
      try{
        const photo=new URL(fields.image_url);
        if(photo.protocol!=='https:' || photo.username || photo.password ||
           !/\.(jpg|jpeg|png|webp)$/i.test(photo.pathname))throw new Error();
      }catch{
        status.textContent='Use a public HTTPS photo URL ending with .jpg, .jpeg, .png or .webp.';return;
      }
    }
    for(const size of ['32','35','39','41']){
      const input=$a('admin-new-stock-'+size);
      const qty=Number(input.value);
      if(input.value.trim()==='' || !Number.isSafeInteger(qty) || qty<0 || qty>100000){
        status.textContent='Stock for size '+size+' must be a whole number between 0 and 100,000.';
        input.focus();return;
      }
      fields.stock_by_size[size]=qty;
    }
    const save=$a('admin-create-submit');
    save.disabled=true;status.textContent='Saving your cap…';
    try{
      const product=fromDevice
        ?await uploadProductWithPhoto(fields,devicePhoto)
        :await apiRequest('/admin/products',{method:'POST',authorize:true,body:fields});
      if(!product?.id)throw new Error('Product was not confirmed by the server.');
      form.reset();
      clearPhotoPreview();
      updatePhotoSource();
      for(const size of ['32','35','39','41'])$a('admin-new-stock-'+size).value='0';
      toggleProductCreator(false);
      const results=await Promise.allSettled([loadProducts(),loadInventory(),refreshOverview()]);
      const failed=results.some(r=>r.status==='rejected');
      const saved='Created '+product.name+'. '+(fields.is_active
        ? 'It is published in the customer catalogue.'
        : 'It is saved as a hidden draft.');
      feedback(saved+(failed?' Some dashboard sections need a refresh.':''),failed?'notice':'success');
    }catch(error){
      status.textContent='Could not save new product: '+error.message;
      feedback('New product was not confirmed: '+error.message,'error');
    }finally{save.disabled=false;}
  }
  const productPhotoPreviews=new Set();
  function clearProductPhotoPreviews(){
    for(const url of productPhotoPreviews)URL.revokeObjectURL(url);
    productPhotoPreviews.clear();
  }
  function productPhotoEditor(product){
    const panel=node('section','admin-product-photo-editor');
    panel.setAttribute('aria-label','Photo for '+product.name);
    panel.append(node('h4','','Product photo'));
    const preview=node('img','admin-product-photo-editor__image');
    preview.alt='Current photo for '+product.name;
    preview.loading='lazy';
    if(typeof product.image_url==='string'){
      if(/^assets\/[a-z0-9_-]+\.(jpg|jpeg|png|webp)$/i.test(product.image_url)){
        preview.src='https://fila-by-deji.vercel.app/'+product.image_url;
      }else{
        try{
          const target=new URL(product.image_url);
          if(target.protocol==='https:'&&!target.username&&!target.password&&
             /\.(jpg|jpeg|png|webp)$/i.test(target.pathname))preview.src=target.href;
        }catch{}
      }
    }
    if(!preview.getAttribute('src'))preview.hidden=true;
    preview.addEventListener('error',()=>{preview.hidden=true});
    panel.append(preview);
    const modeLabel=node('label','admin-form-field','Replace photo using');
    const mode=node('select');
    for(const [value,label] of [['device','Photo from device'],['url','Public photo URL']]){
      const option=node('option','',label);option.value=value;mode.append(option);
    }
    modeLabel.append(mode);
    const fileLabel=node('label','admin-form-field','Select JPG, PNG or WebP (max 5 MB)');
    const file=node('input');file.type='file';
    file.accept='image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp';
    fileLabel.append(file);
    const urlLabel=node('label','admin-form-field','Public HTTPS photo URL');
    const link=node('input');link.type='url';link.maxLength=300;
    link.placeholder='https://your-photo-host.com/new-cap.jpg';
    if(typeof product.image_url==='string'&&product.image_url.startsWith('https://')){
      link.value=product.image_url;
    }
    urlLabel.append(link);
    const status=node('p','admin-muted');
    status.setAttribute('role','status');
    status.setAttribute('aria-live','polite');
    const save=node('button','button button--outline admin-small-button','Replace photo');
    save.type='button';
    function switchMode(){
      const device=mode.value==='device';
      fileLabel.hidden=!device;file.disabled=!device;
      urlLabel.hidden=device;link.disabled=device;
      status.textContent='';
    }
    mode.addEventListener('change',switchMode);
    switchMode();
    file.addEventListener('change',()=>{
      const chosen=file.files?.[0];
      if(!chosen)return;
      if(!['image/jpeg','image/png','image/webp'].includes(chosen.type)
         ||chosen.size===0||chosen.size>5*1024*1024){
        file.value='';
        status.textContent='Choose a JPG, PNG or WebP image under 5 MB.';
        return;
      }
      const old=preview.dataset.objectUrl;
      if(old){productPhotoPreviews.delete(old);URL.revokeObjectURL(old);}
      const temporary=URL.createObjectURL(chosen);
      productPhotoPreviews.add(temporary);
      preview.dataset.objectUrl=temporary;
      preview.src=temporary;preview.hidden=false;
      status.textContent='Preview ready. Select Replace photo to save.';
    });
    save.addEventListener('click',async()=>{
      let body=null;
      let chosen=null;
      if(mode.value==='device'){
        chosen=file.files?.[0];
        if(!chosen||!['image/jpeg','image/png','image/webp'].includes(chosen.type)
           ||chosen.size===0||chosen.size>5*1024*1024){
          status.textContent='Choose a valid JPG, PNG or WebP photo from your device (up to 5 MB).';
          return;
        }
      }else{
        const imageUrl=link.value.trim();
        try{
          const target=new URL(imageUrl);
          if(target.protocol!=='https:'||target.username||target.password||
            !/\.(jpg|jpeg|png|webp)$/i.test(target.pathname))throw new Error();
        }catch{
          status.textContent='Use a direct public HTTPS .jpg, .jpeg, .png or .webp image link.';
          return;
        }
        if(imageUrl===product.image_url){status.textContent='This is already the current photo.';return;}
        body={image_url:imageUrl};
      }
      if(!window.confirm('Replace the existing picture for '+product.name+'? Product details and stock will not change.'))return;
      save.disabled=true;
      status.textContent='Saving replacement photo…';
      try{
        const route='/admin/products/'+encodeURIComponent(product.id);
        let changed;
        if(chosen){
          const data=new FormData();
          data.append('photo',chosen,chosen.name);
          const access=token();
          if(!access)throw new Error('Staff sign-in required');
          const response=await fetch(API_BASE+route+'/photo',{
            method:'PUT',headers:{Authorization:'Bearer '+access,Accept:'application/json'},
            body:data,credentials:'omit',cache:'no-store'
          });
          const outcome=await response.json().catch(()=>({}));
          if(!response.ok){
            if(response.status===401)storeToken('');
            throw new Error(typeof outcome.detail==='string'?outcome.detail:
              'Unable to upload photo ('+response.status+')');
          }
          changed=outcome;
        }else{
          changed=await apiRequest(route+'/photo-url',{
            method:'PUT',authorize:true,body
          });
        }
        if(!changed?.id)throw new Error('Photo update was not confirmed');
        await loadProducts();
        feedback('Photo updated for '+product.name+'. Product stock and historical enquiries are unchanged.','success');
      }catch(error){
        status.textContent='Photo was not updated: '+error.message;
        feedback('Photo replacement failed: '+error.message,'error');
        save.disabled=false;
      }
    });
    panel.append(modeLabel,fileLabel,urlLabel,save,status);
    return panel;
  }
  async function loadProducts(){
    const products=await apiRequest('/admin/products',{authorize:true});
    if(!Array.isArray(products))throw new Error('Unexpected product response.');
    const list=$a('admin-product-list');
    clearProductPhotoPreviews();
    list.replaceChildren();
    for(const product of products){
      const form=node('form','admin-product-card');
      const title=node('div','admin-product-card__heading');
      title.append(node('h3','',product.name),node('span','admin-status-pill',product.is_active?'Visible':'Archived'));
      form.append(title,productPhotoEditor(product));
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
  let reportData=null;
  function renderReports(report){
    const stats=$a('admin-report-stats');
    const list=$a('admin-report-by-product');
    const chart=$a('admin-report-chart');
    const axis=$a('admin-report-chart-axis');
    stats.replaceChildren();list.replaceChildren();chart.replaceChildren();axis.replaceChildren();
    const metrics=[
      ['Recorded enquiries',report.metrics.enquiries],
      ['Unique customers',report.metrics.unique_customers],
      ['Cap units selected · unpaid',report.metrics.selected_units],
      ['Delivery quotes issued',report.metrics.quoted],
      ['Active draft enquiries',report.metrics.drafts],
      ['Temporary stock holds',report.metrics.reserved],
    ];
    for(const [caption,value] of metrics){
      const card=node('article','admin-stat');
      card.append(node('span','',caption),node('strong','',value));stats.append(card);
    }
    const period=report.start_date+' to '+report.end_date+' ('+report.timezone+').';
    const warning=report.truncated
      ? ' Large period: showing only the newest '+report.analyzed_entries+' entries. Select a shorter period for complete figures.'
      : ' Covers all '+report.analyzed_entries+' recorded entries in this period.';
    $a('admin-report-note').textContent=period+warning+' No confirmed sales or revenue are recorded.';
    $a('admin-export-report').disabled=Boolean(report.truncated);
    $a('admin-export-report').title=report.truncated
      ?'Complete export exceeds the safety limit. Choose a shorter period.'
      :'Download the complete selected period as a CSV.';
    $a('admin-report-chart-total').textContent=report.metrics.enquiries+' enquiries';
    if(!Array.isArray(report.daily)||!report.daily.length){
      chart.append(node('p','admin-muted','No enquiry activity available.'));
      return;
    }
    const maximum=Math.max(1,...report.daily.map(p=>p.enquiries));
    const isEmpty=report.daily.every(p=>p.enquiries===0);
    chart.setAttribute('aria-label',
      'Enquiries by day from '+report.start_date+' to '+report.end_date+
      '. Total '+report.metrics.enquiries+'. Highest daily count '+(isEmpty?0:maximum)+'.');
    chart.classList.toggle('admin-report-chart--empty',isEmpty);
    for(const p of report.daily){
      const day=node('div','admin-report-day');
      const bar=node('div','admin-report-bar');
      if(p.enquiries===0)bar.classList.add('admin-report-bar--zero');
      bar.style.height=p.enquiries?Math.max(7,Math.round(100*p.enquiries/maximum))+'%':'2px';
      bar.setAttribute('title',p.day+': '+p.enquiries+' enquiries');
      bar.setAttribute('aria-hidden','true');
      day.append(bar);
      chart.append(day);
    }
    if(isEmpty)chart.append(node('p','admin-report-empty-note','No enquiries recorded in this period.'));
    for(const index of [0,Math.floor((report.daily.length-1)/2),report.daily.length-1]){
      const item=report.daily[index];
      const label=node('span','',new Date(item.day+'T12:00:00').toLocaleDateString('en-NG',{month:'short',day:'numeric'}));
      axis.append(label);
    }
    list.append(node('h3','','Most selected caps (not sales)'));
    if(!report.products.length)list.append(node('p','admin-muted','No cap selections recorded in this period.'));
    for(const p of report.products){
      const row=node('div','admin-report-row');
      row.append(node('span','',p.name),node('strong','',p.selected_units+' units · '+p.enquiries+' selections'));
      list.append(row);
    }
  }
  async function loadReports(){
    const days=Number($a('admin-report-period').value);
    if(![7,30,90].includes(days))throw new Error('Choose a valid reporting period.');
    $a('admin-report-note').textContent='Loading '+days+'-day operational report…';
    const report=await apiRequest('/admin/reports?days='+days,{authorize:true});
    if(!report||report.days!==days||!report.metrics||!Array.isArray(report.products))
      throw new Error('Unexpected analytics response.');
    reportData=report;
    renderReports(report);
  }
  async function exportReports(){
    if(!reportData){feedback('Load the report before exporting.','notice');return;}
    if(reportData.truncated){
      feedback('Select a shorter period for a complete CSV export.','notice');return;
    }
    const days=Number($a('admin-report-period').value);
    if(days!==reportData.days){feedback('Refresh the report for the selected period.','notice');return;}
    const button=$a('admin-export-report');
    button.disabled=true;
    try{
      const access=token();
      if(!access)throw new Error('Staff sign-in required');
      const response=await fetch(API_BASE+'/admin/reports/export?days='+days,{
        headers:{Authorization:'Bearer '+access,Accept:'text/csv'},
        credentials:'omit',cache:'no-store'
      });
      if(!response.ok){
        const error=await response.json().catch(()=>({}));
        if(response.status===401)storeToken('');
        throw new Error(typeof error.detail==='string'?error.detail:'Unable to export report ('+response.status+')');
      }
      const blob=await response.blob();
      const fileURL=URL.createObjectURL(blob);
      const a=node('a');
      a.href=fileURL;
      a.download='fila-enquiries-'+reportData.start_date+'-'+reportData.end_date+'.csv';
      document.body.append(a);a.click();a.remove();
      setTimeout(()=>URL.revokeObjectURL(fileURL),1000);
      feedback('Complete '+days+'-day CSV export created. Handle customer details securely.','success');
    }catch(error){feedback('Report export failed: '+error.message,'error');}
    finally{button.disabled=Boolean(reportData?.truncated);}
  }
  async function saveStaffProfile(event){
    event.preventDefault();
    const form=$a('admin-profile-form');
    if(!form.reportValidity())return;
    const target=$a('admin-profile-feedback');
    const button=$a('admin-profile-save');
    const name=$a('admin-profile-name').value.trim().replace(/\s+/g,' ');
    if(name.length<2||name.length>100){
      target.textContent='Enter a display name between 2 and 100 characters.';return;
    }
    button.disabled=true;
    target.textContent='Saving your profile…';
    try{
      const user=await apiRequest('/admin/account/profile',{
        method:'PUT',authorize:true,body:{name}
      });
      $a('admin-staff-name').textContent=user.name;
      $a('admin-profile-name').value=user.name;
      target.textContent='Profile saved successfully.';
      feedback('Your staff display name has been updated.','success');
    }catch(error){
      target.textContent='Could not save profile: '+error.message;
      feedback('Profile was not saved: '+error.message,'error');
    }finally{button.disabled=false;}
  }
  async function changeStaffPassword(event){
    event.preventDefault();
    const form=$a('admin-password-form');
    if(!form.reportValidity())return;
    const target=$a('admin-password-feedback');
    const button=$a('admin-password-save');
    const current_password=$a('admin-current-password').value;
    const new_password=$a('admin-new-password').value;
    const confirmation=$a('admin-confirm-password').value;
    if(new_password.length<12||new_password.length>128){
      target.textContent='New password must be 12 to 128 characters.';return;
    }
    if(new_password!==confirmation){
      target.textContent='The new passwords do not match.';return;
    }
    if(current_password===new_password){
      target.textContent='Choose a new password different from the current one.';return;
    }
    button.disabled=true;
    target.textContent='Updating your password…';
    try{
      const result=await apiRequest('/admin/account/password',{
        method:'POST',authorize:true,body:{current_password,new_password}
      });
      if(!result?.access_token)throw new Error('New session was not confirmed');
      // Fresh token is issued after the backend revokes all older JWT sessions.
      storeToken(result.access_token);
      form.reset();
      target.textContent='Password changed. Your previous sessions are no longer authorized.';
      feedback('Your password has been changed securely.','success');
    }catch(error){
      target.textContent='Password was not changed: '+error.message;
      feedback('Password update failed: '+error.message,'error');
    }finally{button.disabled=false;}
  }
  async function loadStaff(){
    const staff=await apiRequest('/auth/me',{authorize:true});
    $a('admin-staff-name').textContent=staff.name||'—';
    $a('admin-profile-name').value=staff.name||'';
    $a('admin-staff-email').textContent=staff.email||'—';
  }
  async function refreshOverview(){
    displayOverview(await apiRequest('/admin/overview',{authorize:true}));
  }
  async function loadStockMonitoring(){
    const threshold=Number($a('admin-stock-threshold').value);
    if(![2,3,5,10].includes(threshold))throw new Error('Choose a valid stock threshold.');
    const [data,history]=await Promise.all([
      apiRequest('/admin/inventory/alerts?threshold='+threshold,{authorize:true}),
      apiRequest('/admin/inventory/changes?limit=30',{authorize:true}),
    ]);
    if(data.threshold!==threshold||!Array.isArray(data.alerts)||!Array.isArray(history)){
      throw new Error('Invalid stock monitoring response.');
    }
    const summary=$a('admin-inventory-alerts-summary');
    const alerts=$a('admin-inventory-alerts-list');
    const log=$a('admin-inventory-history-list');
    summary.replaceChildren();alerts.replaceChildren();log.replaceChildren();
    for(const [title,count] of [
      ['Out of stock sizes',data.out_of_stock],
      ['Low stock sizes',data.low_stock],
      ['Sizes requiring attention',data.alerts.length],
    ]){
      const card=node('article','admin-inventory-summary-card');
      card.append(node('span','',title),node('strong','',count));
      summary.append(card);
    }
    $a('admin-inventory-alerts-note').textContent='Checking published caps at or below '+threshold+
      ' available units per size. This is an on-demand report, not a push notification.';
    if(!data.alerts.length){
      alerts.append(node('p','admin-muted','No published cap sizes are below the selected threshold.'));
    }
    for(const item of data.alerts){
      const row=node('div','admin-inventory-alert');
      const info=node('div');
      info.append(node('strong','',item.product_name+' · Size '+item.size));
      info.append(node('span','admin-muted','Available: '+item.available_quantity+' units'));
      const level=node('span','admin-status-pill admin-inventory-alert__'+item.status,
        item.status==='out'?'Out of stock':'Low stock');
      row.append(info,level);alerts.append(row);
    }
    if(!history.length)log.append(node('p','admin-muted','No staff inventory changes have been recorded yet.'));
    const reasonNames={restock:'Restock',correction:'Stock count correction',damage:'Damaged / unavailable',other:'Other adjustment'};
    for(const item of history){
      const row=node('div','admin-inventory-history-row');
      const title=node('div');
      title.append(node('strong','',item.product_name+' · Size '+item.size));
      title.append(node('span','admin-muted',(reasonNames[item.reason]||item.reason)+' · '+item.changed_by_name));
      const detail=node('div','admin-inventory-history-detail');
      detail.append(node('strong','',item.previous_quantity+' → '+item.new_quantity));
      const when=new Date(item.changed_at);
      if(!Number.isNaN(when.getTime())){
        detail.append(node('small','admin-muted',when.toLocaleString('en-NG',{dateStyle:'medium',timeStyle:'short'})));
      }
      row.append(title,detail);log.append(row);
    }
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
      const reasonCell=node('td');
      const reason=node('select','admin-stock-reason');
      for(const [value,label] of [
        ['correction','Stock count correction'],
        ['restock','Restock delivery'],
        ['damage','Damaged / unavailable'],
        ['other','Other adjustment'],
      ]){
        const option=node('option','',label);option.value=value;reason.append(option);
      }
      reason.setAttribute('aria-label','Reason for changing '+(productNames.get(item.product_id)||item.product_id)+' size '+item.size);
      reasonCell.append(reason);tr.append(reasonCell);
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
        if(!window.confirm('Change AVAILABLE stock for '+product+' size '+item.size+' from '+item.available_quantity+' to '+qty+'? Reason: '+reason.options[reason.selectedIndex].text+'.'))return;
        save.disabled=true;
        try{
          await apiRequest('/admin/inventory/'+encodeURIComponent(item.product_id)+'/'+encodeURIComponent(item.size),{
            method:'PUT',authorize:true,body:{available_quantity:qty,reason:reason.value}
          });
          await Promise.all([loadInventory(),refreshOverview(),loadStockMonitoring()]);
          feedback('Stock saved for '+product+' size '+item.size+'.','success');
        }catch(error){feedback('Stock was not updated: '+error.message,'error');save.disabled=false;}
      });
      action.append(save);tr.append(action);body.append(tr);
    }
    if(!items.length){const row=node('tr');const cell=node('td','', 'No inventory rows available.');cell.colSpan=5;row.append(cell);body.append(row);}
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
          await refreshOverview();offset=0;loadedOrders=[];await loadOrders();
          feedback('Delivery quote saved. Customer can view the estimate in their account.','success');
        }catch(error){feedback('Quote was not saved: '+error.message,'error');button.disabled=false;}
      });
      card.append(form);
    }
    const followup=node('form','admin-followup-form');
    const heading=node('h4','','Private staff follow-up');
    const stageLabel=node('label','','Follow-up status');
    const stageSelect=node('select');
    stageSelect.required=true;
    for(const [value,label] of [
      ['new','New — not contacted'],['contacted','Contacted'],
      ['awaiting_reply','Awaiting customer reply'],['closed','Closed follow-up (not paid)']
    ]){
      const option=node('option','',label);option.value=value;
      if((order.followup_stage||'new')===value)option.selected=true;
      stageSelect.append(option);
    }
    stageLabel.append(stageSelect);
    const noteLabel=node('label','','Internal note (private)');
    const note=node('textarea');
    note.rows=3;note.maxLength=1200;
    note.placeholder='e.g. Emailed about delivery location. Awaiting confirmation.';
    note.value=order.internal_note||'';
    noteLabel.append(note);
    const actions=node('div','admin-followup-actions');
    const save=node('button','button button--dark admin-small-button','Save follow-up');
    save.type='submit';
    actions.append(save);
    if(order.followup_updated_at){
      const d=new Date(order.followup_updated_at);
      if(!Number.isNaN(d.getTime())){
        actions.append(node('small','admin-muted','Last updated '+d.toLocaleString('en-NG',{dateStyle:'medium',timeStyle:'short'})));
      }
    }
    const hint=node('p','admin-muted','Visible only to staff. Does not confirm payment, delivery or change stock.');
    followup.append(heading,stageLabel,noteLabel,hint,actions);
    followup.addEventListener('submit',async event=>{
      event.preventDefault();
      if(!followup.reportValidity())return;
      save.disabled=true;
      const body={stage:stageSelect.value,internal_note:note.value.trim()};
      try{
        const updated=await apiRequest('/admin/orders/'+encodeURIComponent(order.id)+'/followup',{
          method:'PUT',authorize:true,body
        });
        loadedOrders=loadedOrders.map(entry=>entry.id===updated.id?updated:entry);
        renderVisibleOrders();
        feedback('Private follow-up saved. The customer-facing order status has not changed.','success');
      }catch(error){
        feedback('Unable to save follow-up: '+error.message,'error');
        save.disabled=false;
      }
    });
    card.append(followup);
    return card;
  }
  function renderVisibleOrders(){
    const list=$a('admin-order-list');
    const search=$a('admin-enquiry-search').value.trim().toLowerCase();
    const stage=$a('admin-enquiry-stage-filter').value;
    const filtered=loadedOrders.filter(order=>{
      if(stage!=='all'&&(order.followup_stage||'new')!==stage)return false;
      if(!search)return true;
      return [order.id,order.customer_name,order.customer_email,order.delivery_destination]
        .some(value=>String(value||'').toLowerCase().includes(search));
    });
    list.replaceChildren();
    for(const order of filtered)list.append(displayOrder(order));
    if(!filtered.length){
      list.append(node('p','admin-muted',loadedOrders.length
        ?'No loaded enquiries match these filters. Adjust the search or load more entries.'
        :'No customer selections or enquiries recorded yet.'));
    }
    $a('admin-enquiry-filter-count').textContent='Showing '+filtered.length+' of '+loadedOrders.length+
      ' loaded entries. Search and filters apply to the loaded entries only.';
  }
  async function loadOrders(){
    if(loading)return;
    loading=true;
    const button=$a('admin-more-orders');button.disabled=true;
    try{
      const data=await apiRequest('/admin/orders?limit=20&offset='+offset,{authorize:true});
      if(!Array.isArray(data))throw new Error('Unexpected orders response.');
      loadedOrders.push(...data);
      offset+=data.length;button.hidden=data.length<20;
      renderVisibleOrders();
    }catch(error){feedback('Unable to load enquiries: '+error.message,'error');throw error;}
    finally{loading=false;button.disabled=false;}
  }
  async function loadStaffManagement(){
    const panel=$a('admin-staff-section'),nav=$a('admin-staff-nav');
    const list=$a('admin-staff-list'),stats=$a('admin-staff-summary'),status=$a('admin-staff-feedback');
    let accounts;
    try{
      accounts=await apiRequest('/admin/staff',{authorize:true});
    }catch(error){
      panel.hidden=true;nav.hidden=true;
      if(error.message==='Staff management permission required')return;
      throw error;
    }
    panel.hidden=false;nav.hidden=false;
    if(!Array.isArray(accounts))throw new Error('Invalid staff-management response');
    status.textContent='Showing '+accounts.length+' staff accounts and applications. Only staff managers may approve access.';
    list.replaceChildren();stats.replaceChildren();
    for(const [caption,value] of [
      ['Pending requests',accounts.filter(a=>a.status==='pending').length],
      ['Approved staff',accounts.filter(a=>a.is_admin).length],
      ['Rejected requests',accounts.filter(a=>a.status==='rejected').length],
      ['Revoked access',accounts.filter(a=>a.status==='revoked').length],
    ]){
      const card=node('article','admin-stat');
      card.append(node('span','',caption),node('strong','',value));
      stats.append(card);
    }
    const statuses={pending:'Awaiting approval',approved:'Approved staff',rejected:'Not approved',revoked:'Access revoked'};
    for(const account of accounts){
      const card=node('article','admin-staff-card');
      const content=node('div','admin-staff-card__details');
      const heading=node('div','admin-staff-card__title');
      heading.append(node('h3','',account.name));
      heading.append(node('span','admin-status-pill',''+(account.can_manage_staff?'Staff manager':(statuses[account.status]||account.status))));
      content.append(heading,node('p','admin-muted',account.email));
      if(account.requested_at){
        const date=new Date(account.requested_at);
        if(!Number.isNaN(date.getTime()))content.append(node('p','admin-muted','Requested '+date.toLocaleString('en-NG',{dateStyle:'medium',timeStyle:'short'})));
      }
      const actions=node('div','admin-staff-card__actions');
      const decisions=account.status==='pending'?[
        ['approve','Approve','button button--gold'],
        ['reject','Reject','button button--outline'],
      ]:(account.is_admin&&!account.can_manage_staff)?[
        ['revoke','Revoke access','button button--outline'],
      ]:[];
      for(const [action,label,style] of decisions){
        const button=node('button',style+' admin-small-button',label);
        button.type='button';
        button.addEventListener('click',async()=>{
          const descriptions={
            approve:'Approve '+account.name+' for business operations? This does NOT give staff-management privileges.',
            reject:'Reject staff access for '+account.name+'?',
            revoke:'Revoke business dashboard access for '+account.name+'? This will not delete their customer account.',
          };
          if(!window.confirm(descriptions[action]))return;
          button.disabled=true;
          try{
            await apiRequest('/admin/staff/'+encodeURIComponent(account.user_id)+'/decision',{
              method:'POST',authorize:true,body:{action}
            });
            await loadStaffManagement();
            feedback('Staff access updated successfully.','success');
          }catch(error){
            status.textContent='Unable to change access: '+error.message;
            button.disabled=false;
          }
        });
        actions.append(button);
      }
      card.append(content,actions);list.append(card);
    }
    if(!accounts.length)list.append(node('p','admin-muted','No staff applications yet. Registered requests will appear here.'));
  }
  async function requestExistingStaffAccess(){
    const state=$a('admin-login-feedback'),button=$a('admin-request-existing');
    const email=$a('admin-email').value.trim(),password=$a('admin-password').value;
    const form=$a('admin-login-form');
    if(!form.reportValidity())return;
    button.disabled=true;state.textContent='Checking your account…';
    try{
      const session=await apiRequest('/auth/login',{method:'POST',body:{email,password}});
      if(!session.access_token)throw new Error('Authentication did not return a session');
      storeToken(session.access_token);
      const outcome=await apiRequest('/staff/apply',{method:'POST',authorize:true});
      state.textContent=outcome.message||'Request submitted for approval.';
      feedback(state.textContent,'success');
    }catch(error){
      state.textContent='Unable to request access: '+error.message;
    }finally{
      storeToken('');
      button.disabled=false;
    }
  }
  function renderNotifications(data){
    if(!data||!Array.isArray(data.notifications)||!Number.isInteger(data.unread_count))
      throw new Error('Unexpected notifications response.');
    const badge=$a('admin-notifications-badge');
    const list=$a('admin-notifications-list');
    const readAll=$a('admin-notifications-read-all');
    const unread=Math.max(0,data.unread_count);
    badge.textContent=String(unread);
    badge.hidden=unread===0;
    readAll.disabled=unread===0;
    $a('admin-notifications-info').textContent=
      unread+' new or unreviewed alert'+(unread===1?'':'s')+' · '+data.notifications.length+
      ' active notifications. Read status is saved to your staff account.';
    list.replaceChildren();
    if(!data.notifications.length){
      list.append(node('p','admin-muted','No active notifications. Check again when new business activity arrives.'));
      return;
    }
    const targets={
      enquiry:{href:'#admin-orders-title',label:'View enquiries'},
      stock:{href:'#admin-inventory-title',label:'View inventory'},
      staff:{href:'#admin-staff-title',label:'Review staff requests'},
    };
    const typeNames={enquiry:'Customer enquiry',stock:'Stock alert',staff:'Staff application'};
    for(const item of data.notifications){
      if(!targets[item.kind])continue;
      const card=node('article','admin-notification-card'+(item.is_read?' admin-notification-card--read':''));
      const content=node('div','admin-notification-copy');
      const heading=node('div','admin-notification-heading');
      heading.append(node('strong','',item.title));
      heading.append(node('span','admin-notification-type',typeNames[item.kind]));
      content.append(heading,node('p','',item.detail));
      if(item.created_at){
        const timestamp=new Date(item.created_at);
        if(!Number.isNaN(timestamp.getTime())){
          content.append(node('small','admin-muted',timestamp.toLocaleString('en-NG',{dateStyle:'medium',timeStyle:'short'})));
        }
      }
      const actions=node('div','admin-notification-actions');
      const view=node('a','button button--outline admin-small-button',targets[item.kind].label);
      view.href=targets[item.kind].href;
      actions.append(view);
      if(!item.is_read){
        const read=node('button','button button--dark admin-small-button','Mark as read');
        read.type='button';
        read.addEventListener('click',async()=>{
          read.disabled=true;
          try{
            const result=await apiRequest('/admin/notifications/read',{
              method:'POST',authorize:true,body:{key:item.key}
            });
            renderNotifications(result);
          }catch(error){
            feedback('Could not mark alert as read: '+error.message,'error');
            read.disabled=false;
          }
        });
        actions.append(read);
      }else{
        actions.append(node('span','admin-notification-read-label','Read'));
      }
      card.append(content,actions);
      list.append(card);
    }
  }
  async function loadNotifications(){
    $a('admin-notifications-info').textContent='Checking recent business activity…';
    const result=await apiRequest('/admin/notifications',{authorize:true});
    renderNotifications(result);
  }
  async function markAllNotificationsRead(){
    const button=$a('admin-notifications-read-all');
    button.disabled=true;
    try{
      const result=await apiRequest('/admin/notifications/read-all',{
        method:'POST',authorize:true
      });
      renderNotifications(result);
      feedback('All current notifications marked as read.','success');
    }catch(error){
      feedback('Could not update notifications: '+error.message,'error');
      button.disabled=false;
    }
  }
  async function loadDashboard(){
    const allowed=await verified();if(!allowed)return;
    feedback('Loading inventory and enquiries…');
    offset=0;loadedOrders=[];$a('admin-order-list').replaceChildren();
    const results=await Promise.allSettled([loadNotifications(),loadProducts(),loadInventory(),loadStockMonitoring(),loadOrders(),loadReports(),loadStaff(),loadStaffManagement()]);
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
    $a('admin-show-signup').addEventListener('click',()=>showAuthPanel('signup'));
    $a('admin-show-login').addEventListener('click',()=>showAuthPanel('login'));
    $a('admin-signup-form').addEventListener('submit',submitSignup);
    $a('admin-profile-form').addEventListener('submit',saveStaffProfile);
    $a('admin-password-form').addEventListener('submit',changeStaffPassword);
    $a('admin-request-existing').addEventListener('click',requestExistingStaffAccess);
    $a('admin-staff-refresh').addEventListener('click',loadStaffManagement);
    $a('admin-refresh').addEventListener('click',loadDashboard);
    $a('admin-notifications-refresh').addEventListener('click',()=>loadNotifications().catch(error=>{
      $a('admin-notifications-info').textContent='Unable to load notifications: '+error.message;
      feedback('Unable to load notifications: '+error.message,'error');
    }));
    $a('admin-notifications-read-all').addEventListener('click',markAllNotificationsRead);
    $a('admin-more-orders').addEventListener('click',loadOrders);
    $a('admin-stock-threshold').addEventListener('change',()=>loadStockMonitoring().catch(error=>{
      $a('admin-inventory-alerts-note').textContent='Unable to refresh stock alerts: '+error.message;
      feedback('Unable to refresh stock alerts: '+error.message,'error');
    }));
    $a('admin-inventory-refresh').addEventListener('click',()=>loadStockMonitoring().catch(error=>{
      $a('admin-inventory-alerts-note').textContent='Unable to refresh stock alerts: '+error.message;
      feedback('Unable to refresh stock alerts: '+error.message,'error');
    }));
    $a('admin-enquiry-search').addEventListener('input',renderVisibleOrders);
    $a('admin-enquiry-stage-filter').addEventListener('change',renderVisibleOrders);
    $a('admin-open-add-product').addEventListener('click',()=>toggleProductCreator($a('admin-create-product').hidden));
    $a('admin-cancel-add-product').addEventListener('click',()=>toggleProductCreator(false));
    $a('admin-create-product').addEventListener('submit',createProduct);
    $a('admin-photo-device').addEventListener('change',updatePhotoSource);
    $a('admin-photo-link').addEventListener('change',updatePhotoSource);
    $a('admin-new-photo-file').addEventListener('change',previewDevicePhoto);
    updatePhotoSource();
    $a('admin-report-period').addEventListener('change',()=>loadReports().catch(error=>{
      $a('admin-report-note').textContent='Report could not load: '+error.message;
      feedback('Report could not load: '+error.message,'error');
    }));
    $a('admin-report-refresh').addEventListener('click',()=>loadReports().catch(error=>{
      $a('admin-report-note').textContent='Report could not load: '+error.message;
      feedback('Report could not load: '+error.message,'error');
    }));
    $a('admin-export-report').addEventListener('click',exportReports);
    $a('admin-release-expired').addEventListener('click',async()=>{
      const button=$a('admin-release-expired');
      button.disabled=true;
      try{
        const result=await apiRequest('/admin/reservations/release-expired',{method:'POST',authorize:true});
        await loadDashboard();
        feedback('Released '+Number(result.expired||0)+' expired stock hold(s). Active holds remain untouched.','success');
      }catch(error){feedback('Unable to release expired holds: '+error.message,'error');}
      finally{button.disabled=false;}
    });
    const signOut=()=>{
      storeToken('');
      $a('admin-notifications-list').replaceChildren();
      $a('admin-notifications-info').textContent='Sign in to view notifications.';
      $a('admin-notifications-badge').hidden=true;
      $a('admin-notifications-read-all').disabled=true;
      $a('admin-content').hidden=true;
      $a('admin-login').hidden=false;
      $a('admin-login-form').reset();
      $a('admin-profile-form').reset();
      $a('admin-password-form').reset();
      $a('admin-profile-feedback').textContent='';
      $a('admin-password-feedback').textContent='';
      reportData=null;
      $a('admin-report-stats').replaceChildren();
      $a('admin-report-by-product').replaceChildren();
      $a('admin-report-chart').replaceChildren();
      $a('admin-report-chart-axis').replaceChildren();
      $a('admin-report-note').textContent='Sign in to view reports.';
      $a('admin-report-stats').replaceChildren();
      $a('admin-product-list').replaceChildren();
      loadedOrders=[];
      $a('admin-order-list').replaceChildren();
      $a('admin-inventory-alerts-summary').replaceChildren();
      $a('admin-inventory-alerts-list').replaceChildren();
      $a('admin-inventory-history-list').replaceChildren();
      $a('admin-staff-section').hidden=true;
      $a('admin-staff-nav').hidden=true;
      $a('admin-staff-list').replaceChildren();
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
          try{
            const application=await apiRequest('/staff/status',{authorize:true});
            state.textContent=application.message;
          }catch{
            state.textContent='This account is not authorized to manage FÌLÀ. Contact the owner.';
          }
          storeToken('');
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
