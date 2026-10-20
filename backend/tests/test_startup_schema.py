"""Avoid Stage 7-style 500s by checking migrations before the API starts."""
import asyncio
from unittest.mock import patch
import pytest
from app import main


def test_startup_fails_with_actionable_schema_error(monkeypatch):
    monkeypatch.setattr(main.settings, 'app_env', 'development')
    async def startup():
        async with main.lifespan(main.app):
            pass
    with patch('app.doctor.check_readiness', return_value=['orders.reserved_until missing']):
        with pytest.raises(RuntimeError, match='orders.reserved_until missing'):
            asyncio.run(startup())


def test_test_environment_skips_alembic_revision_check(monkeypatch):
    monkeypatch.setattr(main.settings, 'app_env', 'test')
    async def startup():
        async with main.lifespan(main.app):
            return None
    with patch('app.doctor.check_readiness') as check:
        asyncio.run(startup())
    check.assert_not_called()
