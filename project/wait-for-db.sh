#!/bin/sh
set -e
echo "Waiting for db at ${DB_HOST:-db}:${DB_PORT:-5432}..."
until python - <<'PY'
import socket,os,sys
host = os.environ.get("DB_HOST","db")
port = int(os.environ.get("DB_PORT", 5432))
s = socket.socket(); s.settimeout(2)
try:
    s.connect((host, port))
    print("DB_OK")
except Exception:
    sys.exit(1)
finally:
    s.close()
PY
do
  echo "DB not reachable — sleeping 1s"
  sleep 1
done

echo "DB reachable — running migrations"
python manage.py migrate --noinput
exec python manage.py runserver 0.0.0.0:8000