#!/bin/sh
# Production entrypoint. docker-compose.prod.yml sets this on the API service
# only. The dev Compose file does not, so local `uvicorn --reload` is unchanged.
set -eu

if [ "${RUN_DB_INIT:-0}" = "1" ]; then
  echo "[entrypoint] waiting for database"
  python wait_for_db.py
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head
  echo "[entrypoint] ensure AI read-only role"
  python ensure_readonly.py
  echo "[entrypoint] seed reference data"
  python seed.py
fi

if [ "$#" -eq 0 ]; then
  echo "[entrypoint] no command given" >&2
  exit 1
fi

exec "$@"
