#!/usr/bin/env bash
#
# PhishSim one-click bootstrap / run script.
#
# Idempotent: safe to re-run. Each step checks whether it already happened
# and skips it if so, so you can run this once to set everything up, or run
# it again later to just start the server (or after a git pull to pick up
# new dependencies/migrations).
#
# Usage:
#   ./scripts/bootstrap.sh              # full setup, then run the server in the foreground
#   ./scripts/bootstrap.sh --no-serve   # set everything up but don't start the server
#   ./scripts/bootstrap.sh --daemon     # start the server in the background (writes a PID file)
#   ./scripts/bootstrap.sh --stop       # stop a --daemon-started server
#
# Environment overrides (all optional -- sensible dev defaults are used otherwise):
#   DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
#   ADMIN_EMAIL, ADMIN_NAME, ADMIN_PASSWORD   (super_admin account created on first run)
#   APP_HOST, APP_PORT
#   SEED_DEMO_DATA=0                          (skip loading demo templates/recipients)
#   PROXY_URL=http://host:port                (only pip installs go through this -- dnf/apt
#                                               are left alone since they often already have
#                                               their own working path to package repos)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$ROOT_DIR/.venv"
ENV_FILE="$ROOT_DIR/.env"
PID_FILE="$ROOT_DIR/.phishsim.pid"

DB_NAME="${DB_NAME:-phishsim}"
DB_USER="${DB_USER:-phishsim}"
DB_PASSWORD="${DB_PASSWORD:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))' 2>/dev/null || echo changeme)}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-9988}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.org}"
ADMIN_NAME="${ADMIN_NAME:-Super Admin}"
SEED_DEMO_DATA="${SEED_DEMO_DATA:-1}"
PROXY_URL="${PROXY_URL:-}"

log()  { printf '\033[1;34m[phishsim]\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m[phishsim]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[phishsim]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[phishsim]\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 0. Parse flags
# ---------------------------------------------------------------------------
SERVE=1
DAEMON=0
for arg in "$@"; do
  case "$arg" in
    --no-serve) SERVE=0 ;;
    --daemon) DAEMON=1 ;;
    --stop)
      if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        stopped_pid="$(cat "$PID_FILE")"
        kill "$stopped_pid"
        rm -f "$PID_FILE"
        ok "Stopped PhishSim (was PID $stopped_pid)."
      else
        warn "No running PhishSim daemon found (or it wasn't started with --daemon)."
      fi
      exit 0
      ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *) die "Unknown argument: $arg" ;;
  esac
done

# ---------------------------------------------------------------------------
# 1. Pick a Python interpreter (prefer 3.12/3.11, fall back to python3)
# ---------------------------------------------------------------------------
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
[[ -n "$PYTHON_BIN" ]] || die "No python3 interpreter found. Install Python 3.10+ and re-run."
PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
log "Using $PYTHON_BIN (Python $PY_VERSION). Python 3.11+ recommended; earlier 3.9/3.10 also works with this project's dependency ranges."

# ---------------------------------------------------------------------------
# 2. Virtualenv + dependencies (idempotent: pip install is safe to re-run)
# ---------------------------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating virtualenv at $VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  log "Virtualenv already exists at $VENV_DIR, reusing it."
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ -n "$PROXY_URL" ]]; then
  log "Installing/updating Python dependencies via proxy $PROXY_URL ..."
  export http_proxy="$PROXY_URL" https_proxy="$PROXY_URL" HTTP_PROXY="$PROXY_URL" HTTPS_PROXY="$PROXY_URL"
  # Don't send internal traffic (DB, this host) through the proxy.
  export no_proxy="${no_proxy:-localhost,127.0.0.1}" NO_PROXY="${NO_PROXY:-localhost,127.0.0.1}"
else
  log "Installing/updating Python dependencies ..."
fi
if ! pip install --upgrade pip -q || ! pip install -r "$ROOT_DIR/requirements.txt" -q; then
  die "pip install failed. If this box has no direct internet access, re-run with PROXY_URL set, e.g.:
    PROXY_URL=http://172.31.105.10:3128 $0
  or point pip at an internal PyPI mirror via a pip.conf / PIP_INDEX_URL instead."
fi
ok "Dependencies installed."

# ---------------------------------------------------------------------------
# 3. PostgreSQL: ensure it's installed, running, and has our db/role
# ---------------------------------------------------------------------------
PSQL=""
for candidate in psql /usr/pgsql-*/bin/psql; do
  if command -v "$candidate" >/dev/null 2>&1; then PSQL="$candidate"; break; fi
done

install_postgresql_dnf() {
  # Package naming differs across the dnf-based distro family:
  #   - Amazon Linux 2023 / Fedora: versioned packages, e.g. postgresql15-server
  #   - RHEL/CentOS/Rocky/AlmaLinux 8+: an AppStream *module stream*
  #     (postgresql:13/:15/:16), installed as plain postgresql-server
  # Try the module-stream path first when it's RHEL-family, then fall back
  # to versioned/plain package names so this works regardless of which of
  # those we guessed right.
  local os_id=""
  if [[ -f /etc/os-release ]]; then
    os_id="$(. /etc/os-release 2>/dev/null; echo "${ID:-}")"
  fi

  if [[ "$os_id" =~ ^(rhel|centos|rocky|almalinux)$ ]] && dnf module list postgresql >/dev/null 2>&1; then
    log "Detected RHEL-family OS ($os_id). Enabling a postgresql module stream ..."
    for stream in 16 15 13; do
      if sudo dnf -y module enable "postgresql:$stream" >/dev/null 2>&1; then
        if sudo dnf install -y postgresql-server postgresql; then
          return 0
        fi
      fi
    done
    warn "postgresql module-stream install didn't work; trying plain/versioned package names instead ..."
  fi

  for pkgset in "postgresql15-server postgresql15" "postgresql16-server postgresql16" "postgresql-server postgresql"; do
    # shellcheck disable=SC2086
    if sudo dnf install -y $pkgset; then
      return 0
    fi
  done
  return 1
}

if [[ -z "$PSQL" ]]; then
  warn "PostgreSQL client (psql) not found."
  if command -v dnf >/dev/null 2>&1; then
    log "Attempting install via dnf (may require sudo)..."
    install_postgresql_dnf || die "Automatic install failed. Install PostgreSQL manually for your distro (on RHEL: 'sudo dnf module enable postgresql:15 && sudo dnf install postgresql-server postgresql'), then re-run."
  elif command -v apt-get >/dev/null 2>&1; then
    log "Attempting install via apt-get (may require sudo)..."
    sudo apt-get update -y && sudo apt-get install -y postgresql postgresql-contrib || die "Automatic install failed -- install PostgreSQL manually, then re-run."
  else
    die "No supported package manager found (dnf/apt-get). Install PostgreSQL 13+ manually, then re-run."
  fi
  for candidate in psql /usr/pgsql-*/bin/psql; do
    if command -v "$candidate" >/dev/null 2>&1; then PSQL="$candidate"; break; fi
  done
fi
[[ -n "$PSQL" ]] || die "psql still not found after install attempt."

PG_ISREADY="$(command -v pg_isready || true)"
if [[ -z "$PG_ISREADY" ]]; then
  PG_ISREADY="$(dirname "$(command -v "$PSQL")")/pg_isready"
fi

if ! "$PG_ISREADY" -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
  log "PostgreSQL isn't running on $DB_HOST:$DB_PORT -- attempting to start it ..."
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q postgresql; then
    # On RHEL/Fedora, the cluster must be initialized once before the unit
    # will start -- systemctl start just fails with no useful error if
    # PGDATA is empty, so check for that first.
    DEFAULT_PGDATA="${PG_DATA:-/var/lib/pgsql/data}"
    if [[ ! -f "$DEFAULT_PGDATA/PG_VERSION" ]]; then
      log "Initializing the PostgreSQL cluster (first run) ..."
      if command -v postgresql-setup >/dev/null 2>&1; then
        sudo postgresql-setup --initdb 2>&1 | grep -v '^$' || true
      elif command -v /usr/bin/postgresql-setup >/dev/null 2>&1; then
        sudo /usr/bin/postgresql-setup --initdb 2>&1 | grep -v '^$' || true
      else
        sudo mkdir -p "$DEFAULT_PGDATA"
        sudo chown -R postgres:postgres "$(dirname "$DEFAULT_PGDATA")"
        sudo -u postgres "$(command -v initdb || echo /usr/pgsql-*/bin/initdb)" -D "$DEFAULT_PGDATA" >/dev/null
      fi
    fi
    sudo systemctl enable postgresql >/dev/null 2>&1 || true
    sudo systemctl start postgresql || sudo systemctl start postgresql.service || true
  else
    # No systemd (containers/sandboxes): initialize + start with pg_ctl directly.
    PG_DATA="${PG_DATA:-/var/lib/pgsql/data}"
    INITDB_BIN="$(command -v initdb || echo /usr/pgsql-*/bin/initdb)"
    PGCTL_BIN="$(command -v pg_ctl || echo /usr/pgsql-*/bin/pg_ctl)"
    if [[ ! -f "$PG_DATA/PG_VERSION" ]]; then
      log "Initializing a new PostgreSQL data directory at $PG_DATA ..."
      sudo mkdir -p "$PG_DATA"
      sudo chown -R postgres:postgres "$(dirname "$PG_DATA")"
      sudo -u postgres "$INITDB_BIN" -D "$PG_DATA" >/dev/null
    fi
    sudo -u postgres "$PGCTL_BIN" -D "$PG_DATA" -l "$PG_DATA/../logfile" -o "-p $DB_PORT -c listen_addresses='$DB_HOST'" start || true
  fi
  sleep 2
  "$PG_ISREADY" -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1 || die "PostgreSQL still not reachable on $DB_HOST:$DB_PORT. Start it manually, then re-run."
fi
ok "PostgreSQL is running on $DB_HOST:$DB_PORT."

role_exists() { sudo -u postgres "$PSQL" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" 2>/dev/null | grep -q 1; }
db_exists()   { sudo -u postgres "$PSQL" -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null | grep -q 1; }

ROLE_ALREADY_EXISTED=0
if role_exists; then
  ROLE_ALREADY_EXISTED=1
  log "Database role '$DB_USER' already exists, leaving its password unchanged for now."
else
  log "Creating database role '$DB_USER' ..."
  sudo -u postgres "$PSQL" -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" >/dev/null
fi

if db_exists; then
  log "Database '$DB_NAME' already exists."
else
  log "Creating database '$DB_NAME' ..."
  sudo -u postgres "$PSQL" -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" >/dev/null
fi
ok "Database ready: $DB_NAME (owner: $DB_USER)."

# ---------------------------------------------------------------------------
# 4. .env (idempotent: never overwrite an existing one)
# ---------------------------------------------------------------------------
if [[ -f "$ENV_FILE" ]]; then
  log ".env already exists, leaving it untouched. Delete it if you want this script to regenerate it."
else
  log "Generating .env ..."
  if [[ "$ROLE_ALREADY_EXISTED" == "1" ]]; then
    # We don't know the existing role's real password (it isn't stored
    # anywhere we can read), and .env is missing, so there's no way to
    # discover it either. Reset it to the value we're about to write so the
    # generated .env is guaranteed to be correct, rather than silently
    # writing a mismatched password that only "works" on setups with trust
    # auth in pg_hba.conf.
    warn "Role '$DB_USER' already existed but no .env was found -- resetting its password so the new .env stays correct."
    sudo -u postgres "$PSQL" -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" >/dev/null
  fi
  SECRET_KEY="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  # Portable in-place sed (GNU/BSD) via temp file.
  tmp="$(mktemp)"
  BASE_URL_HOST="$APP_HOST"
  [[ "$BASE_URL_HOST" == "0.0.0.0" ]] && BASE_URL_HOST="localhost"  # 0.0.0.0 isn't a valid link target for recipients
  sed \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" \
    -e "s|^BASE_URL=.*|BASE_URL=http://$BASE_URL_HOST:$APP_PORT|" \
    -e "s|^APP_HOST=.*|APP_HOST=$APP_HOST|" \
    -e "s|^APP_PORT=.*|APP_PORT=$APP_PORT|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME|" \
    -e "s|^SMTP_HOST=.*|SMTP_HOST=localhost|" \
    -e "s|^SMTP_PORT=.*|SMTP_PORT=1025|" \
    -e "s|^SMTP_USE_TLS=.*|SMTP_USE_TLS=false|" \
    -e "s|^SESSION_COOKIE_SECURE=.*|SESSION_COOKIE_SECURE=false|" \
    -e "s|^REQUIRE_MFA_FOR_ADMINS=.*|REQUIRE_MFA_FOR_ADMINS=false|" \
    "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
  ok "Wrote $ENV_FILE (dev defaults: no TLS SMTP on localhost:1025, MFA optional, cookie not marked Secure)."
  warn "This generated a fresh SMTP/DB password and secret key. Review $ENV_FILE before deploying to production -- see SECURITY.md."
  warn "BASE_URL is set to http://$BASE_URL_HOST:$APP_PORT -- this is embedded in every simulated phishing link, so it MUST be a hostname/IP real recipients' browsers can reach (not 'localhost' unless everyone opens mail on this same box). Edit BASE_URL in $ENV_FILE before running a real campaign."
fi

ln -sf "../.env" "$BACKEND_DIR/.env"  # alembic/app both resolve .env relative to backend/

# ---------------------------------------------------------------------------
# 5. Migrations (idempotent: alembic tracks the applied revision)
# ---------------------------------------------------------------------------
log "Applying database migrations ..."
(cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" alembic upgrade head)
ok "Migrations up to date."

# ---------------------------------------------------------------------------
# 6. Seed RBAC roles/permissions + optional demo data (idempotent by design:
#    seed_rbac and seed_demo_data both check for existing rows before inserting)
# ---------------------------------------------------------------------------
if [[ "$SEED_DEMO_DATA" == "1" ]]; then
  log "Seeding demo data (built-in scenario templates, demo recipients, sender profile) ..."
  (cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" python3 manage.py seed-demo)
else
  log "SEED_DEMO_DATA=0 set, skipping demo data."
fi

# ---------------------------------------------------------------------------
# 7. First admin account (idempotent: skipped if ADMIN_EMAIL already exists)
# ---------------------------------------------------------------------------
ADMIN_EXISTS="$(cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" python3 -c "
from app.database import SessionLocal
from app.services.auth_service import get_admin_by_email
db = SessionLocal()
print('yes' if get_admin_by_email(db, '$ADMIN_EMAIL') else 'no')
db.close()
")"

if [[ "$ADMIN_EXISTS" == "yes" ]]; then
  log "Administrator $ADMIN_EMAIL already exists, skipping creation."
else
  GENERATED_PASSWORD=0
  if [[ -z "${ADMIN_PASSWORD:-}" ]]; then
    # Build the password from guaranteed-present character classes (one
    # upper, one lower, one digit, one symbol, then random padding) rather
    # than pure random sampling -- a purely random draw from this alphabet
    # has a ~1-in-5 chance of missing a symbol entirely, which then fails
    # the app's own password policy (12+ chars, upper/lower/digit/symbol).
    ADMIN_PASSWORD="$("$PYTHON_BIN" -c '
import secrets, string
upper, lower, digit, symbol = string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%^&*-_="
required = [secrets.choice(upper), secrets.choice(lower), secrets.choice(digit), secrets.choice(symbol)]
pool = upper + lower + digit + symbol
required += [secrets.choice(pool) for _ in range(16)]
secrets.SystemRandom().shuffle(required)
print("".join(required))
')"
    GENERATED_PASSWORD=1
  fi
  log "Creating super admin account $ADMIN_EMAIL ..."
  if ! (cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" python3 manage.py create-admin \
      --email "$ADMIN_EMAIL" --full-name "$ADMIN_NAME" --role super_admin --password "$ADMIN_PASSWORD"); then
    die "Failed to create the administrator account. If you set ADMIN_PASSWORD yourself, it must be 12+ characters with an uppercase letter, lowercase letter, digit, and symbol. Re-run with a compliant ADMIN_PASSWORD, or unset it to let this script generate one."
  fi
  ok "Administrator created: $ADMIN_EMAIL"
  if [[ "$GENERATED_PASSWORD" == "1" ]]; then
    warn "Generated password (shown once -- save it now): $ADMIN_PASSWORD"
  fi
fi

echo
ok "Setup complete."
echo "  Dashboard:  http://$APP_HOST:$APP_PORT/"
echo "  API docs:   http://$APP_HOST:$APP_PORT/api/docs"
echo "  Login as:   $ADMIN_EMAIL"
echo

# ---------------------------------------------------------------------------
# 8. Run the server
# ---------------------------------------------------------------------------
if [[ "$SERVE" == "0" ]]; then
  log "Skipping server start (--no-serve). Start it later with: $0"
  exit 0
fi

if [[ "$DAEMON" == "1" ]]; then
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    ok "PhishSim is already running as PID $(cat "$PID_FILE")."
    exit 0
  fi
  log "Starting PhishSim in the background (--daemon) ..."
  nohup "$SCRIPT_DIR/run_server.sh" > "$ROOT_DIR/phishsim.log" 2>&1 &
  echo $! > "$PID_FILE"
  sleep 2
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    die "Server exited immediately -- check $ROOT_DIR/phishsim.log for the error."
  fi
  ok "Started (PID $(cat "$PID_FILE")). Logs: $ROOT_DIR/phishsim.log. Stop with: $0 --stop"
  echo "For a real always-on service (survives reboots/logout, auto-restarts), install it as a systemd service instead: sudo ./scripts/install_service.sh"
else
  log "Starting PhishSim (Ctrl+C to stop) ..."
  exec "$SCRIPT_DIR/run_server.sh"
fi
