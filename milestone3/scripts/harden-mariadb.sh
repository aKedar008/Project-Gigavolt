#!/bin/bash
# harden-mariadb.sh
# Stops systemd from automatically restarting mariadb after a crash, so a node
# can never rejoin or bootstrap on its own while the cluster is in an unknown state.
#
#   ./harden-mariadb.sh             disable auto-restart only
#   ./harden-mariadb.sh --no-boot   also stop mariadb starting at boot
#                                           (after a reboot, run galera-bootstrap-check.sh)

set -e
[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)."; exit 1; }

mkdir -p /etc/systemd/system/mariadb.service.d

# "zz-" makes this drop-in load last, so it overrides the packaged Restart= setting
cat > /etc/systemd/system/mariadb.service.d/zz-no-auto-restart.conf <<'EOF'
[Service]
Restart=no
EOF

systemctl daemon-reload

if [ "${1:-}" = "--no-boot" ]; then
  systemctl disable mariadb
  echo "mariadb will NOT start at boot."
fi

echo "Effective settings:"
systemctl show mariadb -p Restart -p UnitFileState
