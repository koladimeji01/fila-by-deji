"""Saved for later is private, idempotent, and never reserves inventory."""
from app.database import SessionLocal
from app.models import ProductInventory, Product


def test_saved_items_per_user_permissions_and_idempotence(client, auth):
    owner=auth(client)
    other=auth(client,email='other@example.com')
    url='/api/v1/saved-items/premium/39'
    assert client.get('/api/v1/saved-items').status_code==401
    assert client.put(url,json={'quantity':2}).status_code==401
    created=client.put(url,json={'quantity':2},headers=owner)
    assert created.status_code==200
    assert created.json()['quantity']==2
    assert created.json()['unit_price_ngn']==10000
    assert created.json()['available_quantity']==8
    assert client.get('/api/v1/saved-items',headers=other).json()==[]
    assert client.delete(url,headers=other).status_code==204
    assert len(client.get('/api/v1/saved-items',headers=owner).json())==1
    second=client.put(url,json={'quantity':3},headers=owner)
    assert second.status_code==200
    assert len(client.get('/api/v1/saved-items',headers=owner).json())==1
    assert second.json()['quantity']==3
    assert client.delete(url,headers=owner).status_code==204
    assert client.delete(url,headers=owner).status_code==204
    assert client.get('/api/v1/saved-items',headers=owner).json()==[]


def test_wishlist_does_not_reserve_stock_or_create_orders(client, auth):
    user=auth(client)
    with SessionLocal() as db:
        db.get(ProductInventory,('classic','32')).quantity=0
        db.commit()
    result=client.put('/api/v1/saved-items/classic/32',headers=user,json={'quantity':4})
    assert result.status_code==200
    assert result.json()['available_quantity']==0
    with SessionLocal() as db:
        assert db.get(ProductInventory,('classic','32')).quantity==0
    assert client.get('/api/v1/orders',headers=user).json()==[]


def test_invalid_saved_item_payload_and_inactive_products(client, auth):
    h=auth(client)
    base='/api/v1/saved-items/premium/39'
    for qty in (0,11,-1):
        assert client.put(base,headers=h,json={'quantity':qty}).status_code==422
    assert client.put('/api/v1/saved-items/premium/99',headers=h,json={'quantity':1}).status_code==422
    assert client.put('/api/v1/saved-items/missing/39',headers=h,json={'quantity':1}).status_code==404
    with SessionLocal() as db:
        db.get(Product,'premium').is_active=False
        db.commit()
    assert client.put(base,headers=h,json={'quantity':1}).status_code==404


def test_catalog_includes_exact_available_stock_quantities(client):
    response=client.get('/api/v1/products')
    assert response.status_code==200
    assert response.json()[0]['stock_by_size']=={'32':8,'35':8,'39':8,'41':8}
    with SessionLocal() as db:
        db.get(ProductInventory,('premium','39')).quantity=2
        db.commit()
    single=client.get('/api/v1/products/premium').json()
    assert single['stock_by_size']['39']==2
    assert '39' in single['available_sizes']
