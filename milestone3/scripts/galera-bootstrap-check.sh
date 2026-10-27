#!/bin/bash
# galera-bootstrap-check.sh
# Works out which node is safe to bootstrap after a full-cluster outage
# (for example when the AWS lab session times out and every node comes back down).
#
# Run as root on EACH node while mariadb is stopped:
#   ./galera-bootstrap-check.sh               report only
#   ./galera-bootstrap-check.sh --bootstrap   bootstrap only if safe_to_bootstrap=1 and no peer is up
#   ./galera-bootstrap-check.sh --force       bootstrap a node with safe_to_bootstrap=0 (asks to confirm)
#   ./galera-bootstrap-check.sh --mark        set safe_to_bootstrap=1 on this node WITHOUT bootstrapping (asks to confirm)

set -u

GRASTATE=/var/lib/mysql/grastate.dat
CONF=/etc/mysql/mariadb.conf.d/60-galera.cnf
PORT=4567
LOG=/var/log/galera-bootstrap-check.log
ACTION=${1:-report}

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

if [ "$(id -u)" -ne 0 ]; then echo "Run as root (sudo)."; exit 1; fi

case "$ACTION" in
  report|--bootstrap|--force|--mark) ;;
  *) echo "Usage: $0 [--bootstrap|--force|--mark]"; exit 1 ;;
esac

log "===== Galera bootstrap check on $(hostname) ====="

if systemctl is-active --quiet mariadb; then
  log "mariadb is already running on this node - nothing to do."
  mariadb -N -e "SHOW STATUS WHERE Variable_name IN ('wsrep_cluster_size','wsrep_cluster_status','wsrep_local_state_comment')" | tee -a "$LOG"
  exit 0
fi

# ---- 1. Is any peer already listening on the Galera port? -------------------
CLUSTER_ADDR=$(grep -hE '^[[:space:]]*wsrep_cluster_address' "$CONF" | sed -E 's|.*gcomm://([^"#[:space:]]*).*|\1|')
[ -z "$CLUSTER_ADDR" ] && log "WARNING: could not read wsrep_cluster_address from $CONF"
MY_IPS=" $(hostname -I) "
LIVE_PEERS=""
for ip in ${CLUSTER_ADDR//,/ }; do
  case "$MY_IPS" in *" $ip "*) continue ;; esac
  if timeout 3 bash -c "exec 3<>/dev/tcp/$ip/$PORT" 2>/dev/null; then
    LIVE_PEERS="$LIVE_PEERS $ip"
  fi
done

# ---- 2. Read this node's Galera state ---------------------------------------
if [ ! -f "$GRASTATE" ]; then
  log "No $GRASTATE - this node has no Galera state. It must JOIN, never bootstrap."
  exit 2
fi
UUID=$(awk '/^uuid:/ {print $2}' "$GRASTATE")
SEQNO=$(awk '/^seqno:/ {print $2}' "$GRASTATE")
SAFE=$(awk '/^safe_to_bootstrap:/ {print $2}' "$GRASTATE")

RECOVERED=""
if [ "$SEQNO" = "-1" ]; then
  log "seqno is -1 (unclean shutdown). Running wsrep-recover to read the real position..."
  RECOVERED=$(runuser -u mysql -- mariadbd --wsrep-recover 2>&1 | grep -o 'Recovered position:.*' | tail -1 | awk '{print $NF}')
fi

log "Node:               $(hostname) ($(hostname -I | awk '{print $1}'))"
log "Cluster UUID:       ${UUID:-unknown}"
log "grastate seqno:     ${SEQNO:-unknown}"
[ -n "$RECOVERED" ] && log "Recovered position: $RECOVERED   <- compare this number across nodes"
log "safe_to_bootstrap:  ${SAFE:-unknown}"

# ---- 3. Decide ----------------------------------------------------------------
if [ -n "$LIVE_PEERS" ]; then
  log "RESULT: peer(s) listening on $PORT:$LIVE_PEERS - a cluster process is already up."
  log "        Do NOT bootstrap. Check the peer shows wsrep_cluster_status=Primary, then: systemctl start mariadb"
  exit 0
fi

if [ "$SAFE" = "1" ]; then
  log "RESULT: SAFE TO BOOTSTRAP - this node left the cluster last."
else
  log "RESULT: NOT marked safe. Run this script on every node and bootstrap the one with the HIGHEST seqno / recovered position."
fi

do_bootstrap() {
  log "Running galera_new_cluster..."
  if galera_new_cluster; then
    sleep 5
    mariadb -N -e "SHOW STATUS WHERE Variable_name IN ('wsrep_cluster_size','wsrep_cluster_status','wsrep_ready')" | tee -a "$LOG"
    log "Bootstrapped. Start the other nodes ONE AT A TIME with: systemctl start mariadb"
  else
    log "galera_new_cluster failed - see: journalctl -u mariadb --no-pager | tail -30"
    exit 1
  fi
}

case "$ACTION" in
  --mark)
    if [ "$SAFE" = "1" ]; then
      log "Already marked safe_to_bootstrap: 1 on $(hostname)."
    else
      read -r -p "Is this node's seqno/recovered position the HIGHEST of all nodes? Type YES to mark it: " ans
      [ "$ans" = "YES" ] || { log "Aborted."; exit 1; }
      sed -i 's/^safe_to_bootstrap:.*/safe_to_bootstrap: 1/' "$GRASTATE"
      log "safe_to_bootstrap set to 1 on $(hostname). Mark ONLY this node. Next: galera-bootstrap-check.sh --bootstrap"
    fi
    ;;
  --bootstrap)
    if [ "$SAFE" = "1" ]; then
      do_bootstrap
    else
      log "Refusing to bootstrap: safe_to_bootstrap is not 1. Compare seqno on all nodes, then use --force on the highest."
      exit 1
    fi
    ;;
  --force)
    read -r -p "Is this node's seqno/recovered position the HIGHEST of all nodes? Type YES to continue: " ans
    [ "$ans" = "YES" ] || { log "Aborted."; exit 1; }
    sed -i 's/^safe_to_bootstrap:.*/safe_to_bootstrap: 1/' "$GRASTATE"
    do_bootstrap
    ;;
esac
