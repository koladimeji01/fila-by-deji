from functools import lru_cache
from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: Literal['development', 'test', 'production'] = 'development'
    database_url: str = 'sqlite:///./fila_local.db'
    jwt_secret_key: str  # no default secret, fails closed if missing
    access_token_minutes: int = 30
    cors_origins: str = 'http://127.0.0.1:5500,http://localhost:5500'
    rate_limit_redis_url: str = ''  # Required in production, use rediss:// TLS

    @model_validator(mode='after')
    def validate_security(self):
        if len(self.jwt_secret_key) < 32 or self.jwt_secret_key.startswith('REPLACE_'):
            raise ValueError('JWT_SECRET_KEY must be a strong random secret (at least 32 characters)')
        if not 1 <= self.access_token_minutes <= 1440:
            raise ValueError('ACCESS_TOKEN_MINUTES must be between 1 and 1440')
        origins = self.allowed_origins
        if '*' in origins:
            raise ValueError('Wildcard CORS origins are forbidden')
        if self.app_env == 'production':
            if not self.rate_limit_redis_url.startswith('rediss://'):
                raise ValueError('Production requires RATE_LIMIT_REDIS_URL with rediss:// TLS')
            if not self.database_url.startswith('postgresql+psycopg://'):
                raise ValueError('Production requires a PostgreSQL URL using the psycopg driver (postgresql+psycopg://)')
            if any(not origin.startswith('https://') for origin in origins):
                raise ValueError('Production CORS origins must use HTTPS')
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip().rstrip('/') for origin in self.cors_origins.split(',') if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
