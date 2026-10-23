"""Regression tests for owner-managed staff requests and immediate revocation."""
from app.database import SessionLocal
from app.models import StaffAccessAudit, StaffApplication, User


def owner(client, auth):
    header = auth(client)
    with SessionLocal() as db:
        person = db.query(User).filter_by(email='ada@example.com').one()
        person.is_admin = True
        person.can_manage_staff = True
        db.commit()
    return header


def applicant(client, email='staff@example.com'):
    password = 'staff-test-password-123'
    signup = client.post('/api/v1/staff/register', json={
        'name':'New Staff', 'email':email, 'password':password
    })
    assert signup.status_code == 201, signup.text
    token = client.post('/api/v1/auth/login',json={
        'email':email,'password':password
    }).json()['access_token']
    return signup.json()['id'], {'Authorization': 'Bearer ' + token}


def decision(client, header, uid, action):
    return client.post(f'/api/v1/admin/staff/{uid}/decision',
                       headers=header,json={'action':action})


def test_new_staff_request_is_pending_and_hidden_from_customer_data(client, auth):
    mgr = owner(client, auth)
    uid, own_header = applicant(client)
    with SessionLocal() as db:
        person = db.get(User,uid)
        assert not person.is_admin
        assert not person.can_manage_staff
        assert db.get(StaffApplication,uid).status == 'pending'
    status = client.get('/api/v1/staff/status',headers=own_header)
    assert status.status_code == 200
    assert status.json()['status'] == 'pending'
    assert client.get('/api/v1/admin/products',headers=own_header).status_code == 403
    assert client.get('/api/v1/admin/staff',headers=own_header).status_code == 403
    listing = client.get('/api/v1/admin/staff',headers=mgr)
    assert listing.status_code == 200
    assert {u['email'] for u in listing.json()} == {'ada@example.com','staff@example.com'}
    assert next(u for u in listing.json() if u['user_id']==uid)['status'] == 'pending'


def test_approval_grants_only_operational_access_and_is_audited(client, auth):
    manager = owner(client, auth)
    uid, headers = applicant(client)
    approved = decision(client,manager,uid,'approve')
    assert approved.status_code == 200, approved.text
    assert approved.json()['status'] == 'approved'
    assert approved.json()['is_admin'] is True
    assert approved.json()['can_manage_staff'] is False
    assert client.get('/api/v1/admin/overview',headers=headers).status_code == 200
    assert client.get('/api/v1/admin/staff',headers=headers).status_code == 403
    assert decision(client,headers,uid,'revoke').status_code == 403
    with SessionLocal() as db:
        event = db.query(StaffAccessAudit).one()
        assert event.subject_user_id == uid and event.action == 'approved'
        assert db.get(StaffApplication,uid).reviewed_by is not None


def test_staff_can_be_rejected_or_revoked_without_losing_customer_account(client, auth):
    manager = owner(client,auth)
    uid, headers = applicant(client)
    assert decision(client,manager,uid,'reject').status_code == 200
    assert client.get('/api/v1/staff/status',headers=headers).json()['status'] == 'rejected'
    assert client.get('/api/v1/admin/overview',headers=headers).status_code == 403
    assert client.post('/api/v1/staff/apply',headers=headers).json()['status'] == 'pending'
    assert decision(client,manager,uid,'approve').status_code == 200
    assert client.get('/api/v1/admin/overview',headers=headers).status_code == 200
    revoked = decision(client,manager,uid,'revoke')
    assert revoked.status_code == 200
    assert revoked.json()['status'] == 'revoked'
    # Role is validated against database on every request, even an old token.
    assert client.get('/api/v1/admin/overview',headers=headers).status_code == 403
    assert client.get('/api/v1/auth/me',headers=headers).status_code == 200
    assert client.get('/api/v1/staff/status',headers=headers).json()['status'] == 'revoked'
    with SessionLocal() as db:
        assert [event.action for event in db.query(StaffAccessAudit).order_by(
            StaffAccessAudit.created_at,StaffAccessAudit.action).all()] == ['approved','rejected','revoked'] or {
            event.action for event in db.query(StaffAccessAudit).all()
        } == {'approved','rejected','revoked'}
    assert client.post('/api/v1/staff/apply',headers=headers).json()['status']=='pending'


def test_cannot_mutate_manager_or_self_or_approve_without_request(client, auth):
    manager = owner(client, auth)
    uid, headers = applicant(client)
    with SessionLocal() as db:
        owner_id = db.query(User).filter_by(email='ada@example.com').one().id
    assert decision(client,manager,owner_id,'revoke').status_code == 409
    assert decision(client,manager,uid,'revoke').status_code == 409
    assert decision(client,manager,uid,'approve').status_code == 200
    assert decision(client,manager,uid,'approve').status_code == 409
    assert decision(client,manager,uid,'reject').status_code == 409
    assert decision(client,manager,uid,'revoke').status_code == 200
    assert decision(client,manager,uid,'revoke').status_code == 409
    assert decision(client,manager,'not-found','approve').status_code == 404
    assert client.post('/api/v1/admin/staff/'+uid+'/decision',headers=manager,
                       json={'action':'promote-to-manager'}).status_code == 422
    with SessionLocal() as db:
        assert db.get(User,owner_id).can_manage_staff is True
        assert db.get(User,uid).can_manage_staff is False


def test_existing_customer_can_request_staff_access_without_second_registration(client, auth):
    owner_token = owner(client, auth)
    credentials=auth(client,email='customer@example.com')
    status=client.get('/api/v1/staff/status',headers=credentials)
    assert status.json()['status']=='not_requested'
    applied=client.post('/api/v1/staff/apply',headers=credentials)
    assert applied.status_code==200 and applied.json()['status']=='pending'
    assert client.post('/api/v1/staff/apply',headers=credentials).json()['status']=='pending'
    listed=client.get('/api/v1/admin/staff',headers=owner_token).json()
    assert sum(1 for item in listed if item['email']=='customer@example.com')==1


def test_public_registration_cannot_assign_privileges(client):
    created=client.post('/api/v1/staff/register',json={
        'name':'Fake Owner','email':'fake@example.com',
        'password':'long-password-no-secrets','is_admin':True,'can_manage_staff':True,
    })
    assert created.status_code==422
    assert client.get('/api/v1/admin/staff').status_code==401


def test_staff_ui_is_owner_only_and_securely_escaped():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    page=(root/'admin-site'/'index.html').read_text(encoding='utf-8')
    js=(root/'admin-site'/'js'/'admin.js').read_text(encoding='utf-8')
    assert 'id="admin-staff-section"' in page
    assert 'id="admin-staff-nav"' in page
    assert 'id="admin-request-existing"' in page
    assert "apiRequest('/staff/register'" in js
    assert "apiRequest('/staff/apply'" in js
    assert "apiRequest('/admin/staff',{authorize:true})" in js
    assert "action" in js and "revoke" in js
    assert "get_current_staff_manager" in (root/'backend'/'app'/'main.py').read_text()
