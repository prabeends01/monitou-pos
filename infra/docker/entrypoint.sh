#!/bin/sh
set -e

echo "waiting for database..."
until uv run python -c "
import sys
from sqlalchemy import create_engine, text
from app.config import settings
try:
    create_engine(settings.database_url).connect().close()
except Exception as exc:
    print(exc); sys.exit(1)
" 2>/dev/null; do
  sleep 1
done

echo "running migrations..."
uv run alembic upgrade head

exec "$@"
