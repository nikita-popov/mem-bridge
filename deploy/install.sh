#!/usr/bin/env bash
# Bootstrap mem-bridge on any systemd-based Linux system.
# Run as root.  All paths and the service user are configurable.
#
# Usage:
#   bash install.sh [options]
#
# Options:
#   --user    NAME   System user to create and run the service (default: mem-bridge)
#   --dir     PATH   Installation directory                    (default: /opt/mem-bridge)
#   --conf    PATH   Directory for config/token files          (default: /etc/mem-bridge)
#   --palace  PATH   Path to MemPalace palace directory        (default: <dir>/.mempalace/palace)
#   --host    HOST   External hostname for MCP access          (default: empty)
#   --help           Show this help and exit

set -euo pipefail

# ── defaults ──────────────────────────────────────────────────────────────────
SVC_USER="mem-bridge"
INSTALL_DIR="/opt/mem-bridge"
CONF_DIR="/etc/mem-bridge"
PALACE_PATH=""
ALLOWED_HOST=""

# ── argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --user)   SVC_USER="$2";    shift 2 ;;
        --dir)    INSTALL_DIR="$2"; shift 2 ;;
        --conf)   CONF_DIR="$2";    shift 2 ;;
        --palace) PALACE_PATH="$2"; shift 2 ;;
        --host)   ALLOWED_HOST="$2"; shift 2 ;;
        --help)
            sed -n '3,21p' "$0"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$PALACE_PATH" ]] && PALACE_PATH="$INSTALL_DIR/.mempalace/palace"

VENV="$INSTALL_DIR/venv"
TOKENS_FILE="$CONF_DIR/tokens"
ENV_FILE="$CONF_DIR/env"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.."; pwd)"
UNIT_DST="/etc/systemd/system/mem-bridge.service"

echo "==> Configuration"
echo "    user:         $SVC_USER"
echo "    install dir:  $INSTALL_DIR"
echo "    conf dir:     $CONF_DIR"
echo "    palace:       $PALACE_PATH"
echo "    allowed host: ${ALLOWED_HOST:-'(localhost only)'}"
echo

# ── system user ───────────────────────────────────────────────────────────────
echo "==> Creating user '$SVC_USER' (if absent)"
if ! id -u "$SVC_USER" &>/dev/null; then
    useradd -r -s /usr/sbin/nologin -d "$INSTALL_DIR" -m "$SVC_USER"
fi

# ── directories ───────────────────────────────────────────────────────────────
echo "==> Creating directories"
install -d -o "$SVC_USER" -g "$SVC_USER" -m 750 "$INSTALL_DIR"
install -d -o "$SVC_USER" -g "$SVC_USER" -m 750 "$CONF_DIR"
install -d -o "$SVC_USER" -g "$SVC_USER" -m 750 "$(dirname "$PALACE_PATH")"

# ── config files ──────────────────────────────────────────────────────────────
echo "==> Writing config to $ENV_FILE"
if [[ ! -f "$ENV_FILE" ]]; then
    cat > "$ENV_FILE" <<EOF
MEMBRIDGE_PALACE_PATH=$PALACE_PATH
MEMBRIDGE_MEMPALACE_BIN=$VENV/bin/mempalace
MEMBRIDGE_TOKENS_FILE=$TOKENS_FILE
MEMBRIDGE_BIND=127.0.0.1:8765
MEMBRIDGE_WORKERS=1
MEMBRIDGE_ALLOWED_HOSTS=$ALLOWED_HOST
EOF
    chown "$SVC_USER:$SVC_USER" "$ENV_FILE"
    chmod 640 "$ENV_FILE"
fi

echo "==> Creating empty tokens file (edit it: $TOKENS_FILE)"
if [[ ! -f "$TOKENS_FILE" ]]; then
    install -o "$SVC_USER" -g "$SVC_USER" -m 600 /dev/null "$TOKENS_FILE"
fi

# ── virtualenv + deps ─────────────────────────────────────────────────────────
echo "==> Bootstrapping virtualenv at $VENV"
if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
    chown -R "$SVC_USER:$SVC_USER" "$VENV"
fi

echo "==> Installing Python deps"
sudo -u "$SVC_USER" "$VENV/bin/pip" install -q --upgrade pip
sudo -u "$SVC_USER" "$VENV/bin/pip" install -q -r "$REPO_DIR/requirements.txt"
sudo -u "$SVC_USER" "$VENV/bin/pip" install -q mempalace

# ── copy app ──────────────────────────────────────────────────────────────────
echo "==> Copying application to $INSTALL_DIR"
rsync -a --exclude='.git' --exclude='venv' --exclude='__pycache__' \
    "$REPO_DIR/" "$INSTALL_DIR/"
chown -R "$SVC_USER:$SVC_USER" "$INSTALL_DIR"

# ── systemd unit ──────────────────────────────────────────────────────────────
echo "==> Installing systemd unit"
sed \
    -e "s|User=mem-bridge|User=$SVC_USER|" \
    -e "s|Group=mem-bridge|Group=$SVC_USER|" \
    -e "s|WorkingDirectory=/opt/mem-bridge|WorkingDirectory=$INSTALL_DIR|" \
    -e "s|EnvironmentFile=-/etc/mem-bridge/env|EnvironmentFile=-$ENV_FILE|" \
    -e "s|/opt/mem-bridge/venv|$VENV|" \
    "$REPO_DIR/deploy/mem-bridge.service" > "$UNIT_DST"

systemctl daemon-reload
systemctl enable --now mem-bridge.service

echo
echo "========================================================="
echo " mem-bridge installed and started."
echo
echo " Next steps:"
echo "   1. Add bearer tokens to $TOKENS_FILE"
echo "      (one per line, lines starting with # are comments)"
echo "   2. systemctl restart mem-bridge"
echo "   3. Include deploy/nginx-location.conf in your server block"
echo "   4. Test: curl https://your-domain/mem-bridge/healthz"
echo "========================================================="
