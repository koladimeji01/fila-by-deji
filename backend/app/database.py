from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from .config import get_settings


class Base(DeclarativeBase):
    pass


url = get_settings().database_url
engine = create_engine(
    url,
    pool_pre_ping=True,
    connect_args={'check_same_thread': False} if url.startswith('sqlite') else {},
)

if url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def enforce_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
