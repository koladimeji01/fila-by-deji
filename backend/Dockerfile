# FÌLÀ by Deji API: build with context set to ./backend
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt && \
    useradd --uid 10001 --create-home --shell /usr/sbin/nologin fila

COPY --chown=fila:fila app/ ./app/
COPY --chown=fila:fila alembic/ ./alembic/
COPY --chown=fila:fila alembic.ini ./alembic.ini
COPY --chown=fila:fila scripts/start-api.sh ./scripts/start-api.sh

USER fila
EXPOSE 8000
# Host health checks also use GET /api/v1/health. Does not print secrets.
HEALTHCHECK --interval=30s --timeout=6s --start-period=45s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health',timeout=4).read()"
CMD ["sh", "./scripts/start-api.sh"]
