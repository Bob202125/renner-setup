#!/usr/bin/env bash
set -euo pipefail

SOURCE_HOST="bridges2.psc.edu"
SOURCE_PATH="/jet/home/clopton/utils/.vo"
LOCAL_PARENT="/Users/gradyclopton/ObsidianVaults/vasp/Code Base/cluster_utilities"
LOCAL_VO="${LOCAL_PARENT}/.vo"
MANIFEST="${LOCAL_PARENT}/BRIDGES_VO_MIRROR_SYNC_MANIFEST.json"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP_VO="${LOCAL_PARENT}/.vo.sync-tmp-${STAMP}"
BACKUP_VO="${LOCAL_PARENT}/.vo.backup-before-bridges-sync-${STAMP}"

mkdir -p "${TMP_VO}"

ssh -o BatchMode=yes -o ConnectTimeout=10 "${SOURCE_HOST}" "cd '${SOURCE_PATH}' && tar -cf - ." | tar -xf - -C "${TMP_VO}"

if [[ -d "${LOCAL_VO}" ]]; then
  mv "${LOCAL_VO}" "${BACKUP_VO}"
else
  BACKUP_VO=""
fi

mv "${TMP_VO}" "${LOCAL_VO}"

REMOTE_HASHES="$(ssh -o BatchMode=yes -o ConnectTimeout=10 "${SOURCE_HOST}" "cd '${SOURCE_PATH}' && sha256sum vo templates/pwcs_single.sh tools/pwcs/progress.py tools/kpcs/progress.py 2>/dev/null")"
LOCAL_HASHES="$(cd "${LOCAL_VO}" && shasum -a 256 vo templates/pwcs_single.sh tools/pwcs/progress.py tools/kpcs/progress.py 2>/dev/null)"
REMOTE_COUNT="$(ssh -o BatchMode=yes -o ConnectTimeout=10 "${SOURCE_HOST}" "cd '${SOURCE_PATH}' && find . -type f | sort | wc -l" | tr -d '[:space:]')"
LOCAL_COUNT="$(cd "${LOCAL_VO}" && find . -type f | sort | wc -l | tr -d '[:space:]')"

REMOTE_HASH_FILE="$(mktemp)"
LOCAL_HASH_FILE="$(mktemp)"
trap 'rm -f "${REMOTE_HASH_FILE}" "${LOCAL_HASH_FILE}"' EXIT
printf "%s\n" "${REMOTE_HASHES}" | awk '{print $1 "  " $2}' > "${REMOTE_HASH_FILE}"
printf "%s\n" "${LOCAL_HASHES}" | awk '{print $1 "  " $2}' > "${LOCAL_HASH_FILE}"

if ! diff -u "${REMOTE_HASH_FILE}" "${LOCAL_HASH_FILE}" >/dev/null; then
  echo "VO mirror sync hash verification failed." >&2
  diff -u "${REMOTE_HASH_FILE}" "${LOCAL_HASH_FILE}" >&2 || true
  exit 1
fi

if [[ "${REMOTE_COUNT}" != "${LOCAL_COUNT}" ]]; then
  echo "VO mirror sync file-count verification failed: remote=${REMOTE_COUNT} local=${LOCAL_COUNT}" >&2
  exit 1
fi

python3 - "${MANIFEST}" "${BACKUP_VO}" "${LOCAL_COUNT}" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

manifest_path = Path(sys.argv[1])
backup_path = sys.argv[2] or None
file_count = int(sys.argv[3])

manifest = {
    "mirror_purpose": "Local read-only mirror for Claude review. Bridges remains authoritative.",
    "source_host": "bridges2.psc.edu",
    "source_path": "/jet/home/clopton/utils/.vo",
    "local_path": "/Users/gradyclopton/ObsidianVaults/vasp/Code Base/cluster_utilities/.vo",
    "synced_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "sync_method": "ssh tar stream from Bridges to local Mac",
    "local_file_count": file_count,
    "previous_mirror_backup": backup_path,
    "verified_key_files": [
        "vo",
        "templates/pwcs_single.sh",
        "tools/pwcs/progress.py",
        "tools/kpcs/progress.py",
    ],
    "note": "Do not treat this mirror as authoritative for live Bridges state; resync before external review.",
}

manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
PY

echo "Synced Bridges VO mirror."
echo "Source: ${SOURCE_HOST}:${SOURCE_PATH}"
echo "Mirror: ${LOCAL_VO}"
echo "Manifest: ${MANIFEST}"
if [[ -n "${BACKUP_VO}" ]]; then
  echo "Previous mirror backup: ${BACKUP_VO}"
fi
