"""Read-only startup diagnostic. Run: python -m app.doctor

Checks configured DB, the Alembic revision and the schema before serving traffic.
Never prints database credentials, JWT secrets or Redis connection strings.
"""
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from .config import get_settings
from .database import engine


def check_readiness() -> list[str]:
    errors: list[str] = []
    ini = Path(__file__).resolve().parents[1] / 'alembic.ini'
    expected = ScriptDirectory.from_config(Config(str(ini))).get_current_head()

    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
            actual = MigrationContext.configure(conn).get_current_revision()
            if actual != expected:
                errors.append(f'Database migration is {actual or "unversioned"}; expected {expected}. Run: python -m alembic upgrade head')
            schema = inspect(conn)
            checks = {
                'users': {'id', 'email', 'is_admin'},
                'products': {'id', 'price_kobo'},
                'orders': {'id', 'status', 'reserved_until', 'client_request_id', 'delivery_destination', 'shipping_quote_kobo', 'shipping_quoted_at'},
                'delivery_quote_audit': {'id', 'order_id', 'admin_user_id', 'new_amount_kobo'},
                'order_items': {'order_id', 'product_id'},
                'product_inventory': {'product_id', 'size', 'quantity'},
                'product_photos': {'product_id', 'image_data', 'mime_type', 'created_at'},
                'staff_applications': {'user_id', 'status', 'requested_at', 'reviewed_at', 'reviewed_by'},
                'staff_access_audit': {'id', 'subject_user_id', 'actor_user_id', 'action', 'created_at'},
                'enquiry_followups': {'order_id', 'stage', 'internal_note', 'updated_by', 'updated_at'},
                'saved_items': {'user_id', 'product_id', 'size', 'quantity'},
            }
            tables = set(schema.get_table_names())
            for name, required in checks.items():
                if name not in tables:
                    errors.append(f'Missing database table: {name}')
                    continue
                columns = {column['name'] for column in schema.get_columns(name)}
                for missing in sorted(required - columns):
                    errors.append(f'Missing database column: {name}.{missing}')
    except Exception as exc:
        errors.append(f'Database unavailable or schema check failed ({type(exc).__name__})')

    if get_settings().app_env == 'production':
        try:
            from .rate_limit import redis_client
            redis_client(get_settings().rate_limit_redis_url).ping()
        except Exception as exc:
            errors.append(f'Redis security counter unavailable ({type(exc).__name__})')
    return errors


if __name__ == '__main__':
    problems = check_readiness()
    if problems:
        for problem in problems:
            print('NOT READY:', problem)
        raise SystemExit(1)
    print('READY: database schema, migration and configured security services checked.')
