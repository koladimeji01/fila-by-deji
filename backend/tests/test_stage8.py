"""Stage 8 protection and preflight tests (SQLite, no external services needed)."""
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.doctor import check_readiness
from app.rate_limit import match_rule


PROD = dict(app_env='production', jwt_secret_key='s' * 64,
            database_url='postgresql+psycopg://user:pass@db.example.com/fila?sslmode=require',
            cors_origins='https://shop.example.org')


def test_production_requires_shared_redis():
    with pytest.raises(ValidationError):
        Settings(**PROD, rate_limit_redis_url='', _env_file=None)
    with pytest.raises(ValidationError):
        Settings(**PROD, rate_limit_redis_url='redis://localhost:6379/0', _env_file=None)


def test_production_accepts_secure_services():
    s = Settings(**PROD, rate_limit_redis_url='rediss://redis.example.org:6380/0', _env_file=None)
    assert s.app_env == 'production'


def test_local_config_needs_no_redis():
    s = Settings(app_env='development', jwt_secret_key='s'*64,
                 rate_limit_redis_url='', _env_file=None)
    assert s.app_env == 'development'


def test_rate_limit_matchers_are_narrow():
    assert match_rule('POST', '/api/v1/auth/login') == 'login'
    assert match_rule('POST', '/api/v1/auth/register') == 'register'
    assert match_rule('POST', '/api/v1/orders/drafts') == 'draft'
    assert match_rule('POST', '/api/v1/orders/abc/reserve') == 'reserve'
    assert match_rule('PUT', '/api/v1/admin/inventory/premium/39') == 'admin-write'
    assert match_rule('GET', '/api/v1/products') is None
    assert match_rule('OPTIONS', '/api/v1/auth/login') is None
    assert match_rule('POST', '/api/v1/orders/abc/cancel') is None


def test_login_is_rate_limited(client):
    # One IP in TestClient, all failed logins count.
    for _ in range(10):
        assert client.post('/api/v1/auth/login',json={'email':'none@example.org','password':'wrong'}).status_code==401
    r=client.post('/api/v1/auth/login',json={'email':'none@example.org','password':'wrong'})
    assert r.status_code == 429
    assert int(r.headers['retry-after']) > 0
    assert r.headers['cache-control'] == 'no-store'
    assert client.get('/api/v1/products').status_code == 200


def test_signup_rate_limited(client):
    for _ in range(5):
        assert client.post('/api/v1/auth/register',json={'name':'X','email':'bad','password':'short'}).status_code==422
    r=client.post('/api/v1/auth/register',json={'name':'X','email':'bad','password':'short'})
    assert r.status_code == 429


def test_production_counter_failure_is_closed(client):
    fake = Settings(**PROD, rate_limit_redis_url='rediss://redis.example.org:6380/0', _env_file=None)
    with patch('app.rate_limit.get_settings', return_value=fake), patch(
            'app.rate_limit._redis_increment', side_effect=ConnectionError('service offline')):
        r = client.post('/api/v1/auth/login',json={'email':'none@example.org','password':'x'})
    assert r.status_code == 503
    assert r.json()['detail'] == 'Security service temporarily unavailable'
    assert r.headers['cache-control'] == 'no-store'


def test_preflight_passes_with_valid_test_schema(client):
    # The test fixture creates all tables directly, without running migrations;
    # stamp only the isolated TEST database to model a completed deployment.
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    ini = Path(__file__).resolve().parents[1] / 'alembic.ini'
    command.stamp(Config(str(ini)), 'head')
    assert check_readiness() == []


def test_preflight_rejects_unversioned_db(client):
    # Previous test may have stamped the shared isolated test database.
    from sqlalchemy import text
    from app.database import engine
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM alembic_version'))
    assert any('unversioned' in msg for msg in check_readiness())


def test_preflight_detects_missing_column(client,monkeypatch):
    # The same error caused by running Stage 7 code against a Stage 6 database.
    from app import doctor
    class DummyInspector:
        def get_table_names(self):
            return ['users','products','orders','order_items','product_inventory']
        def get_columns(self, table):
            table_cols = {
                'users': ['id', 'email', 'is_admin'],
                'products': ['id', 'price_kobo'],
                'orders': ['id', 'status'],
                'order_items': ['order_id', 'product_id'],
                'product_inventory': ['product_id', 'size', 'quantity'],
            }
            return [{'name':x} for x in table_cols[table]]
    monkeypatch.setattr(doctor,'inspect',lambda conn: DummyInspector())
    assert any('orders.reserved_until' in msg for msg in check_readiness())


def test_rate_limit_reply_has_cors_for_approved_site(client):
    for _ in range(10):
        client.post('/api/v1/auth/login',json={'email':'none@example.org','password':'wrong'})
    r=client.post('/api/v1/auth/login',json={'email':'none@example.org','password':'wrong'},
                  headers={'Origin':'http://localhost:5500'})
    assert r.status_code == 429
    assert r.headers.get('access-control-allow-origin') == 'http://localhost:5500'
