"""Upload cap photos from devices without exposing database credentials."""
import io
import json
from PIL import Image
from app.database import SessionLocal
from app.models import Product, ProductPhoto, User


def staff(client, auth):
    credentials=auth(client)
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin=True
        db.commit()
    return credentials


def details(**changes):
    return {'name':'Navy Embroidered Fila', 'category':'Premium',
            'description':'A classic embroidered cap for traditional outfits.',
            'price_ngn':15000, 'stock_by_size':{'32':4,'35':0,'39':2,'41':1},
            'is_active':True, **changes}


def picture(fmt='PNG', size=(360,420)):
    output=io.BytesIO()
    Image.new('RGB',size,(110,70,40)).save(output, format=fmt)
    return output.getvalue()


def upload(client, headers=None, data=None, contents=None, filename='cap.png', mimetype='image/png'):
    return client.post('/api/v1/admin/products/with-photo', headers=headers,
        data={'details':json.dumps(data or details())},
        files={'photo':(filename,contents if contents is not None else picture(),mimetype)})


def test_device_photo_upload_requires_admin_role(client, auth):
    normal=auth(client)
    assert upload(client).status_code==401
    assert upload(client,normal).status_code==403
    assert len(client.get('/api/v1/products').json())==3


def test_device_photo_is_optimized_and_published_atomically(client, auth):
    admin=staff(client,auth)
    response=upload(client,admin)
    assert response.status_code==201, response.text
    product=response.json()
    assert product['image_url'].endswith('/api/v1/product-images/'+product['id']+'.webp')
    assert product['available_sizes']==['32','39','41']
    assert product['stock_by_size']=={'32':4,'35':0,'39':2,'41':1}
    page=client.get('/api/v1/product-images/'+product['id']+'.webp')
    assert page.status_code==200
    assert page.headers['content-type']=='image/webp'
    assert page.headers['cache-control']=='public, max-age=3600'
    assert page.content[:4]==b'RIFF'
    with Image.open(io.BytesIO(page.content)) as decoded:
        assert decoded.format=='WEBP'
        assert decoded.size==(360,420)
    with SessionLocal() as db:
        photo=db.get(ProductPhoto,product['id'])
        assert photo is not None and photo.image_data==page.content
        assert db.get(Product,product['id']).is_active
    visible=client.get('/api/v1/products').json()
    assert any(p['id']==product['id'] for p in visible)


def test_unpublished_device_photo_is_not_public_until_publish(client, auth):
    admin=staff(client,auth)
    response=upload(client,admin,data=details(is_active=False))
    assert response.status_code==201,response.text
    created=response.json()
    assert created['is_active'] is False
    image_path='/api/v1/product-images/'+created['id']+'.webp'
    assert client.get(image_path).status_code==404
    assert client.get('/api/v1/products/'+created['id']).status_code==404
    update={field:created[field] for field in ('name','category','description','price_ngn')}
    update['is_active']=True
    assert client.put('/api/v1/admin/products/'+created['id'], headers=admin,json=update).status_code==200
    assert client.get(image_path).status_code==200


def test_reject_invalid_and_oversized_device_photos_without_products(client, auth):
    admin=staff(client,auth)
    bad=[
        (b'not-a-picture','fake.png','image/png',422),
        (picture(), 'cap.svg', 'image/svg+xml',415),
        (b'x'*(5*1024*1024+1),'large.png','image/png',413),
        (picture(size=(20,20)),'tiny.png','image/png',422),
        (b'', 'empty.png','image/png',422),
    ]
    for data,filename,mime,expected in bad:
        response=upload(client,admin,contents=data,filename=filename,mimetype=mime)
        assert response.status_code==expected, response.text
    assert len(client.get('/api/v1/products').json())==3
    with SessionLocal() as db:
        assert db.query(ProductPhoto).count()==0


def test_reject_invalid_metadata_before_saving_photo(client, auth):
    admin=staff(client,auth)
    for values in (details(price_ngn=-2),details(stock_by_size={'40':1}),details(image_url='https://evil.test/img.webp')):
        result=upload(client,admin,data=values)
        assert result.status_code==422,result.text
    assert len(client.get('/api/v1/products').json())==3


def test_device_picker_and_url_option_are_both_present():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    html=(root/'admin-site'/'index.html').read_text()
    js=(root/'admin-site'/'js'/'admin.js').read_text()
    for field in ('admin-photo-device','admin-photo-link','admin-new-photo-file',
                  'admin-photo-preview','admin-photo-device-panel','admin-photo-url-panel'):
        assert 'id="'+field+'"' in html
    assert 'type="file" accept="image/jpeg,image/png,image/webp' in html
    assert "apiRequest('/admin/products',{method:'POST',authorize:true" in js
    assert "'/admin/products/with-photo'" in js
    assert 'new FormData()' in js and "payload.append('photo',file,file.name)" in js
    assert 'URL.createObjectURL' in js and 'URL.revokeObjectURL' in js
