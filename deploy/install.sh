#!/usr/bin/env bash
# Run once as root to bootstrap mem-bridge on a Debian server.
set -euo pipefail

SVC_USER=chatd
SVC_HOME=/opt/chatd
REPO_DIR=$SVC_HOME/mem-bridge
VENV=$SVC_HOME/venv
TOKENS_FILE=$SVC_HOME/etc/mempalace.tokens
UNIT_SRC=$REPO_DIR/deploy/mem-bridge.service
UNIT_DST=/etc/systemd/system/mem-bridge.service

echo "==> Creating user $SVC_USER (if absent)"
id -u $SVC_USER &>/dev/null || useradd -r -s /usr/sbin/nologin -d $SVC_HOME -m $SVC_USER

echo "==> Creating directories"
install -d -o $SVC_USER -g $SVC_USER -m 750 $SVC_HOME/etc
install -d -o $SVC_USER -g $SVC_USER -m 750 $SVC_HOME/.mempalace

echo "==> Creating empty tokens file (edit it: $TOKENS_FILE)"
[ -f "$TOKENS_FILE" ] || install -o $SVC_USER -g $SVC_USER -m 600 /dev/null $TOKENS_FILE

echo "==> Bootstrapping virtualenv"
if [ ! -d "$VENV" ]; then
    python3 -m venv $VENV
    chown -R $SVC_USER:$SVC_USER $VENV
fi

echo "==> Installing Python deps"
sudo -u $SVC_USER $VENV/bin/pip install -q --upgrade pip
sudo -u $SVC_USER $VENV/bin/pip install -q -r $REPO_DIR/requirements.txt
sudo -u $SVC_USER $VENV/bin/pip install -q mempalace

echo "==> Installing systemd unit"
cp $UNIT_SRC $UNIT_DST
systemctl daemon-reload
systemctl enable --now mem-bridge.service

echo
echo "Done. Edit $TOKENS_FILE and run: systemctl restart mem-bridge"
