"""Stage 7 customer isolation, atomic reservations, expiry, admin separation."""
from datetime import timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Order, Product, ProductInventory, User
from app.reservations import now_utc


def draft(p='premium', size='39', quantity=2):
    return {'items': [{'product_id': p, 'size': size, 'quantity': quantity}]}


def make_draft(client, headers, body=None):
    response = client.post('/api/v1/orders/drafts', json=body or draft(), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()['id']


def available(p='premium', size='39'):
    with SessionLocal() as db:
        return db.get(ProductInventory, (p, size)).quantity


def test_reserve_decrements_exact_stock_and_order_remains_unpaid(client, auth):
    h = auth(client)
    order_id = make_draft(client, h)
    reservation = client.post(f'/api/v1/orders/{order_id}/reserve', headers=h)
    assert reservation.status_code == 200, reservation.text
    data = reservation.json()
    assert data['status'] == 'reserved'
    assert data['reserved_until'] is not None
    assert data['total_ngn'] == 20000
    assert available() == 6
    assert client.get('/api/v1/products/premium').status_code == 200
    assert client.post(f'/api/v1/orders/{order_id}/reserve', headers=h).status_code == 409
    assert available() == 6


def test_reserve_all_items_or_none(client, auth):
    h = auth(client)
    with SessionLocal() as db:
        db.get(ProductInventory, ('classic', '32')).quantity = 1
        db.commit()
    body = {'items': [{'product_id':'premium','size':'39','quantity':2},
                      {'product_id':'classic','size':'32','quantity':2}]}
    # Draft itself rejects insufficient stock; race stock change AFTER draft.
    order_id = make_draft(client, h, {'items': [dict(body['items'][0]), dict(body['items'][1], quantity=1)]})
    with SessionLocal() as db:
        db.get(ProductInventory, ('classic', '32')).quantity = 0
        db.commit()
    response = client.post(f'/api/v1/orders/{order_id}/reserve', headers=h)
    assert response.status_code == 409
    assert available() == 8
    assert available('classic','32') == 0
    assert client.get(f'/api/v1/orders/{order_id}', headers=h).json()['status'] == 'draft'


def test_reduced_stock_before_reservation_and_only_one_active_hold(client, auth):
    h = auth(client)
    one = make_draft(client, h, draft(quantity=1))
    two = make_draft(client, h, draft(quantity=1))
    assert client.post(f'/api/v1/orders/{one}/reserve',headers=h).status_code == 200
    assert client.post(f'/api/v1/orders/{two}/reserve',headers=h).status_code == 409
    assert available() == 7


def test_cancel_draft_or_reservation_and_prevent_double_restocks(client, auth):
    h=auth(client)
    a=make_draft(client,h)
    result=client.post(f'/api/v1/orders/{a}/cancel',headers=h)
    assert result.status_code == 200
    assert result.json()['status']=='cancelled'
    assert available()==8
    assert client.post(f'/api/v1/orders/{a}/reserve',headers=h).status_code==409
    assert client.post(f'/api/v1/orders/{a}/cancel',headers=h).status_code==409
    b=make_draft(client,h)
    assert client.post(f'/api/v1/orders/{b}/reserve',headers=h).status_code==200
    assert available()==6
    assert client.post(f'/api/v1/orders/{b}/cancel',headers=h).status_code==200
    assert available()==8
    assert client.post(f'/api/v1/orders/{b}/cancel',headers=h).status_code==409
    assert available()==8


def test_expiry_returns_inventory_exactly_once(client,auth):
    h=auth(client)
    oid=make_draft(client,h)
    client.post(f'/api/v1/orders/{oid}/reserve',headers=h)
    with SessionLocal() as db:
        order=db.get(Order,oid)
        order.reserved_until=now_utc()-timedelta(minutes=1)
        db.commit()
    # A catalog read opportunistically releases expired holds.
    assert client.get('/api/v1/products').status_code==200
    assert available()==8
    data=client.get(f'/api/v1/orders/{oid}',headers=h).json()
    assert data['status']=='expired'
    assert available()==8
    assert client.post(f'/api/v1/orders/{oid}/cancel',headers=h).status_code==409
    assert client.post(f'/api/v1/orders/{oid}/reserve',headers=h).status_code==409


def test_price_recalculated_at_reservation_time(client,auth):
    h=auth(client)
    oid=make_draft(client,h,draft(quantity=1))
    with SessionLocal() as db:
        p=db.get(Product,'premium')
        p.price_kobo=1_500_000
        db.commit()
    r=client.post(f'/api/v1/orders/{oid}/reserve',headers=h)
    assert r.status_code==200
    assert r.json()['total_ngn']==15000
    assert r.json()['items'][0]['unit_price_ngn']==15000


def test_cannot_modify_other_users_orders(client,auth):
    owner=auth(client)
    stranger=auth(client,email='other@example.com')
    oid=make_draft(client,owner)
    assert client.post(f'/api/v1/orders/{oid}/reserve',headers=stranger).status_code==404
    assert client.post(f'/api/v1/orders/{oid}/cancel',headers=stranger).status_code==404
    assert client.post(f'/api/v1/orders/{oid}/reserve').status_code==401
    assert available()==8


def test_admin_access_denied_to_customer_and_not_self_assignable(client,auth):
    h=auth(client)
    assert client.get('/api/v1/admin/inventory').status_code==401
    assert client.get('/api/v1/admin/inventory',headers=h).status_code==403
    assert client.get('/api/v1/admin/orders',headers=h).status_code==403
    assert client.post('/api/v1/admin/reservations/release-expired',headers=h).status_code==403
    url='/api/v1/admin/inventory/premium/39'
    assert client.put(url,headers=h,json={'available_quantity':900}).status_code==403
    assert available()==8
    reg=client.post('/api/v1/auth/register',json={'name':'Someone Else','email':'hidden@example.com',
      'password':'a-great-long-secret-123','is_admin':True})
    assert reg.status_code==422


def test_admin_updates_only_available_stock(client,auth):
    h=auth(client)
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin=True
        db.commit()
    levels=client.get('/api/v1/admin/inventory',headers=h)
    assert levels.status_code==200
    assert len(levels.json())==12
    url='/api/v1/admin/inventory/premium/39'
    good=client.put(url,json={'available_quantity':3},headers=h)
    assert good.status_code==200
    assert good.json()['available_quantity']==3
    assert available()==3
    assert client.put(url,json={'available_quantity':-1},headers=h).status_code==422
    assert client.put(url,json={'available_quantity':100001},headers=h).status_code==422
    assert client.put(url,json={'available_quantity':10,'price_ngn':1},headers=h).status_code==422
    assert client.put('/api/v1/admin/inventory/unknown/39',json={'available_quantity':2},headers=h).status_code==404
    assert available()==3
    oid=make_draft(client,h,draft(quantity=1))
    assert client.get('/api/v1/admin/orders',headers=h).json()[0]['id']==oid
    assert client.get('/api/v1/admin/orders?limit=0',headers=h).status_code==422
    assert client.get('/api/v1/admin/orders',headers=h).headers['cache-control']=='no-store'


def test_admin_sweep_can_release_expired_hold(client,auth):
    admin=auth(client)
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin=True
        db.commit()
    oid=make_draft(client,admin,draft(quantity=1))
    client.post(f'/api/v1/orders/{oid}/reserve',headers=admin)
    with SessionLocal() as db:
        db.get(Order,oid).reserved_until=now_utc()-timedelta(hours=1)
        db.commit()
    r=client.post('/api/v1/admin/reservations/release-expired',headers=admin)
    assert r.status_code==200
    assert r.json()['expired']==1
    assert available()==8
    assert client.post('/api/v1/admin/reservations/release-expired',headers=admin).json()['expired']==0


def test_admin_put_cors_preflight_from_approved_frontend(client):
    r=client.options('/api/v1/admin/inventory/premium/39', headers={
        'Origin':'http://localhost:5500',
        'Access-Control-Request-Method':'PUT',
        'Access-Control-Request-Headers':'authorization,content-type',
    })
    assert r.status_code==200
    assert r.headers.get('access-control-allow-origin')=='http://localhost:5500'
    r2=client.options('/api/v1/admin/inventory/premium/39', headers={
        'Origin':'https://not-allowed.invalid','Access-Control-Request-Method':'PUT',
    })
    assert r2.headers.get('access-control-allow-origin') is None
