"""Business signup creates ordinary accounts, not administrator access."""
from pathlib import Path
from app.database import SessionLocal
from app.models import User

ROOT = Path(__file__).resolve().parents[2]


def test_business_signup_form_is_present_and_uses_existing_registration_api():
    page = (ROOT / 'admin-site' / 'index.html').read_text(encoding='utf-8')
    script = (ROOT / 'admin-site' / 'js' / 'admin.js').read_text(encoding='utf-8')
    for target in (
        'admin-show-signup', 'admin-show-login', 'admin-signup',
        'admin-signup-form', 'admin-signup-name', 'admin-signup-email',
        'admin-signup-password', 'admin-signup-confirm',
        'admin-signup-feedback', 'admin-signup-submit',
    ):
        assert f'id="{target}"' in page
    assert 'minlength="12"' in page
    assert "apiRequest('/staff/register'" in script
    assert "body:{name,email,password}" in script
    assert 'password!==confirmation' in script
    assert "showAuthPanel('signup')" in script
    assert "showAuthPanel('login')" in script
    signup_handler = script.split('async function submitSignup(event){', 1)[1].split('async function verified(){', 1)[0]
    assert 'storeToken(' not in signup_handler
    assert 'is_admin' not in signup_handler
    assert "apiRequest('/admin/overview',{authorize:true})" in script


def test_new_business_signup_cannot_access_admin_until_explicit_approval(client):
    request = {
        'name': 'New Team Member',
        'email': 'newstaff@example.com',
        'password': 'strong-long-secret-12345',
    }
    created = client.post('/api/v1/staff/register', json=request)
    assert created.status_code == 201, created.text
    login = client.post('/api/v1/auth/login', json={
        'email': request['email'], 'password': request['password']
    })
    assert login.status_code == 200
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    assert client.get('/api/v1/admin/overview', headers=headers).status_code == 403
    assert client.get('/api/v1/admin/products', headers=headers).status_code == 403
    with SessionLocal() as db:
        from app.models import StaffApplication
        user = db.query(User).filter_by(email=request['email']).one()
        assert user.is_active
        assert not user.is_admin
        assert not user.can_manage_staff
        assert db.get(StaffApplication,user.id).status == 'pending'
    rejected = client.post('/api/v1/auth/register', json={
        'name': 'Intruder',
        'email': 'anotherstaff@example.com',
        'password': request['password'],
        'is_admin': True,
    })
    assert rejected.status_code == 422
