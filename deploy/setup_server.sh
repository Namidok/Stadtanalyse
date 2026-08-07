#!/usr/bin/env bash
# One-time server install for the Stadtanalyse DuckDB-mode demo (Option 2, no Docker).
# Run as root on the t3.micro. Assumes /opt/stadtanalyse already contains:
#   api/                        (the FastAPI package, from repo)
#   data/cities.json            (from repo data/)
#   data/city.json              (from repo data/)
#   data/local/stadtanalyse.duckdb  (demo snapshot, from repo data/local/)
#   web_dist/                   (React build: repo web/dist)
#   deploy/requirements-server.txt, nginx.conf, stadtanalyse-api.service
set -euo pipefail

APP=/opt/stadtanalyse
USER=stadtanalyse

apt-get update
apt-get install -y python3-venv python3-pip nginx

# --- app user ---------------------------------------------------------------
if ! id "$USER" >/dev/null 2>&1; then
    useradd --system --home "$APP" --shell /usr/sbin/nologin "$USER"
fi
chown -R "$USER:$USER" "$APP"

# --- python venv (lean: no sklearn/scipy/xgboost) ---------------------------
if [ ! -d "$APP/.venv" ]; then
    su -s /bin/bash "$USER" -c "python3 -m venv $APP/.venv"
fi
su -s /bin/bash "$USER" -c "$APP/.venv/bin/pip install --no-cache-dir -r $APP/deploy/requirements-server.txt"

# --- systemd unit -----------------------------------------------------------
cp "$APP/deploy/stadtanalyse-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now stadtanalyse-api

# --- nginx -------------------------------------------------------------------
cp "$APP/deploy/nginx.conf" /etc/nginx/sites-available/stadtanalyse
ln -sf /etc/nginx/sites-available/stadtanalyse /etc/nginx/sites-enabled/stadtanalyse
nginx -t
systemctl reload nginx

echo "== done. status: =="
systemctl status stadtanalyse-api --no-pager | head -6
curl -s http://127.0.0.1:8000/api/v1/health || true
echo
echo "Now: point DNS stadtanalyse.srikarkodi.dev at this box, then run:"
echo "  sudo certbot --nginx -d stadtanalyse.srikarkodi.dev"
