"""Stage 7: private staff enquiry workflow never changes unpaid financial state."""
from app.database import SessionLocal
from app.models import EnquiryFollowup, Order, ProductInventory, User


def create_order(client, auth):
    owner = auth(client)
    created = client.post('/api/v1/orders/drafts', headers=owner, json={
        'items': [{'product_id': 'premium', 'size': '39', 'quantity': 1}],
        'delivery_destination': 'Ikeja, Lagos',
    })
    assert created.status_code == 201, created.text
    return owner, created.json()['id']


def promote():
    with SessionLocal() as session:
        session.query(User).filter_by(email='ada@example.com').one().is_admin = True
        session.commit()


def followup(client, ref, headers=None, status='contacted', note='Asked about delivery location.'):
    return client.put('/api/v1/admin/orders/'+ref+'/followup', headers=headers,
                      json={'stage':status,'internal_note':note})


def test_followup_requires_staff_permissions_and_never_leaks_to_customers(client, auth):
    customer, order_id = create_order(client, auth)
    url='/api/v1/admin/orders/'+order_id+'/followup'
    assert followup(client,order_id).status_code == 401
    assert followup(client,order_id,customer).status_code == 403
    promote()
    data = followup(client,order_id,customer,note='Private call about delivery').json()
    assert data['followup_stage'] == 'contacted'
    assert data['internal_note'] == 'Private call about delivery'
    assert data['followup_updated_at'] is not None
    assert data['status'] == 'draft'
    listing = client.get('/api/v1/admin/orders',headers=customer).json()
    assert listing[0]['internal_note'] == 'Private call about delivery'
    assert listing[0]['followup_stage'] == 'contacted'
    public = client.get('/api/v1/orders/'+order_id,headers=customer).json()
    assert 'internal_note' not in public and 'followup_stage' not in public
    assert 'followup_updated_at' not in public
    assert public['status'] == 'draft'
    assert public['total_ngn'] == 10000
    with SessionLocal() as db:
        assert db.get(Order,order_id).status == 'draft'
        assert db.get(ProductInventory,('premium','39')).quantity == 8
        assert db.get(EnquiryFollowup,order_id).updated_by == db.query(User).filter_by(email='ada@example.com').one().id


def test_followup_status_changes_are_private_and_idempotent(client, auth):
    owner, ref = create_order(client,auth)
    promote()
    no_note = client.get('/api/v1/admin/orders',headers=owner).json()[0]
    assert no_note['followup_stage'] == 'new'
    assert no_note['internal_note'] == ''
    assert no_note['followup_updated_at'] is None
    for stage in ('contacted','awaiting_reply','closed','new'):
        result = followup(client,ref,owner,status=stage,note='Talked to the customer')
        assert result.status_code == 200,result.text
        assert result.json()['followup_stage'] == stage
        assert result.json()['status'] == 'draft'
    unchanged = followup(client,ref,owner,status='new',note='Talked to the customer')
    assert unchanged.status_code == 200
    assert unchanged.json()['followup_updated_at'] is not None
    assert client.get('/api/v1/orders/'+ref,headers=owner).json()['status']=='draft'


def test_followup_rejects_invalid_fields_and_nonexistent_refs(client,auth):
    owner,ref = create_order(client,auth)
    promote()
    path='/api/v1/admin/orders/'+ref+'/followup'
    for payload in (
        {'stage':'paid','internal_note':'No payments allowed'},
        {'stage':'shipped','internal_note':'Not allowed'},
        {'stage':'new','internal_note':'a'*1201},
        {'stage':'new','internal_note':'Invalid\x00character'},
        {'stage':'new','internal_note':'note','status':'paid'},
        {'stage':'new','internal_note':'note','total_ngn':0},
        {'stage':'new','internal_note':'note','is_admin':True},
        {'stage':'new'},
    ):
        rejected=client.put(path,headers=owner,json=payload)
        assert rejected.status_code==422,rejected.text
    assert followup(client,'does-not-exist',owner).status_code==404
    with SessionLocal() as db:
        assert db.get(EnquiryFollowup,ref) is None


def test_followup_on_cancelled_order_does_not_change_customer_cancel_status(client,auth):
    owner,ref=create_order(client,auth)
    promote()
    cancelled=client.post('/api/v1/orders/'+ref+'/cancel',headers=owner)
    assert cancelled.status_code==200
    updated=followup(client,ref,owner,status='closed',note='Customer no longer interested')
    assert updated.status_code==200,updated.text
    assert updated.json()['status']=='cancelled'
    assert client.get('/api/v1/orders/'+ref,headers=owner).json()['status']=='cancelled'
    with SessionLocal() as db:
        assert db.get(ProductInventory,('premium','39')).quantity==8


def test_staff_enquiry_ui_has_filters_and_private_note_editor():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    html=(root/'admin-site'/'index.html').read_text(encoding='utf-8')
    js=(root/'admin-site'/'js'/'admin.js').read_text(encoding='utf-8')
    assert 'id="admin-enquiry-search"' in html
    assert 'id="admin-enquiry-stage-filter"' in html
    assert "admin-followup-form" in js
    assert "'/followup'" in js
    assert 'internal_note' in js
    assert 'renderVisibleOrders()' in js
    assert 'loadedOrders' in js
    assert "Only" not in '' # Placeholder for future markup-only assertions
