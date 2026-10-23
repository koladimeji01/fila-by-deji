import pytest
from app.database import SessionLocal
from app.models import Product, User
from app.security import create_token


def test_health_and_catalog(client):
    assert client.get('/api/v1/health').json() == {'status': 'ok'}
    result = client.get('/api/v1/products')
    assert result.status_code == 200
    assert len(result.json()) == 3
    assert {p['price_ngn'] for p in result.json()} == {10000}
    assert {p['id'] for p in result.json()} == {'ceremonial', 'classic', 'premium'}
    assert client.get('/api/v1/products/premium').json()['image_url'] == 'assets/premium.jpg'
    assert client.get('/api/v1/products/missing').status_code == 404


def test_register_login_and_profile(client):
    created = client.post('/api/v1/auth/register', json={
        'name': '  Ada Example  ', 'email': 'ADA@EXAMPLE.COM', 'password': 'a-great-long-secret-123'})
    assert created.status_code == 201
    assert created.json()['name'] == 'Ada Example'
    assert created.json()['email'] == 'ada@example.com'
    assert 'password' not in created.json()
    assert client.post('/api/v1/auth/register', json={
        'name': 'Again', 'email': 'ada@example.com', 'password': 'another-long-password'}).status_code == 409
    login = client.post('/api/v1/auth/login', json={
        'email': 'ada@example.com', 'password': 'a-great-long-secret-123'})
    assert login.status_code == 200
    assert client.get('/api/v1/auth/me', headers={'Authorization':'Bearer '+login.json()['access_token']}).json()['name'] == 'Ada Example'
    assert client.post('/api/v1/auth/login', json={
        'email': 'ada@example.com', 'password': 'wrong'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={
        'email': 'unknown@example.com', 'password': 'wrong'}).status_code == 401


def test_auth_rejects_missing_bad_expired_or_disabled(client, auth):
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.get('/api/v1/auth/me', headers={'Authorization':'Bearer not-a-jwt'}).status_code == 401
    credentials = auth(client)
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == 'ada@example.com').one()
        user.is_active = False
        db.commit()
    assert client.get('/api/v1/auth/me', headers=credentials).status_code == 401


def test_password_validation(client):
    result = client.post('/api/v1/auth/register', json={
        'name': 'Ada Example','email':'ada@example.com','password':'short'})
    assert result.status_code == 422
    result = client.post('/api/v1/auth/register', json={
        'name': '   ', 'email':'ada@example.com','password':'a-long-test-password'})
    assert result.status_code == 422


def test_order_requires_auth(client):
    result = client.post('/api/v1/orders/drafts', json={
        'items':[{'product_id':'premium','size':'39','quantity':1}]})
    assert result.status_code == 401


def test_server_side_pricing_and_ownership(client, auth):
    headers = auth(client)
    body = {'items':[{'product_id':'premium','size':'39','quantity':2},
                     {'product_id':'classic','size':'41','quantity':1}]}
    result = client.post('/api/v1/orders/drafts', json=body, headers=headers)
    assert result.status_code == 201, result.text
    order = result.json()
    assert order['status'] == 'draft'
    assert order['total_ngn'] == 30000
    assert all(item['unit_price_ngn'] == 10000 for item in order['items'])
    assert client.get('/api/v1/orders/'+order['id'], headers=headers).status_code == 200
    assert len(client.get('/api/v1/orders',headers=headers).json()) == 1
    other_headers = auth(client, email='other@example.com')
    assert client.get('/api/v1/orders/'+order['id'], headers=other_headers).status_code == 404
    assert client.get('/api/v1/orders', headers=other_headers).json() == []
    assert 'password_hash' not in str(order)


def test_draft_rejects_client_price_injection(client, auth):
    headers = auth(client)
    attempted = {'items':[{'product_id':'premium','size':'39','quantity':2,
                            'unit_price_ngn':1}], 'total_ngn':2, 'status':'paid'}
    result = client.post('/api/v1/orders/drafts', json=attempted,headers=headers)
    # Reject unexpected client-supplied totals or order states outright.
    assert result.status_code == 422
    valid = client.post('/api/v1/orders/drafts', json={
        'items': [{'product_id': 'premium', 'size': '39', 'quantity': 2}]}, headers=headers)
    assert valid.status_code == 201
    assert valid.json()['total_ngn'] == 20000
    assert valid.json()['status'] == 'draft'


@pytest.mark.parametrize('items', [
    [],
    [{'product_id':'premium','size':'XS','quantity':1}],
    [{'product_id':'premium','size':'39','quantity':0}],
    [{'product_id':'premium','size':'39','quantity':11}],
    [{'product_id':'premium','size':'39','quantity':1},
     {'product_id':'premium','size':'39','quantity':2}],
])
def test_bad_draft_inputs(client, auth, items):
    headers=auth(client)
    assert client.post('/api/v1/orders/drafts',json={'items':items},headers=headers).status_code == 422


def test_unavailable_product(client, auth):
    headers=auth(client)
    with SessionLocal() as db:
        product = db.get(Product, 'premium')
        product.is_active = False
        db.commit()
    result = client.post('/api/v1/orders/drafts',json={
        'items':[{'product_id':'premium','size':'39','quantity':1}]},headers=headers)
    assert result.status_code == 400
    assert client.get('/api/v1/products/premium').status_code == 404


def test_price_snapshot_unaffected_by_product_price_change(client, auth):
    headers=auth(client)
    result = client.post('/api/v1/orders/drafts',json={
        'items':[{'product_id':'premium','size':'39','quantity':1}]},headers=headers)
    order_id=result.json()['id']
    with SessionLocal() as db:
        product=db.get(Product,'premium')
        product.price_kobo=2_500_000
        db.commit()
    assert client.get('/api/v1/orders/'+order_id,headers=headers).json()['total_ngn']==10000
    next_order=client.post('/api/v1/orders/drafts',json={
        'items':[{'product_id':'premium','size':'39','quantity':1}]},headers=headers)
    assert next_order.json()['total_ngn']==25000


def test_cors_allows_local_frontend_only(client):
    valid = client.options('/api/v1/orders/drafts', headers={'Origin':'http://localhost:5500',
        'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
    assert valid.headers.get('access-control-allow-origin') == 'http://localhost:5500'
    invalid=client.options('/api/v1/orders/drafts', headers={'Origin':'https://evil.invalid',
        'Access-Control-Request-Method':'POST'})
    assert invalid.headers.get('access-control-allow-origin') is None

def test_checkout_request_is_idempotent_and_keeps_delivery_quote_unconfirmed(client, auth):
    from uuid import uuid4
    h = auth(client)
    key = str(uuid4())
    payload = {'client_request_id': key,
               'delivery_destination': 'Lagos, Ikeja',
               'items': [{'product_id': 'premium', 'size': '39', 'quantity': 2}]}
    first = client.post('/api/v1/orders/drafts', json=payload, headers=h)
    assert first.status_code == 201, first.text
    ref = first.json()['id']
    assert first.json()['total_ngn'] == 20000
    assert first.json()['status'] == 'draft'
    assert first.json()['delivery_destination'] == 'Lagos, Ikeja'
    again = client.post('/api/v1/orders/drafts', json=payload, headers=h)
    assert again.status_code == 201
    assert again.json()['id'] == ref
    assert len(client.get('/api/v1/orders', headers=h).json()) == 1
    amended = {**payload, 'items': [{'product_id': 'premium', 'size': '39', 'quantity': 1}]}
    assert client.post('/api/v1/orders/drafts', json=amended, headers=h).status_code == 409
    another = auth(client, email='stage3-other@example.com')
    assert client.post('/api/v1/orders/drafts', json=payload, headers=another).status_code == 409


def test_checkout_request_validates_shipping_destination(client, auth):
    h = auth(client)
    valid = {'items': [{'product_id': 'classic', 'size': '39', 'quantity': 1}]}
    assert client.post('/api/v1/orders/drafts', json={**valid, 'delivery_destination': '  Ibadan,   Oyo  '}, headers=h).json()['delivery_destination']=='Ibadan, Oyo'
    for invalid in ('x', '  ', 'a'*121):
        assert client.post('/api/v1/orders/drafts', json={**valid, 'delivery_destination': invalid}, headers=h).status_code == 422
    assert client.post('/api/v1/orders/drafts', json={**valid, 'client_request_id': 'guess'}, headers=h).status_code == 422
