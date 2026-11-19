#!/bin/sh
set -e
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-$RENDER_EXTERNAL_URL}"
export API_PUBLIC_URL="${API_PUBLIC_URL:-$RENDER_EXTERNAL_URL}"
cd /app/backend
echo "Preparing database..."
alembic upgrade head
python -m app.seed.seed
echo "Starting API..."
uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips='*' &
for i in $(seq 1 30); do
  python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')" 2>/dev/null && break
  sleep 1
done
echo "Starting website on port ${PORT:-10000}..."
cd /app/frontend
exec node node_modules/next/dist/bin/next start -H 0.0.0.0 -p "${PORT:-10000}"
