#!/usr/bin/env bash
#
# Installs PhishSim as a systemd service (survives reboots/logout, restarts
# automatically on crash) without touching any other service on the box.
#
# Requires: ./scripts/bootstrap.sh --no-serve already run once (venv + .env
# + database must already exist -- this script only wires up systemd).
#
# Usage:
#   sudo ./scripts/install_service.sh            # install/update and start
#   sudo ./scripts/install_service.sh --uninstall
#
# Optional: SERVICE_USER=someuser to run the process as a non-root user
# instead of root (recommended once you've confirmed it works -- the app
# itself needs no root privileges, only bootstrap.sh's package-install step
# did).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UNIT_PATH="/etc/systemd/system/phishsim.service"
SERVICE_USER="${SERVICE_USER:-root}"
SERVICE_GROUP="${SERVICE_GROUP:-$SERVICE_USER}"

log()  { printf '\033[1;34m[phishsim]\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m[phishsim]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[phishsim]\033[0m %s\n' "$1" >&2; exit 1; }

[[ "$(id -u)" == "0" ]] || die "Run this with sudo/root -- it writes to /etc/systemd/system."

if [[ "${1:-}" == "--uninstall" ]]; then
  log "Stopping and removing the phishsim systemd service (this does not touch any other service) ..."
  systemctl stop phishsim 2>/dev/null || true
  systemctl disable phishsim 2>/dev/null || true
  rm -f "$UNIT_PATH"
  systemctl daemon-reload
  ok "Uninstalled. PostgreSQL and everything else on this box is untouched."
  exit 0
fi

[[ -x "$ROOT_DIR/.venv/bin/uvicorn" ]] || die "No virtualenv at $ROOT_DIR/.venv -- run ./scripts/bootstrap.sh --no-serve first."
[[ -f "$ROOT_DIR/.env" ]] || die "No .env at $ROOT_DIR/.env -- run ./scripts/bootstrap.sh --no-serve first."
chmod +x "$SCRIPT_DIR/run_server.sh"

cat > "$UNIT_PATH" <<EOF
[Unit]
Description=PhishSim - Phishing Simulation & Security Awareness Platform
After=network.target postgresql.service
# We only declare an ordering dependency on postgresql (start after it) --
# not a hard "Requires=", so installing/starting/stopping this unit never
# stops or restarts postgresql or any other unit on this host.

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$ROOT_DIR
ExecStart="$SCRIPT_DIR/run_server.sh"
Restart=on-failure
RestartSec=5
# Keep this service's failures/restarts isolated from the rest of the host:
StartLimitIntervalSec=60
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
EOF

log "Wrote $UNIT_PATH (runs as user '$SERVICE_USER')."
systemctl daemon-reload
systemctl enable phishsim >/dev/null
systemctl restart phishsim
sleep 2

if systemctl is-active --quiet phishsim; then
  APP_PORT="$(grep -E '^APP_PORT=' "$ROOT_DIR/.env" | cut -d= -f2 || echo 9988)"
  ok "phishsim.service is running on port ${APP_PORT:-9988}."
  echo "  Status:  systemctl status phishsim"
  echo "  Logs:    journalctl -u phishsim -f"
  echo "  Stop:    sudo systemctl stop phishsim      (does not affect any other service)"
  echo "  Restart: sudo systemctl restart phishsim"
  echo "  Remove:  sudo ./scripts/install_service.sh --uninstall"
else
  systemctl status phishsim --no-pager || true
  die "Service failed to start -- see 'journalctl -u phishsim -e' for the error."
fi
