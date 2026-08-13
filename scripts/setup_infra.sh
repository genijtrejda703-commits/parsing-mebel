#!/usr/bin/env bash
# ============================================================
# HOMEART Data Hub - infrastructure bootstrap (idempotent)
# Restores PostgreSQL+pgvector, Redis, FastAPI, Celery after
# pod restart (apt packages outside /app,/root are ephemeral).
# ============================================================
set -e

echo "[1/6] apt packages..."
if ! command -v /usr/lib/postgresql/15/bin/postgres >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql-15 postgresql-server-dev-15 redis-server build-essential
fi

echo "[2/6] pgvector extension..."
if [ ! -f /usr/lib/postgresql/15/lib/vector.so ]; then
  if [ ! -d /root/pgvector ]; then
    git clone --depth 1 --branch v0.8.0 https://github.com/pgvector/pgvector.git /root/pgvector
  fi
  cd /root/pgvector && make clean >/dev/null 2>&1 || true
  make PG_CONFIG=/usr/lib/postgresql/15/bin/pg_config -j2
  make PG_CONFIG=/usr/lib/postgresql/15/bin/pg_config install
fi

echo "[3/6] postgres data dir (/app/data/postgres)..."
mkdir -p /app/data/postgres /app/data/redis
chown -R postgres:postgres /app/data/postgres
chmod 700 /app/data/postgres
if [ ! -f /app/data/postgres/PG_VERSION ]; then
  su postgres -c "/usr/lib/postgresql/15/bin/initdb -D /app/data/postgres --auth-local=trust --auth-host=md5"
  echo "listen_addresses = '127.0.0.1'" >> /app/data/postgres/postgresql.conf
  echo "port = 5432" >> /app/data/postgres/postgresql.conf
fi

echo "[4/6] supervisor programs..."
cp /app/scripts/datahub_supervisor.conf /etc/supervisor/conf.d/datahub.conf
# supervisord must start AFTER apt created the postgres user
if ! supervisorctl status >/dev/null 2>&1; then
  supervisord -c /etc/supervisor/supervisord.conf || true
  sleep 5
fi
supervisorctl reread >/dev/null && supervisorctl update >/dev/null
supervisorctl restart postgresql redis >/dev/null 2>&1 || true
sleep 4

echo "[5/6] role + database + migrations..."
cd /tmp
su postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='datahub'\"" | grep -q 1 || \
  su postgres -c "psql -c \"CREATE ROLE datahub LOGIN PASSWORD 'datahub_secret' SUPERUSER\""
su postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='furniture_hub'\"" | grep -q 1 || \
  su postgres -c "psql -c \"CREATE DATABASE furniture_hub OWNER datahub\""

echo "[6/6] python deps + migrations..."
/root/.venv/bin/pip install -q -r /app/backend/requirements.txt
cd /app/backend && /root/.venv/bin/python migrate.py
supervisorctl restart fastapi celery >/dev/null 2>&1 || true
echo "INFRA READY"
