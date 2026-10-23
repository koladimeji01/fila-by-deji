"""Regression tests for staff product edits and truthful stock counts."""
from app.database import SessionLocal
from app.models import User


def make_admin(client, auth):
    headers = auth(client)
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin = True
        db.commit()
    return headers


def form(is_active=True, price_ngn=12500):
    return {
        'name': '  Ceremonial Fila Updated  ',
        'category': ' Ceremonial ',
        'description': '  Elegant ceremonial cap, for cultural celebrations.  ',
        'price_ngn': price_ngn,
        'is_active': is_active,
    }


def test_product_editor_requires_real_admin(client, auth):
    normal = auth(client)
    assert client.get('/api/v1/admin/products').status_code == 401
    assert client.get('/api/v1/admin/products', headers=normal).status_code == 403
    assert client.put('/api/v1/admin/products/ceremonial', headers=normal,
                      json=form()).status_code == 403


def test_admin_edits_only_existing_product_and_updates_live_catalogue(client, auth):
    staff = make_admin(client, auth)
    listed = client.get('/api/v1/admin/products', headers=staff)
    assert listed.status_code == 200
    assert len(listed.json()) == 3
    before = client.get('/api/v1/products/ceremonial').json()
    changed = client.put('/api/v1/admin/products/ceremonial', headers=staff, json=form())
    assert changed.status_code == 200, changed.text
    payload = changed.json()
    assert payload['price_ngn'] == 12500
    assert payload['name'] == 'Ceremonial Fila Updated'
    assert payload['description'] == 'Elegant ceremonial cap, for cultural celebrations.'
    assert payload['image_url'] == before['image_url']
    public = client.get('/api/v1/products/ceremonial').json()
    assert public['price_ngn'] == 12500
    assert public['name'] == payload['name']
    assert client.put('/api/v1/admin/products/not-real', headers=staff,
                      json=form()).status_code == 404


def test_product_editor_rejects_unexpected_fields_and_invalid_prices(client, auth):
    staff = make_admin(client, auth)
    url = '/api/v1/admin/products/ceremonial'
    assert client.put(url, headers=staff, json={**form(), 'is_admin': True}).status_code == 422
    assert client.put(url, headers=staff, json=form(price_ngn=-2)).status_code == 422
    assert client.put(url, headers=staff, json=form(price_ngn=15.5)).status_code == 422
    assert client.put(url, headers=staff, json={**form(), 'image_url':'https://bad.invalid/x.jpg'}).status_code == 422
    assert client.get('/api/v1/products/ceremonial').json()['price_ngn'] == 10000


def test_archived_products_stop_contributing_to_visible_stock(client, auth):
    staff = make_admin(client, auth)
    archived = client.put('/api/v1/admin/products/ceremonial', headers=staff, json=form(is_active=False))
    assert archived.status_code == 200, archived.text
    assert archived.json()['is_active'] is False
    assert client.get('/api/v1/products/ceremonial').status_code == 404
    ids = [p['id'] for p in client.get('/api/v1/products').json()]
    assert 'ceremonial' not in ids
    overview = client.get('/api/v1/admin/overview', headers=staff).json()
    assert overview['active_products'] == 2
    assert overview['available_units'] == 64
    assert overview['out_of_stock_variants'] == 0
    assert len(client.get('/api/v1/admin/products', headers=staff).json()) == 3


def test_active_hold_blocks_archiving_product(client, auth):
    staff = make_admin(client, auth)
    draft = client.post('/api/v1/orders/drafts', headers=staff, json={
        'items':[{'product_id':'ceremonial','size':'39','quantity':1}],
    })
    assert draft.status_code == 201
    hold = client.post('/api/v1/orders/'+draft.json()['id']+'/reserve', headers=staff)
    assert hold.status_code == 200
    blocked = client.put('/api/v1/admin/products/ceremonial', headers=staff, json=form(is_active=False))
    assert blocked.status_code == 409
    assert client.get('/api/v1/products/ceremonial').status_code == 200
