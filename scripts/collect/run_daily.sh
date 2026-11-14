#!/bin/bash
# Usage: run_daily.sh user|root
# user: host + docker collectors. root: SMART only (needs root).
# Exit: 0 ok, 1 partial data, 2 fatal collector, 3 skipped (already running).
MODE=${1:?usage: run_daily.sh user|root}
DIR="$(cd "$(dirname "$0")" && pwd)"
BASE=/srv/data/reports
export G600_RAW_DIR=$BASE/raw
LOG=$BASE/logs/daily-$MODE.log
log() { echo "$(date -Is) [$MODE] $*" >> "$LOG"; }

exec 9>"/tmp/g600-daily-$MODE.lock"
flock -n 9 || { log "SKIP: previous run still active"; exit 3; }

case $MODE in
  user) JOBS="host_health.py docker_health.py"; [ "$(id -u)" -ne 0 ] || { log "FATAL: do not run user mode as root"; exit 2; } ;;
  root) JOBS="smart_health.py"; [ "$(id -u)" -eq 0 ] || { echo "root mode needs sudo" >&2; exit 2; } ;;
  *) echo "bad mode" >&2; exit 2 ;;
esac
[ -d "$G600_RAW_DIR" ] || { log "FATAL: $G600_RAW_DIR missing"; exit 2; }

worst=0
for j in $JOBS; do
  log "START $j"
  "$DIR/$j" > /dev/null 2>> "$LOG"; rc=$?
  log "END $j rc=$rc"
  [ $rc -gt $worst ] && worst=$rc
done
log "DONE worst_rc=$worst"
exit $worst
