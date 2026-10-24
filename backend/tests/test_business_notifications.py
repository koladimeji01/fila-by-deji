"""Stage 10: live, staff-scoped business alerts and persistent read acknowledgements."""
from datetime import timedelta
from app.database import SessionLocal
from app.models import (
    Order, ProductInventory, StaffNotificationRead, StaffApplication, User, utcnow
)


def grant_admin(client, auth, *, manager=False, email='ada@example.com'):
    h=auth(client,email=email)
    with SessionLocal() as db:
        actor=db.query(User).filter_by(email=email).one()
        actor.is_admin=True
        actor.can_manage_staff=manager
        db.commit()
    return h


def customer_enquiry(client, headers):
    response=client.post('/api/v1/orders/drafts', headers=headers,json={
        'items':[{'product_id':'premium','size':'39','quantity':1}],
        'delivery_destination':'Lagos, Nigeria'
    })
    assert response.status_code==201,response.text
    return response.json()['id']


def test_notifications_require_staff_access(client,auth):
    customer=auth(client)
    assert client.get('/api/v1/admin/notifications').status_code==401
    assert client.get('/api/v1/admin/notifications',headers=customer).status_code==403
    assert client.post('/api/v1/admin/notifications/read',
                       json={'key':'fake'}).status_code==401
    assert client.post('/api/v1/admin/notifications/read-all',
                       headers=customer).status_code==403


def test_manager_sees_pending_staff_and_reads_do_not_grant_permissions(client,auth):
    manager=grant_admin(client,auth,manager=True)
    signup=client.post('/api/v1/staff/register',json={
        'name':'New Fila Assistant','email':'applicant@example.com',
        'password':'long-unique-test-password-123'
    })
    assert signup.status_code==201,signup.text
    person=signup.json()
    feed=client.get('/api/v1/admin/notifications',headers=manager).json()
    key='staff:'+person['id']
    row=next(n for n in feed['notifications'] if n['key']==key)
    assert row['kind']=='staff' and row['destination']=='staff' and not row['is_read']
    assert feed['unread_count']>=1
    marked=client.post('/api/v1/admin/notifications/read',headers=manager,
                       json={'key':key})
    assert marked.status_code==200,marked.text
    marked_item=next(n for n in marked.json()['notifications'] if n['key']==key)
    assert marked_item['is_read'] is True
    assert client.get('/api/v1/admin/notifications',headers=manager).json()['unread_count']==0
    assert client.post('/api/v1/admin/notifications/read',headers=manager,
                       json={'key':key}).status_code==200
    with SessionLocal() as db:
        person_db=db.get(User,person['id'])
        assert person_db.is_admin is False
        assert person_db.can_manage_staff is False
        assert db.query(StaffNotificationRead).count()==1
        assert db.get(StaffApplication,person['id']).status=='pending'
    decided=client.post('/api/v1/admin/staff/'+person['id']+'/decision',
                        headers=manager,json={'action':'reject'})
    assert decided.status_code==200
    after=client.get('/api/v1/admin/notifications',headers=manager).json()
    assert key not in [n['key'] for n in after['notifications']]


def test_operational_staff_cannot_see_manager_notifications(client,auth):
    manager=grant_admin(client,auth,manager=True)
    regular=grant_admin(client,auth,email='operator@example.com')
    pending=client.post('/api/v1/staff/register',json={
        'name':'Pending Team','email':'pending@example.com',
        'password':'long-unique-test-password-123'
    }).json()
    manager_feed=client.get('/api/v1/admin/notifications',headers=manager).json()
    member_feed=client.get('/api/v1/admin/notifications',headers=regular).json()
    key='staff:'+pending['id']
    assert key in {x['key'] for x in manager_feed['notifications']}
    assert key not in {x['key'] for x in member_feed['notifications']}
    denied=client.post('/api/v1/admin/notifications/read',
                       headers=regular,json={'key':key})
    assert denied.status_code==404
    assert client.post('/api/v1/admin/notifications/read-all',headers=regular).status_code==200


def test_new_enquiry_and_low_stock_notifications_follow_live_state(client,auth):
    manager=grant_admin(client,auth)
    enquiry_id=customer_enquiry(client,manager)
    with SessionLocal() as db:
        db.get(ProductInventory,('classic','32')).quantity=2
        db.commit()
    feed=client.get('/api/v1/admin/notifications',headers=manager).json()
    kinds={item['kind'] for item in feed['notifications']}
    assert 'enquiry' in kinds and 'stock' in kinds
    order_key='enquiry:'+enquiry_id
    stock=next(x for x in feed['notifications']
               if x['kind']=='stock' and x['key'].startswith('stock:classic:32:'))
    assert stock['key']=='stock:classic:32:2'
    assert '2 available' in stock['detail']
    before=feed['unread_count']
    mark=client.post('/api/v1/admin/notifications/read',headers=manager,
                     json={'key':stock['key']}).json()
    assert mark['unread_count']==before-1
    with SessionLocal() as db:
        db.get(ProductInventory,('classic','32')).quantity=8
        db.commit()
    changed=client.get('/api/v1/admin/notifications',headers=manager).json()
    assert stock['key'] not in {x['key'] for x in changed['notifications']}
    updated=client.put('/api/v1/admin/orders/'+enquiry_id+'/followup',headers=manager,
                       json={'stage':'contacted','internal_note':'Responded by email'})
    assert updated.status_code==200,updated.text
    cleared=client.get('/api/v1/admin/notifications',headers=manager).json()
    assert order_key not in {x['key'] for x in cleared['notifications']}


def test_acknowledgements_are_individual_and_do_not_persist_into_new_quantity(client,auth):
    first=grant_admin(client,auth)
    second=grant_admin(client,auth,email='another@example.com')
    with SessionLocal() as db:
        db.get(ProductInventory,('premium','35')).quantity=3
        db.commit()
    key='stock:premium:35:3'
    initial=client.get('/api/v1/admin/notifications',headers=first).json()
    assert key in {n['key'] for n in initial['notifications']}
    marked=client.post('/api/v1/admin/notifications/read',headers=first,json={'key':key})
    assert marked.status_code==200
    other=client.get('/api/v1/admin/notifications',headers=second).json()
    assert next(n for n in other['notifications'] if n['key']==key)['is_read'] is False
    with SessionLocal() as db:
        db.get(ProductInventory,('premium','35')).quantity=1
        db.commit()
    new_key='stock:premium:35:1'
    new=client.get('/api/v1/admin/notifications',headers=first).json()
    assert next(n for n in new['notifications'] if n['key']==new_key)['is_read'] is False
    clear=client.post('/api/v1/admin/notifications/read-all',headers=first)
    assert clear.status_code==200 and clear.json()['unread_count']==0
    assert client.get('/api/v1/admin/notifications',headers=first).json()['unread_count']==0


def test_old_enquiries_are_not_shown_and_invalid_read_keys_rejected(client,auth):
    manager=grant_admin(client,auth)
    enquiry_id=customer_enquiry(client,manager)
    with SessionLocal() as db:
        db.get(Order,enquiry_id).created_at=utcnow()-timedelta(days=18)
        db.commit()
    feed=client.get('/api/v1/admin/notifications',headers=manager).json()
    assert 'enquiry:'+enquiry_id not in [n['key'] for n in feed['notifications']]
    for payload in ({'key':'unavailable:key'}, {'key':'x'}, {'key':'x'*141},
                    {'key':'other:key','is_admin':True}):
        r=client.post('/api/v1/admin/notifications/read',headers=manager,json=payload)
        assert r.status_code in (404,422),r.text
    with SessionLocal() as db:
        assert db.query(StaffNotificationRead).count()==0


def test_dashboard_has_private_notifications_centre_and_actions():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    html=(root/'admin-site'/'index.html').read_text(encoding='utf-8')
    js=(root/'admin-site'/'js'/'admin.js').read_text(encoding='utf-8')
    for identifier in (
        'admin-notifications-nav','admin-notifications-badge',
        'admin-notifications-list','admin-notifications-read-all',
        'admin-notifications-refresh','admin-notifications-section'
    ):
        assert 'id="'+identifier+'"' in html
    assert "apiRequest('/admin/notifications',{authorize:true})" in js
    assert "apiRequest('/admin/notifications/read'," in js
    assert "apiRequest('/admin/notifications/read-all'," in js
    assert "renderNotifications(result)" in js
    assert "loadNotifications()" in js
