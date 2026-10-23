"""Admin delivery quotes must be private, auditable and never collect money."""
from app.database import SessionLocal
from app.models import DeliveryQuoteAudit, Order, ProductInventory, User


def create_enquiry(client, auth, destination='Ikeja, Lagos'):
    headers = auth(client)
    r = client.post('/api/v1/orders/drafts', headers=headers, json={
        'items':[{'product_id':'premium','size':'39','quantity':2}],
        'delivery_destination':destination,
    })
    assert r.status_code == 201, r.text
    return headers, r.json()['id']


def grant_admin():
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin=True
        db.commit()


def test_only_admin_can_quote_unpaid_delivery(client, auth):
    customer, ref = create_enquiry(client,auth)
    url=f'/api/v1/admin/orders/{ref}/delivery-quote'
    body={'shipping_amount_ngn':2500}
    assert client.put(url,json=body).status_code == 401
    assert client.put(url,json=body,headers=customer).status_code == 403
    another=auth(client,email='another@example.com')
    grant_admin()
    good=client.put(url,json=body,headers=customer)
    assert good.status_code==200,good.text
    data=good.json()
    assert data['status']=='draft'
    assert data['shipping_quote_ngn']==2500
    assert data['estimated_total_ngn']==22500
    assert data['shipping_quoted_at'] is not None
    assert data['total_ngn']==20000
    assert client.get(f'/api/v1/orders/{ref}',headers=another).status_code==404
    own=client.get(f'/api/v1/orders/{ref}',headers=customer).json()
    assert own['shipping_quote_ngn']==2500
    assert own['estimated_total_ngn']==22500
    assert 'password_hash' not in str(data)
    with SessionLocal() as db:
        assert db.get(ProductInventory,('premium','39')).quantity==8
        assert db.query(DeliveryQuoteAudit).count()==1
    assert client.put(url,json=body,headers=customer).status_code==200
    with SessionLocal() as db:
        assert db.query(DeliveryQuoteAudit).count()==1
    newer=client.put(url,json={'shipping_amount_ngn':3000},headers=customer)
    assert newer.json()['estimated_total_ngn']==23000
    with SessionLocal() as db:
        logs=db.query(DeliveryQuoteAudit).order_by(DeliveryQuoteAudit.created_at).all()
        assert len(logs)==2
        assert sorted((x.new_amount_kobo for x in logs))==[250000,300000]
    assert client.put(url,json={'shipping_amount_ngn':True},headers=customer).status_code==422
    assert client.put(url,json={'shipping_amount_ngn':-1},headers=customer).status_code==422
    assert client.put(url,json={'shipping_amount_ngn':2_000_001},headers=customer).status_code==422
    assert client.put(url,json={'shipping_amount_ngn':200,'total_ngn':1},headers=customer).status_code==422
    assert client.put('/api/v1/admin/orders/does-not-exist/delivery-quote',json=body,headers=customer).status_code==404


def test_no_quote_on_cancelled_or_destinationless_order(client,auth):
    headers, ref=create_enquiry(client,auth)
    grant_admin()
    url=f'/api/v1/admin/orders/{ref}/delivery-quote'
    assert client.post(f'/api/v1/orders/{ref}/cancel',headers=headers).status_code==200
    assert client.put(url,json={'shipping_amount_ngn':0},headers=headers).status_code==409
    second=client.post('/api/v1/orders/drafts',headers=headers,json={
        'items':[{'product_id':'premium','size':'39','quantity':1}],
    }).json()['id']
    assert client.put(f'/api/v1/admin/orders/{second}/delivery-quote',
                      json={'shipping_amount_ngn':0},headers=headers).status_code==409
    with SessionLocal() as db:
        assert db.query(DeliveryQuoteAudit).count()==0
