#!/bin/sh
# Run in a pre-provisioned production container; never migrate automatically.
set -eu

if [ "${APP_ENV:-}" != "production" ]; then
    echo 'Refusing deployment: APP_ENV must be production' >&2
    exit 1
fi

# Fail closed if the schema is behind or Redis/DB credentials are unreachable.
python -m app.doctor

case "${PORT:-8000}" in
    ''|*[!0-9]*) echo 'PORT must be numeric' >&2; exit 1 ;;
esac

# Do not blindly trust X-Forwarded-For from arbitrary clients. Configure a
# verified trusted proxy before moving to per-user IP throttling at scale.
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-proxy-headers
