#!/usr/bin/env bash
# One-command reproducibility after any container reset.
# Installs CORE python deps (NO torch / sentence-transformers), writes .env from
# .env.example if missing, registers the dsworker supervisor program and starts
# services. Idempotent: safe to re-run.
#
# Secret handling: the master password is NEVER stored in the repo. Provide it
# via env when first bootstrapping a fresh container:
#     MASTER_PASSWORD='...' ./scripts/bootstrap.sh
# Otherwise a placeholder is written and you must edit /app/.env by hand.
set -euo pipefail
APP=/app
VENV=/root/.venv/bin

echo '==> [1/5] installing CORE python deps (pinned, no torch)'
"$VENV/pip3" install -q \
  "pymupdf==1.24.9" "openpyxl==3.1.5" "uvicorn==0.30.6" \
  "fastapi==0.115.0" "pymongo==4.6.3" "python-multipart" "numpy" || true

echo '==> [2/5] ensuring /app/.env exists'
if [ ! -f "$APP/.env" ]; then
  cp "$APP/.env.example" "$APP/.env"
  if [ -n "${MASTER_PASSWORD:-}" ]; then
    sed -i "s|^MASTER_PASSWORD=.*|MASTER_PASSWORD=${MASTER_PASSWORD}|" "$APP/.env"
    echo '    wrote .env with provided MASTER_PASSWORD'
  else
    echo '    WARNING: .env created with placeholder password. Edit /app/.env before use.'
  fi
else
  echo '    .env already present (left untouched)'
fi

echo '==> [3/5] registering dsworker supervisor program (:8001)'
cat > /etc/supervisor/conf.d/dsworker.conf <<'CONF'
[program:dsworker]
command=/root/.venv/bin/uvicorn worker:app --host 0.0.0.0 --port 8001 --workers 1
directory=/app/backend
autostart=true
autorestart=true
startsecs=5
stopsignal=TERM
stopwaitsecs=20
redirect_stderr=true
stdout_logfile=/var/log/supervisor/dsworker.out.log
environment=DATA_DIR="/app/data",PYTHONUNBUFFERED="1"
CONF

echo '==> [4/5] reloading supervisor'
supervisorctl reread
supervisorctl update

echo '==> [5/5] (re)starting services'
supervisorctl restart dsworker || supervisorctl start dsworker || true
supervisorctl restart nextjs || supervisorctl start nextjs || true

echo '==> bootstrap done. Health:'
sleep 4
curl -s http://localhost:8001/health || echo '(dsworker not answering yet — check logs)'
echo
echo 'Next: python3 scripts/reingest.py   # wipe-and-rebuild DB from /app/data'
