#!/usr/bin/env bash
#
# Thin wrapper that starts the PhishSim server using the venv + .env created
# by bootstrap.sh. This is the single script both `bootstrap.sh` (foreground/
# --daemon) and the systemd unit (see install_service.sh) call, so there is
# one place that knows how to actually launch uvicorn.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
BACKEND_DIR="$ROOT_DIR/backend"
ENV_FILE="$ROOT_DIR/.env"

[[ -x "$VENV_DIR/bin/uvicorn" ]] || {
  echo "No virtualenv found at $VENV_DIR. Run ./scripts/bootstrap.sh --no-serve first." >&2
  exit 1
}
[[ -f "$ENV_FILE" ]] || {
  echo "No .env found at $ENV_FILE. Run ./scripts/bootstrap.sh --no-serve first." >&2
  exit 1
}

# Read just the two keys we need directly out of .env with grep/cut rather
# than `source`-ing the whole file: .env values are allowed to contain
# unquoted spaces (e.g. DEFAULT_SENDER_NAME=IT Security), which is valid
# dotenv syntax but NOT valid bash -- sourcing it directly makes bash try to
# run "Security" as a command and blows up. The app itself reads the full
# .env correctly via pydantic-settings' own dotenv parser; this script only
# needs the two values below to pick uvicorn's bind address.
read_env_var() {
  grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}

APP_HOST="$(read_env_var APP_HOST)"
APP_PORT="$(read_env_var APP_PORT)"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-9988}"

cd "$ROOT_DIR"
exec "$VENV_DIR/bin/uvicorn" app.main:app --host "$APP_HOST" --port "$APP_PORT" --app-dir "$BACKEND_DIR"
