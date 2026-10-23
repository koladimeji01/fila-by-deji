"""The Render ingress must isolate real users without trusting spoofed XFF."""
import asyncio
from collections import Counter
from types import SimpleNamespace

from fastapi import Request
from fastapi.responses import Response

from app import rate_limit
from app.config import Settings


def production_settings(**extra):
    options = {
        'app_env': 'production',
        'jwt_secret_key': 'test-only-secret-key-long-enough-for-tests-1234',
        'database_url': 'postgresql+psycopg://test:test@localhost/test?sslmode=require',
        'cors_origins': 'https://fila-by-deji.vercel.app',
        'rate_limit_redis_url': 'rediss://localhost:6380/0',
        'rate_limit_trust_render_client_ip': True,
        '_env_file': None,
    }
    options.update(extra)
    return Settings(**options)


def make_request(address='8.8.8.8', xff='1.2.3.4', socket='127.0.0.1'):
    headers = [
        (b'host', b'fila-by-deji-api.onrender.com'),
        (b'x-forwarded-for', xff.encode()),
        (b'cf-connecting-ip', address.encode()),
    ]
    return Request({
        'type': 'http',
        'method': 'POST',
        'path': '/api/v1/auth/login',
        'raw_path': b'/api/v1/auth/login',
        'headers': headers,
        'query_string': b'',
        'client': (socket, 12345),
        'server': ('127.0.0.1', 8000),
        'scheme': 'http',
        'http_version': '1.1',
    })


def test_explicit_render_trust_prevents_shared_proxy_limit():
    settings = production_settings()
    assert rate_limit.client_rate_limit_identity(make_request('8.8.8.8'), settings) == '8.8.8.8'
    assert rate_limit.client_rate_limit_identity(make_request('1.1.1.1'), settings) == '1.1.1.1'
    assert rate_limit.client_rate_limit_identity(
        make_request('8.8.8.8', xff='6.6.6.6, 7.7.7.7'), settings) == '8.8.8.8'
    off = production_settings(rate_limit_trust_render_client_ip=False)
    assert rate_limit.client_rate_limit_identity(make_request(), off) == '127.0.0.1'
    dev = SimpleNamespace(app_env='test', rate_limit_trust_render_client_ip=True)
    assert rate_limit.client_rate_limit_identity(make_request(), dev) == '127.0.0.1'


def test_untrusted_or_malformed_cf_header_never_becomes_redis_identity():
    settings = production_settings()
    for bad in ('', '8.8.8.8, 1.1.1.1', '8.8.8.8 ', '127.0.0.1',
                '10.0.0.1', 'not-an-ip', '[2606:4700:4700::1111]:443'):
        assert rate_limit.client_rate_limit_identity(make_request(bad), settings) == '127.0.0.1'
    assert rate_limit.client_rate_limit_identity(make_request('2606:4700:4700::1111'),settings) == '2606:4700:4700::1111'


def test_two_visitors_get_independent_redis_rate_limit_buckets(monkeypatch):
    monkeypatch.setattr(rate_limit, 'get_settings', lambda: production_settings())
    monkeypatch.setattr(rate_limit.time, 'time', lambda: 3600)
    counts = Counter()

    def fake_redis_increment(url, key, ttl):
        counts[key] += 1
        return counts[key]

    monkeypatch.setattr(rate_limit, '_redis_increment', fake_redis_increment)

    async def pass_through(request):
        return Response(status_code=200)

    async def check(ip, forged_xff='9.9.9.9'):
        return await rate_limit.limit_request(make_request(ip, xff=forged_xff),pass_through)

    async def scenario():
        for i in range(10):
            assert (await check('8.8.8.8')).status_code == 200
        assert (await check('8.8.8.8',forged_xff='4.4.4.4')).status_code == 429
        assert (await check('1.1.1.1')).status_code == 200
        assert len(counts) == 2

    asyncio.run(scenario())
