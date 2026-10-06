#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/opt/phishsim"
ENV_FILE="$APP_DIR/.env"
BACKUP_DIR="/var/backups/phishsim"
STAMP="$(date +%Y%m%d-%H%M%S)"

log(){ printf '[phishsim-update] %s\n' "$*"; }
die(){ printf '[phishsim-update] ERROR: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root: sudo $0"
[[ -d "$APP_DIR" ]] || die "$APP_DIR does not exist"
[[ -d "$REPO_DIR/.git" ]] || die "$REPO_DIR is not a Git working tree"

cd "$REPO_DIR"
log "Pulling latest main from GitHub..."
git pull --ff-only origin main

mkdir -p "$BACKUP_DIR"
if [[ -f "$ENV_FILE" ]]; then
  cp -a "$ENV_FILE" "$BACKUP_DIR/.env.$STAMP"
  log "Backed up .env to $BACKUP_DIR/.env.$STAMP"
fi

install -D -m 0644 "$REPO_DIR/backend/app/web/templates/base.html" "$APP_DIR/backend/app/web/templates/base.html"
install -D -m 0644 "$REPO_DIR/backend/app/main.py" "$APP_DIR/backend/app/main.py"
install -D -m 0644 "$REPO_DIR/backend/app/web/routes/email_web.py" "$APP_DIR/backend/app/web/routes/email_web.py"
install -D -m 0644 "$REPO_DIR/backend/app/web/templates/settings/email.html" "$APP_DIR/backend/app/web/templates/settings/email.html"

if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  log "Installing Python dependencies..."
  "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
else
  die "PhishSim virtualenv not found at $APP_DIR/.venv"
fi

if [[ -x "$APP_DIR/.venv/bin/alembic" ]]; then
  log "Applying database migrations..."
  (cd "$APP_DIR/backend" && "$APP_DIR/.venv/bin/alembic" -c alembic.ini upgrade head)
fi

log "Restarting only phishsim.service..."
systemctl restart phishsim

APP_PORT="$(awk -F= '$1=="APP_PORT" {print $2}' "$ENV_FILE" 2>/dev/null | tail -1)"
APP_PORT="${APP_PORT:-9988}"
log "Waiting for phishsim.service to become active..."
for i in {1..15}; do
  if systemctl is-active --quiet phishsim; then
    break
  fi
  sleep 2
done
systemctl is-active --quiet phishsim || {
  journalctl -u phishsim -n 80 --no-pager
  die "phishsim.service failed to start"
}

log "Waiting for TCP port $APP_PORT..."
for i in {1..15}; do
  if (echo >/dev/tcp/127.0.0.1/"$APP_PORT") >/dev/null 2>&1; then
    log "PhishSim is listening on port $APP_PORT."
    log "Update complete. phishsim.service is healthy."
    exit 0
  fi
  sleep 2
done

journalctl -u phishsim -n 80 --no-pager
die "PhishSim did not become reachable on port $APP_PORT."
