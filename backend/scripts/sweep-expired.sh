#!/usr/bin/env bash
# Run from cron once per minute with absolute path. Does not require a web request.
set -euo pipefail
BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"
# Single-job lock on this host; reservation status transitions remain transactional.
exec 9>"${TMPDIR:-/tmp}/fila-by-deji-expiry.lock"
flock -n 9 || exit 0
exec "$BACKEND_DIR/.venv/bin/python" -m app.expire
