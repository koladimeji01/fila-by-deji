"""Admin-only real catalog creation and safe customer image URLs."""
import pytest
from app.database import SessionLocal
from app.models import Product, ProductInventory, User


def grant_admin(client, auth):
    headers = auth(client)
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin = True
        db.commit()
    return headers


def product_data(**changes):
    record = {
        'name': 'Heritage Gold Fila', 'category': 'Ceremonial',
        'description': 'Hand-finished Aso-oke fila made for special celebrations.',
        'price_ngn': 14000,
        'image_url': 'https://cdn.example.com/fila/heritage-gold.webp',
        'stock_by_size': {'32': 5, '35': 1, '39': 0, '41': 9},
        'is_active': True
    }
    return {**record, **changes}


def test_new_product_create_requires_verified_administrator(client, auth):
    regular = auth(client)
    path = '/api/v1/admin/products'
    assert client.post(path, json=product_data()).status_code == 401
    assert client.post(path, headers=regular, json=product_data()).status_code == 403
    assert len(client.get('/api/v1/products').json()) == 3


def test_admin_created_product_shows_in_store_and_has_size_inventory(client, auth):
    staff = grant_admin(client, auth)
    created = client.post('/api/v1/admin/products', headers=staff, json=product_data())
    assert created.status_code == 201, created.text
    product = created.json()
    assert product['name'] == 'Heritage Gold Fila'
    assert product['price_ngn'] == 14000
    assert product['image_url'] == product_data()['image_url']
    assert product['id'].startswith('heritage-gold-fila-')
    assert product['available_sizes'] == ['32', '35', '41']
    assert product['stock_by_size'] == {'32': 5, '35': 1, '39': 0, '41': 9}
    public = client.get('/api/v1/products').json()
    assert len(public) == 4
    assert any(p['id'] == product['id'] for p in public)
    assert client.get('/api/v1/products/'+product['id']).json()['image_url'] == product['image_url']
    with SessionLocal() as db:
        row = db.get(Product, product['id'])
        assert row and row.is_active
        assert db.get(ProductInventory, (product['id'], '39')).quantity == 0
    assert client.get('/api/v1/admin/overview', headers=staff).json()['active_products'] == 4


def test_new_products_can_be_drafts_then_published(client, auth):
    staff = grant_admin(client, auth)
    created = client.post('/api/v1/admin/products', headers=staff,
                          json=product_data(is_active=False, stock_by_size={}))
    assert created.status_code == 201, created.text
    item = created.json()
    assert item['is_active'] is False
    assert item['available_sizes'] == []
    assert set(item['stock_by_size']) == {'32', '35', '39', '41'}
    assert not any(p['id'] == item['id'] for p in client.get('/api/v1/products').json())
    assert client.get('/api/v1/products/'+item['id']).status_code == 404
    publish = client.put('/api/v1/admin/products/'+item['id'], headers=staff, json={
        'name': item['name'], 'category': item['category'], 'description': item['description'],
        'price_ngn': item['price_ngn'], 'is_active': True
    })
    assert publish.status_code == 200
    assert client.get('/api/v1/products/'+item['id']).status_code == 200


@pytest.mark.parametrize('updates', [
    {'price_ngn': -5},
    {'price_ngn': 2.5},
    {'price_ngn': 10000001},
    {'stock_by_size': {'40': 3}},
    {'stock_by_size': {'39': -3}},
    {'stock_by_size': {'32': 100001}},
    {'image_url': 'http://cdn.example.com/cap.jpg'},
    {'image_url': 'javascript:alert(1)'},
    {'image_url': 'https://localhost/cap.jpg'},
    {'image_url': 'https://127.0.0.1/cap.jpg'},
    {'image_url': 'https://cdn.example.com/cap.svg'},
    {'image_url': 'https://cdn.example.com/cap.jpg#fragment'},
    {'image_url': 'https://user:password@cdn.example.com/cap.jpg'},
    {'name': '    '},
    {'description': '  z  '},
    {'is_admin': True},
])
def test_admin_create_rejects_invalid_or_privilege_injected_data(client, auth, updates):
    staff = grant_admin(client, auth)
    bad = client.post('/api/v1/admin/products', headers=staff,
                      json=product_data(**updates))
    assert bad.status_code == 422, bad.text
    assert len(client.get('/api/v1/products').json()) == 3


def test_admin_create_allows_multiple_products_with_same_name_without_overwrite(client, auth):
    staff = grant_admin(client, auth)
    first = client.post('/api/v1/admin/products', headers=staff, json=product_data())
    second = client.post('/api/v1/admin/products', headers=staff, json=product_data())
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()['id'] != second.json()['id']


def test_admin_add_form_and_storefront_are_wired_together():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    page = (root / 'admin-site' / 'index.html').read_text(encoding='utf-8')
    admin_js = (root / 'admin-site' / 'js' / 'admin.js').read_text(encoding='utf-8')
    store_js = (root / 'js' / 'app.js').read_text(encoding='utf-8')
    for field in ('admin-open-add-product', 'admin-create-product', 'admin-new-name',
                  'admin-new-price', 'admin-new-image', 'admin-new-publish',
                  'admin-new-stock-32', 'admin-new-stock-35',
                  'admin-new-stock-39', 'admin-new-stock-41'):
        assert 'id="'+field+'"' in page
    assert "apiRequest('/admin/products',{method:'POST',authorize:true" in admin_js
    assert "image:catalogImage(p)" in store_js
    assert "['ceremonial','classic','premium'].includes(product.id)" in store_js
    assert "product.image_url===local" in store_js
