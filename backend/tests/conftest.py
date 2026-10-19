import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Hard isolate the test database and auth key from any developer environment.
_tmpdir = tempfile.TemporaryDirectory(prefix='fila-api-tests-')
os.environ['APP_ENV'] = 'test'
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_tmpdir.name) / 'test.db')
os.environ['JWT_SECRET_KEY'] = 'tests-only-secret-that-is-very-long-and-not-for-production'
os.environ['CORS_ORIGINS'] = 'http://localhost:5500'

from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models  # noqa: E402, F401
from app.main import app  # noqa: E402
from app.seed import seed_products  # noqa: E402


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_products(session)
    with TestClient(app) as api:
        yield api


def _auth(client, email='ada@example.com', password='a-great-long-secret-123'):
    response = client.post('/api/v1/auth/register', json={'name': 'Ada Example', 'email': email, 'password': password})
    assert response.status_code == 201, response.text
    login = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert login.status_code == 200
    return {'Authorization': 'Bearer ' + login.json()['access_token']}


@pytest.fixture
def auth():
    return _auth
