"""Regressions for inventory and private draft-order history."""
import pytest
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models import ProductInventory


def draft(product_id='premium', size='39', quantity=1):
    return {'items': [{'product_id': product_id, 'size': size, 'quantity': quantity}]}


def test_catalog_advertises_only_available_sizes(client):
    assert client.get('/api/v1/products/premium').json()['available_sizes'] == ['32', '35', '39', '41']
    with SessionLocal() as db:
        row = db.get(ProductInventory, ('premium', '39'))
        row.quantity = 0
        db.commit()
    result = client.get('/api/v1/products/premium').json()
    assert result['available_sizes'] == ['32', '35', '41']
    product = next(x for x in client.get('/api/v1/products').json() if x['id'] == 'premium')
    assert '39' not in product['available_sizes']


def test_out_of_stock_size_fails_closed(client, auth):
    h = auth(client)
    with SessionLocal() as db:
        db.get(ProductInventory, ('premium', '39')).quantity = 0
        db.commit()
    unavailable = client.post('/api/v1/orders/drafts', json=draft(), headers=h)
    assert unavailable.status_code == 409
    assert client.get('/api/v1/orders', headers=h).json() == []


def test_quantity_is_checked_against_size_stock(client, auth):
    h = auth(client)
    with SessionLocal() as db:
        db.get(ProductInventory, ('premium', '39')).quantity = 3
        db.commit()
    assert client.post('/api/v1/orders/drafts', json=draft(quantity=4), headers=h).status_code == 409
    ok = client.post('/api/v1/orders/drafts', json=draft(quantity=3), headers=h)
    assert ok.status_code == 201
    # Drafts never reserve/decrement inventory or mark the order as paid.
    assert ok.json()['status'] == 'draft'
    assert client.post('/api/v1/orders/drafts', json=draft(quantity=3), headers=h).status_code == 201
    with SessionLocal() as db:
        assert db.get(ProductInventory, ('premium', '39')).quantity == 3


def test_composite_inventory_constraint(client):
    with SessionLocal() as db:
        db.get(ProductInventory, ('premium', '39')).quantity = -1
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_order_history_is_private_and_paginated(client, auth):
    owner = auth(client)
    other = auth(client, email='second@example.com')
    ids = []
    for _ in range(4):
        res = client.post('/api/v1/orders/drafts', json=draft(), headers=owner)
        assert res.status_code == 201
        ids.append(res.json()['id'])
    assert client.get('/api/v1/orders', headers=other).json() == []
    assert client.get('/api/v1/orders', headers=owner).status_code == 200
    first = client.get('/api/v1/orders?limit=2&offset=0', headers=owner).json()
    second = client.get('/api/v1/orders?limit=2&offset=2', headers=owner).json()
    assert len(first) == len(second) == 2
    assert {x['id'] for x in first + second} == set(ids)
    assert client.get(f'/api/v1/orders/{ids[0]}', headers=other).status_code == 404
    assert client.get('/api/v1/orders?limit=0', headers=owner).status_code == 422
    assert client.get('/api/v1/orders?limit=101', headers=owner).status_code == 422
    assert client.get('/api/v1/orders?offset=-1', headers=owner).status_code == 422


def test_private_responses_not_cacheable(client, auth):
    h = auth(client)
    assert client.get('/api/v1/orders', headers=h).headers['cache-control'] == 'no-store'
    assert client.get('/api/v1/auth/me', headers=h).headers['cache-control'] == 'no-store'
    assert client.get('/api/v1/products').headers['x-content-type-options'] == 'nosniff'
