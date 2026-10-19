import pytest
from pydantic import ValidationError
from app.config import Settings


def test_rejects_weak_secret():
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key='abc', _env_file=None)


def test_rejects_production_sqlite():
    with pytest.raises(ValidationError):
        Settings(app_env='production', jwt_secret_key='z'*64, database_url='sqlite:///./production.db',
                 cors_origins='https://fila.example', _env_file=None)


def test_rejects_insecure_production_origin():
    with pytest.raises(ValidationError):
        Settings(app_env='production', jwt_secret_key='z'*64,
                 database_url='postgresql+psycopg://user:password@localhost:5432/fila',
                 cors_origins='http://fila.example', _env_file=None)
