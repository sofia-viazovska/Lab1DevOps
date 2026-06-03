#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Single entry point that bootstraps the entire mywebapp stack on an Ubuntu
# 22.04/24.04 LTS VM, in line with the Lab 1 specification.
#
# Steps:
#   1. install required packages
#   2. create system users (student, teacher, app, operator)
#   3. create PostgreSQL database & role (loopback-only)
#   4. lay down configuration files
#   5. install systemd socket + service
#   6. start the service
#   7. configure nginx as a reverse proxy
#   8. create /home/student/gradebook with N
#   9. lock the default cloud user
#
# Run on a fresh VM as a sudo-capable user (e.g. the cloud default account).
# ---------------------------------------------------------------------------
set -euo pipefail

# Student record-book number used to derive the variant (V2=2, V3=2, V5=3)
readonly N="3697"
readonly APP_DIR="/opt/mywebapp"
readonly APP_USER="app"
readonly DB_NAME="mywebapp"
readonly DB_USER="app_user"
readonly DB_PASSWORD="$(openssl rand -hex 16)"
readonly DEFAULT_USER_CANDIDATES=("ubuntu" "debian" "azureuser" "ec2-user")

log() { printf '\n=== %s ===\n' "$*"; }

# Source directory = repo root (one level above scripts/)
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    exec sudo --preserve-env=N -E bash "$0" "$@"
fi

# ---------------------------------------------------------------------------
# 1. Packages
# ---------------------------------------------------------------------------
log "1/9 Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    nginx \
    sudo openssl ca-certificates

# ---------------------------------------------------------------------------
# 2. Users
# ---------------------------------------------------------------------------
log "2/9 Creating users"

create_human_user() {
    local user="$1"
    if ! id "$user" >/dev/null 2>&1; then
        # If a system group with the same name already exists (e.g. Ubuntu's
        # built-in 'operator' group, GID 37), reuse it as the primary group —
        # otherwise useradd would refuse to create the user.
        if getent group "$user" >/dev/null 2>&1; then
            useradd --create-home --shell /bin/bash --gid "$user" --groups sudo "$user"
        else
            useradd --create-home --shell /bin/bash --groups sudo "$user"
        fi
    else
        # User already exists (likely from a partial earlier run) — make sure
        # they are at least in the sudo group.
        usermod -aG sudo "$user" || true
    fi
    # Always (re)set the default password and force a change at next login.
    echo "${user}:12345678" | chpasswd
    chage -d 0 "$user"
}

create_human_user student
create_human_user teacher
create_human_user operator

# `app` is a system user that runs the service. No login shell, no home dir.
if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi

# ---------------------------------------------------------------------------
# 3. PostgreSQL
# ---------------------------------------------------------------------------
log "3/9 Configuring PostgreSQL"
systemctl enable --now postgresql

# Restrict PG to loopback (defensive — Debian defaults to localhost already)
PG_CONF_DIR="$(sudo -u postgres psql -tAc "SHOW config_file" | xargs dirname)"
if ! grep -qE "^listen_addresses\s*=\s*'localhost'" "${PG_CONF_DIR}/postgresql.conf"; then
    sed -i -E "s|^#?\s*listen_addresses\s*=.*|listen_addresses = 'localhost'|" \
        "${PG_CONF_DIR}/postgresql.conf"
fi
systemctl restart postgresql

# Create role + database (idempotent)
sudo -u postgres psql <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
    ELSE
        ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

# ---------------------------------------------------------------------------
# 4. Application files + configuration
# ---------------------------------------------------------------------------
log "4/9 Installing application files and configuration"

mkdir -p "${APP_DIR}"
# Copy source (excluding venvs, IDE state, caches)
rsync -a --delete \
    --exclude '.venv' \
    --exclude '.idea' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.git' \
    --exclude 'test.db' \
    "${SRC_DIR}/" "${APP_DIR}/"

# Python venv for the app user
python3 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# Config file (mode 0640, readable by `app` group)
mkdir -p /etc/mywebapp
cat >/etc/mywebapp/config.yaml <<EOF
database_url: "postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}"
EOF
chown root:"${APP_USER}" /etc/mywebapp/config.yaml
chmod 0640 /etc/mywebapp/config.yaml

# Log dir for the service (ReadWritePaths in the unit)
mkdir -p /var/log/mywebapp
chown "${APP_USER}":"${APP_USER}" /var/log/mywebapp

# Ownership of the application tree
chown -R "${APP_USER}":"${APP_USER}" "${APP_DIR}"

# Operator sudoers
install -m 0440 -o root -g root \
    "${APP_DIR}/config/sudoers-operator" /etc/sudoers.d/operator
visudo -cf /etc/sudoers.d/operator

# ---------------------------------------------------------------------------
# 5. Systemd units
# ---------------------------------------------------------------------------
log "5/9 Installing systemd units"
install -m 0644 "${APP_DIR}/config/mywebapp.service" /etc/systemd/system/mywebapp.service
install -m 0644 "${APP_DIR}/config/mywebapp.socket"  /etc/systemd/system/mywebapp.socket
systemctl daemon-reload

# ---------------------------------------------------------------------------
# 6. Start the service (via socket activation)
# ---------------------------------------------------------------------------
log "6/9 Enabling and starting mywebapp"
systemctl enable --now mywebapp.socket
# Start the service explicitly so the migration runs on first deploy
systemctl restart mywebapp.service

# ---------------------------------------------------------------------------
# 7. Nginx
# ---------------------------------------------------------------------------
log "7/9 Configuring nginx"
install -m 0644 "${APP_DIR}/config/nginx.conf" /etc/nginx/sites-available/mywebapp
ln -sf /etc/nginx/sites-available/mywebapp /etc/nginx/sites-enabled/mywebapp
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx

# ---------------------------------------------------------------------------
# 8. Gradebook
# ---------------------------------------------------------------------------
log "8/9 Writing /home/student/gradebook"
echo "${N}" >/home/student/gradebook
chown student:student /home/student/gradebook
chmod 0644 /home/student/gradebook

# ---------------------------------------------------------------------------
# 9. Lock default cloud user
# ---------------------------------------------------------------------------
log "9/9 Locking default cloud user"
for candidate in "${DEFAULT_USER_CANDIDATES[@]}"; do
    if id "$candidate" >/dev/null 2>&1 && [[ "$candidate" != "student" && "$candidate" != "teacher" && "$candidate" != "operator" ]]; then
        usermod --lock --expiredate 1 "$candidate" || true
        # Disable SSH key login as well, if applicable
        if [[ -f "/home/${candidate}/.ssh/authorized_keys" ]]; then
            mv "/home/${candidate}/.ssh/authorized_keys" \
               "/home/${candidate}/.ssh/authorized_keys.disabled"
        fi
        echo "Locked default user: $candidate"
    fi
done

log "Done. Verify with: curl -s http://127.0.0.1/ and curl -s http://127.0.0.1/tasks"
