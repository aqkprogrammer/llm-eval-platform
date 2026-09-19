#!/bin/sh
# Container entrypoint: wait for the database, apply migrations, optionally seed, then exec CMD.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "entrypoint: applying database migrations"
  attempt=0
  until alembic upgrade head; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
      echo "entrypoint: database not reachable after $attempt attempts" >&2
      exit 1
    fi
    echo "entrypoint: database not ready yet, retrying in 2s ($attempt/30)"
    sleep 2
  done
fi

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "entrypoint: seeding sample data (idempotent)"
  evalctl seed --traffic "${SEED_TRAFFIC:-160}" $( [ "${SEED_DEMO:-true}" = "true" ] || echo "--no-demo" ) \
    || echo "entrypoint: seeding failed (continuing)" >&2
fi

exec "$@"
