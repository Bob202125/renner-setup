#!/usr/bin/env bash
# transfer — push a file/dir from your Mac to cc or Bridges,
#            OR open a reverse tunnel so the cluster can push back.
#
# Usage:
#   transfer <src> to <cc|bridges> [-d] [-n NAME]
#   transfer start <cc|bridges>
#
# Options:
#   -d, --date            Prepend mm-dd-yy-HHMM folder on remote host
#   -n, --name <name>     Wrap payload in a custom-named folder
# ----------------------------------------------------------------------------
set -euo pipefail
SSH_OPTS="-q -o LogLevel=ERROR" # keep ssh/scp quiet
TMP_ERR=$(mktemp)               # ← ➊ collect remote stderr
cleanup() { rm -f "$TMP_ERR"; }
trap cleanup EXIT
check_err() {
  local rc=$1
  if [[ $rc -ne 0 ]]; then cat "$TMP_ERR" >&2; fi
  return $rc
}

# ───────────── reverse-tunnel “transfer start …” ──────────────────────────
if [[ ${1:-} == start ]]; then
  target=${2:-cc}
  case "$target" in
  cc)
    echo "⏳  Opening reverse tunnel to cc-login1…"
    exec ssh -N -o ExitOnForwardFailure=yes \
      -R 8022:localhost:22 gclopton@cc-login1.campuscluster.illinois.edu
    ;;
  bridges)
    echo "⏳  Opening reverse tunnel to bridges2-login…"
    exec ssh -N -o ExitOnForwardFailure=yes \
      -R 8023:localhost:22 clopton@bridges2.psc.edu
    ;;
  *)
    echo "Unknown target '$target' (use cc | bridges)"
    exit 1
    ;;
  esac
fi

# ───────────── push mode “transfer <src> to <target> …” ───────────────────
DATE_FLAG=0
CUSTOM=""

usage() {
  cat <<EOF
Usage:
  transfer <src> to <cc|bridges> [-d] [-n NAME]
  transfer start <cc|bridges>
EOF
  exit 1
}

[[ $# -ge 3 ]] || usage
SRC=$1
shift
[[ $1 == to ]] || usage
shift
TARGET=$1
shift

while [[ $# -gt 0 ]]; do
  case $1 in
  -d | --date) DATE_FLAG=1 ;;
  -n | --name)
    shift
    [[ $# -ge 1 ]] || usage
    CUSTOM=$1
    ;;
  -h | --help) usage ;;
  *)
    echo "Unknown option $1"
    usage
    ;;
  esac
  shift
done
[[ -e $SRC ]] || {
  echo "❌ source '$SRC' does not exist"
  exit 1
}

case "$TARGET" in
cc)
  REMOTE_USER="gclopton"
  REMOTE_HOST="cc-login.campuscluster.illinois.edu"
  DEST_BASE="/u/gclopton/transfer"
  ;;
bridges)
  REMOTE_USER="clopton"
  REMOTE_HOST="bridges2.psc.edu"
  DEST_BASE="/ocean/projects/mat220011p/clopton/transfer"
  ;;
*)
  echo "❌ unknown target '$TARGET'"
  usage
  ;;
esac

DEST_PATH="$DEST_BASE"
[[ $DATE_FLAG -eq 1 ]] && DEST_PATH+="/$(date +%m-%d-%y-%H%M)"
[[ -n $CUSTOM ]] && DEST_PATH+="/$CUSTOM"

ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" \
  "mkdir -p '$DEST_PATH'" 2>"$TMP_ERR"
check_err $?

if [[ -d $SRC ]]; then
  scp $SSH_OPTS -O -r "$SRC" "${REMOTE_USER}@${REMOTE_HOST}":"$DEST_PATH/" \
    2>>"$TMP_ERR"
  check_err $?
else
  scp $SSH_OPTS -O "$SRC" "${REMOTE_USER}@${REMOTE_HOST}":"$DEST_PATH/" \
    2>>"$TMP_ERR"
  check_err $?
fi

echo "✅  $SRC → $REMOTE_HOST:$DEST_PATH"
