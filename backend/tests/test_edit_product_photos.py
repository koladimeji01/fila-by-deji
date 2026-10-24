"""Safe replacement photos for existing cap styles (including seeded catalog)."""
import io
from PIL import Image
from app.database import SessionLocal
from app.models import Order, Product, ProductInventory, ProductPhoto, User


def login_admin(client, auth):
    headers=auth(client)
    with SessionLocal() as db:
        person=db.query(User).filter_by(email='ada@example.com').one()
        person.is_admin=True
        db.commit()
    return headers


def photo_bytes(color=(200,90,20)):
    out=io.BytesIO()
    Image.new('RGB',(340,310),color).save(out,format='PNG')
    return out.getvalue()


def photo_upload(client, product_id='classic', headers=None, body=None, mime='image/png'):
    if body is None:
        body=photo_bytes()
    return client.put('/api/v1/admin/products/'+product_id+'/photo',
                      headers=headers,files={'photo':('product.png',body,mime)})


def url_update(client, product_id='classic', headers=None, url='https://cdn.example.com/cap.jpg'):
    return client.put('/api/v1/admin/products/'+product_id+'/photo-url',
                      headers=headers,json={'image_url':url})


def test_edit_photo_requires_admin_for_upload_and_url(client, auth):
    customer=auth(client)
    for response in (
        photo_upload(client),
        photo_upload(client,headers=customer),
        url_update(client),
        url_update(client,headers=customer),
    ):
        assert response.status_code in (401,403)
    with SessionLocal() as db:
        assert db.query(ProductPhoto).count() == 0
        assert db.get(Product,'classic').image_url=='assets/classic.jpg'


def test_existing_original_cap_photo_can_be_replaced_without_touching_stock_or_history(client,auth):
    admin=login_admin(client,auth)
    draft=client.post('/api/v1/orders/drafts',headers=admin,json={
        'items':[{'product_id':'classic','size':'35','quantity':1}]
    })
    assert draft.status_code==201,draft.text
    order_id=draft.json()['id']
    before=client.get('/api/v1/products/classic').json()
    uploaded=photo_upload(client,headers=admin)
    assert uploaded.status_code==200,uploaded.text
    updated=uploaded.json()
    assert updated['id']=='classic'
    assert updated['name']==before['name']
    assert updated['price_ngn']==before['price_ngn']
    assert updated['stock_by_size']==before['stock_by_size']
    assert updated['image_url'].startswith(
      'https://fila-by-deji-api.onrender.com/api/v1/product-images/classic.webp?v='
    )
    fetched=client.get('/api/v1/product-images/classic.webp')
    assert fetched.status_code==200 and fetched.headers['content-type']=='image/webp'
    with Image.open(io.BytesIO(fetched.content)) as image:
        assert image.format=='WEBP'
    with SessionLocal() as db:
        assert db.get(ProductPhoto,'classic') is not None
        assert db.get(ProductInventory,('classic','35')).quantity==8
        order=db.get(Order,order_id)
        assert order.status=='draft' and order.items[0].product_id=='classic'
    second=photo_upload(client,headers=admin,body=photo_bytes((5,30,170)))
    assert second.status_code==200,second.text
    assert second.json()['image_url'] != updated['image_url']
    assert client.get('/api/v1/product-images/classic.webp').content != fetched.content
    assert client.get('/api/v1/orders/'+order_id,headers=admin).json()['status']=='draft'


def test_switch_from_uploaded_photo_to_safe_link_cleans_orphan_and_preserves_record(client,auth):
    admin=login_admin(client,auth)
    first=photo_upload(client,headers=admin)
    assert first.status_code==200, first.text
    assert client.get('/api/v1/product-images/classic.webp').status_code==200
    linked=url_update(client,headers=admin)
    assert linked.status_code==200,linked.text
    assert linked.json()['image_url']=='https://cdn.example.com/cap.jpg'
    assert linked.json()['is_active'] is True
    assert client.get('/api/v1/products/classic').json()['image_url']==linked.json()['image_url']
    assert client.get('/api/v1/product-images/classic.webp').status_code==404
    with SessionLocal() as db:
        assert db.get(ProductPhoto,'classic') is None
        assert db.get(Product,'classic').image_url=='https://cdn.example.com/cap.jpg'


def test_external_url_can_be_replaced_with_local_file(client,auth):
    admin=login_admin(client,auth)
    assert url_update(client,headers=admin).status_code==200
    replacement=photo_upload(client,headers=admin)
    assert replacement.status_code==200,replacement.text
    assert replacement.json()['image_url'].endswith('.webp?v='+replacement.json()['image_url'].split('?v=')[1])
    assert client.get('/api/v1/product-images/classic.webp').status_code==200


def test_invalid_uploads_and_external_urls_do_not_change_product(client,auth):
    admin=login_admin(client,auth)
    before=client.get('/api/v1/products/classic').json()['image_url']
    for data,mime,expected in (
        (b'', 'image/png', 422),
        (b'invalid-data','image/png',422),
        (photo_bytes(),'image/svg+xml',415),
        (b'1'*(5*1024*1024+1),'image/png',413),
    ):
        r=photo_upload(client,headers=admin,body=data,mime=mime)
        assert r.status_code==expected,r.text
    for url in (
        'http://example.com/bad.png','https://localhost/cap.webp',
        'https://127.0.0.1/cap.png','https://cdn.example.com/unsafe.svg',
        'https://user:pass@example.com/cap.jpg','https://cdn.example.com/a.jpg#frag'
    ):
        r=url_update(client,headers=admin,url=url)
        assert r.status_code==422,r.text
    assert client.put('/api/v1/admin/products/classic/photo-url',headers=admin,
        json={'image_url':'https://cdn.example.com/image.png','is_admin':True}).status_code==422
    assert photo_upload(client,'missing-product',admin).status_code==404
    assert url_update(client,'missing-product',admin).status_code==404
    with SessionLocal() as db:
        assert db.get(Product,'classic').image_url==before
        assert db.get(ProductPhoto,'classic') is None


def test_draft_photo_cannot_be_seen_publicly(client,auth):
    admin=login_admin(client,auth)
    original=client.get('/api/v1/admin/products',headers=admin).json()
    item=next(p for p in original if p['id']=='premium')
    disable=client.put('/api/v1/admin/products/premium',headers=admin,json={
        'name':item['name'],'category':item['category'],'description':item['description'],
        'price_ngn':item['price_ngn'],'is_active':False
    })
    assert disable.status_code==200
    replacement=photo_upload(client,'premium',admin)
    assert replacement.status_code==200,replacement.text
    assert client.get('/api/v1/product-images/premium.webp').status_code==404
    assert client.get('/api/v1/products/premium').status_code==404
    assert any(p['id']=='premium' for p in client.get('/api/v1/admin/products',headers=admin).json())


def test_photo_editor_wiring_and_original_default_paths():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    js=(root/'admin-site'/'js'/'admin.js').read_text(encoding='utf-8')
    storefront=(root/'js'/'app.js').read_text(encoding='utf-8')
    vercel=(root/'admin-site'/'vercel.json').read_text(encoding='utf-8')
    assert 'productPhotoEditor(product)' in js
    assert "mode.value==='device'" in js
    assert "'/photo-url'" in js and "'/photo'" in js
    assert "new FormData()" in js and "data.append('photo',chosen,chosen.name)" in js
    assert 'product.image_url===local' in storefront
    assert "img-src 'self' data: blob: https:" in vercel
