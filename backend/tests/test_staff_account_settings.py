"""Stage 11: secure staff self-service account details and password rotation."""
from app.database import SessionLocal
from app.models import User
from app.security import verify_password


def manager_session(client, auth):
    header=auth(client)
    with SessionLocal() as db:
        user=db.query(User).filter_by(email='ada@example.com').one()
        user.is_admin=True
        user.can_manage_staff=True
        db.commit()
    return header


def test_staff_can_edit_own_display_name_without_role_or_email_changes(client,auth):
    staff=manager_session(client,auth)
    another=auth(client,email='other@example.com')
    endpoint='/api/v1/admin/account/profile'
    assert client.put(endpoint,json={'name':'New Name'}).status_code==401
    assert client.put(endpoint,headers=another,json={'name':'Other Name'}).status_code==403
    response=client.put(endpoint,headers=staff,json={'name':'  Senior    Team  Member  '})
    assert response.status_code==200,response.text
    assert response.json()['name']=='Senior Team Member'
    assert response.json()['email']=='ada@example.com'
    assert 'is_admin' not in response.json()
    with SessionLocal() as db:
        owner=db.query(User).filter_by(email='ada@example.com').one()
        assert owner.name=='Senior Team Member'
        assert owner.is_admin and owner.can_manage_staff
        assert owner.auth_version==0
        assert db.query(User).filter_by(email='other@example.com').one().name=='Ada Example'


def test_staff_name_validation_prevents_privilege_or_account_injection(client,auth):
    admin=manager_session(client,auth)
    url='/api/v1/admin/account/profile'
    for body in (
        {'name':' '},
        {'name':'x'},
        {'name':'X'*101},
        {'name':'Updated Staff','is_admin':False},
        {'name':'Updated Staff','can_manage_staff':False},
        {'name':'Updated Staff','email':'bad@example.com'},
        {'user_id':'unknown','name':'Changed'},
    ):
        r=client.put(url,headers=admin,json=body)
        assert r.status_code==422,r.text
    with SessionLocal() as db:
        user=db.query(User).filter_by(email='ada@example.com').one()
        assert user.name=='Ada Example'
        assert user.is_admin and user.can_manage_staff


def test_password_change_rejects_wrong_old_password_without_logging_out(client,auth):
    admin=manager_session(client,auth)
    url='/api/v1/admin/account/password'
    wrong=client.post(url,headers=admin,json={
        'current_password':'not-the-real-password',
        'new_password':'the-better-password-456'
    })
    assert wrong.status_code==400,wrong.text
    assert 'password_hash' not in wrong.text
    assert client.get('/api/v1/admin/overview',headers=admin).status_code==200
    with SessionLocal() as db:
        user=db.query(User).filter_by(email='ada@example.com').one()
        assert user.auth_version==0
        assert verify_password('a-great-long-secret-123',user.password_hash)


def test_password_change_rotates_token_and_expires_all_previous_sessions(client,auth):
    admin=manager_session(client,auth)
    previous=client.post('/api/v1/auth/login',json={
        'email':'ada@example.com','password':'a-great-long-secret-123'
    })
    assert previous.status_code==200
    old_other={'Authorization':'Bearer '+previous.json()['access_token']}
    result=client.post('/api/v1/admin/account/password',headers=admin,json={
        'current_password':'a-great-long-secret-123',
        'new_password':'a-new-long-staff-password-4321'
    })
    assert result.status_code==200,result.text
    data=result.json()
    assert data['token_type']=='bearer'
    assert data['access_token'] != admin['Authorization'].split(' ',1)[1]
    fresh={'Authorization':'Bearer '+data['access_token']}
    assert client.get('/api/v1/admin/overview',headers=admin).status_code==401
    assert client.get('/api/v1/admin/overview',headers=old_other).status_code==401
    assert client.get('/api/v1/admin/overview',headers=fresh).status_code==200
    failed=client.post('/api/v1/auth/login',json={
        'email':'ada@example.com','password':'a-great-long-secret-123'
    })
    assert failed.status_code==401
    new_login=client.post('/api/v1/auth/login',json={
        'email':'ada@example.com','password':'a-new-long-staff-password-4321'
    })
    assert new_login.status_code==200
    newer={'Authorization':'Bearer '+new_login.json()['access_token']}
    assert client.get('/api/v1/admin/overview',headers=newer).status_code==200
    with SessionLocal() as db:
        user=db.query(User).filter_by(email='ada@example.com').one()
        assert user.is_admin and user.can_manage_staff
        assert user.auth_version==1
        assert verify_password('a-new-long-staff-password-4321',user.password_hash)
        assert not verify_password('a-great-long-secret-123',user.password_hash)


def test_password_change_rejects_weak_same_or_extra_properties(client,auth):
    staff=manager_session(client,auth)
    url='/api/v1/admin/account/password'
    cases=[
        {'current_password':'a-great-long-secret-123','new_password':'short'},
        {'current_password':'a-great-long-secret-123','new_password':'a-great-long-secret-123'},
        {'current_password':'a-great-long-secret-123','new_password':'n'*129},
        {'current_password':'a-great-long-secret-123','new_password':'valid-long-secret-123','is_admin':True},
        {'current_password':'a-great-long-secret-123','new_password':'valid-long-secret-123','auth_version':100},
    ]
    for body in cases:
        response=client.post(url,headers=staff,json=body)
        assert response.status_code==422,response.text
    with SessionLocal() as db:
        user=db.query(User).filter_by(email='ada@example.com').one()
        assert user.auth_version==0


def test_staff_settings_html_preserved_and_connected():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    html=(root/'admin-site'/'index.html').read_text(encoding='utf-8')
    javascript=(root/'admin-site'/'js'/'admin.js').read_text(encoding='utf-8')
    for element in (
        'admin-settings-signout','admin-profile-form','admin-profile-name',
        'admin-profile-feedback','admin-password-form','admin-current-password',
        'admin-new-password','admin-confirm-password','admin-password-feedback',
        'admin-password-save'
    ):
        assert f'id="{element}"' in html
    assert "apiRequest('/admin/account/profile'" in javascript
    assert "apiRequest('/admin/account/password'" in javascript
    assert "storeToken(result.access_token)" in javascript
    assert "'password'" in html or 'type="password"' in html
