#!/bin/bash
LOGFILE="/var/log/user-data.log"
exec > >(tee -a "${LOGFILE}") 2>&1
echo "================================================================="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting User Data initialization..."
echo "================================================================="
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Step 1/3] Updating package lists..."
apt-get update -y

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Step 2/3] Installing prerequisites..."
apt-get install -y apt-transport-https curl unzip

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Step 3/3] Adding MariaDB repository..."
mkdir -p /etc/apt/keyrings
curl -o /etc/apt/keyrings/mariadb-keyring.asc 'https://mariadb.org/mariadb_release_signing_key.pgp'

cat << EOL > /etc/apt/sources.list.d/mariadb.sources
X-Repolib-Name: MariaDB
Types: deb
URIs: https://mirrors.accretive-networks.net/mariadb/repo/12.3/ubuntu
Suites: resolute
Components: main main/debug
Signed-By: /etc/apt/keyrings/mariadb-keyring.asc
EOL

apt-get update -y

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Installing MariaDB server..."
apt-get install -y mariadb-server mariadb-server-galera galera-4 mariadb-client libmariadb3 mariadb-backup mariadb-common mariadb-plugin-columnstore

if ! command -v mariadb &> /dev/null; then
echo "ERROR: MariaDB installation failed. Exiting."
exit 1
fi

sleep 5
echo "================================================================="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] MariaDB installation complete!"
echo "================================================================="

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Downloading data files..."
mkdir -p /opt/data && cd /opt/data
wget -q "https://622.gomillion.org/data/fall2026.zip" -O data.zip
unzip -o data.zip

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Creating stg layer..."

cat << 'EOF' > /tmp/stg_layer.sql