"""Production configuration hardening and deployment artifact regressions."""
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def secure(**overrides):
    values = {
        'app_env': 'production',
        'jwt_secret_key': 'very-long-production-test-only-token-' + 'x' * 40,
        'database_url': 'postgresql+psycopg://fila:encoded-pass@db.example.com:5432/fila?sslmode=require',
        'rate_limit_redis_url': 'rediss://redis.example.com:6380/0',
        'cors_origins': 'https://shop.example.com',
        '_env_file': None,
    }
    values.update(overrides)
    return Settings(**values)


def test_secure_production_config_is_accepted():
    assert secure().app_env == 'production'


@pytest.mark.parametrize('url', [
    'postgresql+psycopg://u:p@db.example.com:5432/fila',
    'postgresql+psycopg://u:p@db.example.com:5432/fila?sslmode=disable',
    'postgresql+psycopg://u:p@db.example.com:5432/fila?sslmode=prefer',
])
def test_production_rejects_db_without_required_tls(url):
    with pytest.raises(ValidationError, match='sslmode'):
        secure(database_url=url)


@pytest.mark.parametrize('origin', [
    'https://localhost:5500',
    'https://127.0.0.1:5500',
    'http://shop.example.com',
    'https://shop.example.com/some/path',
    'https://shop.example.com?tracking=1',
    'https://*.example.com',
    '',
])
def test_production_rejects_unsafe_or_invalid_frontend_origin(origin):
    with pytest.raises(ValidationError):
        secure(cors_origins=origin)


def test_prod_without_encrypted_redis_is_rejected():
    with pytest.raises(ValidationError):
        secure(rate_limit_redis_url='redis://redis.example.com/0')


def test_docker_image_excludes_secrets_and_does_not_run_automatic_migration():
    dockerfile = (ROOT / 'backend/Dockerfile').read_text()
    ignore = (ROOT / 'backend/.dockerignore').read_text()
    script = (ROOT / 'backend/scripts/start-api.sh').read_text()
    assert 'USER fila' in dockerfile
    assert '.env' in ignore and '*.db' in ignore and 'tests/' in ignore
    assert 'alembic upgrade' not in script
    assert 'python -m app.doctor' in script
    assert '--no-proxy-headers' in script


def test_ci_tests_site_and_backend():
    yaml = (ROOT / '.github/workflows/backend-ci.yml').read_text()
    assert 'pytest -q' in yaml
    assert 'node --check js/app.js' in yaml
