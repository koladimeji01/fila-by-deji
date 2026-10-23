from functools import lru_cache
import re
from typing import Literal
from urllib.parse import parse_qs, urlsplit
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def is_render_private_redis_url(url: str) -> bool:
    """Permit plaintext Redis only for Render's private Key Value DNS and port.

    The web service and Key Value must share a Render workspace and region.
    Never allow an arbitrary redis:// URL in production.
    """
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == 'redis'
            and parsed.hostname is not None
            and re.fullmatch(r'red-[a-z0-9]{6,40}', parsed.hostname) is not None
            and parsed.port == 6379
            and parsed.path in ('', '/', '/0')
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: Literal['development', 'test', 'production'] = 'development'
    database_url: str = 'sqlite:///./fila_local.db'
    jwt_secret_key: str  # no default secret, fails closed if missing
    access_token_minutes: int = 30
    cors_origins: str = 'http://127.0.0.1:5500,http://localhost:5500'
    rate_limit_redis_url: str = ''  # Required in production
    rate_limit_allow_render_private_redis: bool = False  # Explicit opt-in for Render private-network Redis
    rate_limit_trust_render_client_ip: bool = False  # Enable only behind Render's Cloudflare-protected public ingress

    @model_validator(mode='after')
    def validate_security(self):
        if len(self.jwt_secret_key) < 32 or self.jwt_secret_key.startswith('REPLACE_'):
            raise ValueError('JWT_SECRET_KEY must be a strong random secret (at least 32 characters)')
        if not 1 <= self.access_token_minutes <= 1440:
            raise ValueError('ACCESS_TOKEN_MINUTES must be between 1 and 1440')
        origins = self.allowed_origins
        if any('*' in origin for origin in origins):
            raise ValueError('Wildcard CORS origins are forbidden')
        if self.app_env == 'production':
            if not (self.rate_limit_redis_url.startswith('rediss://') or
                    (self.rate_limit_allow_render_private_redis and
                     is_render_private_redis_url(self.rate_limit_redis_url))):
                raise ValueError('Production requires rediss:// TLS, or an explicitly allowed Render private redis:// hostname')
            if not self.database_url.startswith('postgresql+psycopg://'):
                raise ValueError('Production requires a PostgreSQL URL using the psycopg driver (postgresql+psycopg://)')
            db_parts = urlsplit(self.database_url)
            tls_mode = parse_qs(db_parts.query).get('sslmode', [''])[0]
            if not db_parts.hostname or tls_mode not in ('require', 'verify-ca', 'verify-full'):
                raise ValueError('Production DATABASE_URL must specify PostgreSQL host and sslmode=require or stronger')
            if not origins:
                raise ValueError('Production requires at least one HTTPS CORS origin')
            for origin in origins:
                parts = urlsplit(origin)
                if (parts.scheme != 'https' or not parts.hostname or parts.username or
                        parts.password or parts.query or parts.fragment or parts.path not in ('', '/')):
                    raise ValueError('Production CORS origins must be exact HTTPS origins without paths')
                hostname = parts.hostname.lower()
                if hostname in ('localhost', '127.0.0.1', '::1') or hostname.endswith('.local'):
                    raise ValueError('Production CORS origins must not point to localhost')
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip().rstrip('/') for origin in self.cors_origins.split(',') if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
