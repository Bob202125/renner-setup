#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  fm -- local file-manager helper
#
#  This Mac-side helper currently implements:
#    fm archive --local [REMOTE_DIR]    Pull Bridges scratch data to local SSD.
#
#  It intentionally complements, rather than replaces, the Bridges-side fm
#  helper. Run this command on the Mac when the archive destination is a local
#  disk mounted under /Volumes.
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_NAME=$(basename "$0")

REMOTE_USER="${FM_REMOTE_USER:-clopton}"
REMOTE_HOST="${FM_REMOTE_HOST:-bridges2.psc.edu}"
REMOTE_SCRATCH="${FM_REMOTE_SCRATCH:-/jet/home/clopton/scratch}"
LOCAL_ARCHIVE_ROOT="${FM_LOCAL_ARCHIVE:-/Volumes/Extreme SSD/bridges2_archive}"

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <command> [options]

Commands:
  fm archive --local [REMOTE_DIR] [options]
  fm sync --from CLUSTER [PATH] [options]
  fm sync --to CLUSTER [PATH] [options]

Local archive options:
  --all                 Mirror the whole Bridges scratch tree. This is also
                        the default when REMOTE_DIR is omitted.
  --status, --dry-run   Show what would be transferred without copying files.
  --dest PATH           Override the local archive root.
                        Default: $LOCAL_ARCHIVE_ROOT
  Source absence never authorizes deletion. The --delete option is disabled.
  --quiet               Suppress per-file progress and print only rsync stats.
  --copy-unsafe-links   Copy out-of-tree symlink targets as real files.
                        Off by default so broken old active-file symlinks do
                        not make the archive fail.

Examples:
  fm archive --local --status
  fm archive --local --all
  fm archive --local convergence_tests
  fm archive --local /jet/home/clopton/scratch/convergence_tests/CeO2_mp-1018664
  fm archive --local convergence_tests --dest "/Volumes/Extreme SSD/bridges2_archive"
  fm sync --from bridges convergence_tests --quiet
  fm sync --to cc convergence_tests --status

Environment overrides:
  FM_REMOTE_USER, FM_REMOTE_HOST, FM_REMOTE_SCRATCH, FM_LOCAL_ARCHIVE
EOF
  exit 1
}

cluster_field() {
  local cluster="$1"
  local field="$2"
  case "$cluster:$field" in
    bridges:user) echo "clopton" ;;
    bridges:host) echo "bridges2.psc.edu" ;;
    bridges:scratch) echo "/jet/home/clopton/scratch" ;;
    cc:user) echo "gclopton" ;;
    cc:host) echo "cc-login.campuscluster.illinois.edu" ;;
    cc:scratch) echo "/scratch/gclopton" ;;
    delta:user) echo "gclopton" ;;
    delta:host) echo "login.delta.ncsa.illinois.edu" ;;
    delta:scratch) echo "/scratch/gclopton" ;;
    *)
      echo "Error: unknown cluster or field: $cluster $field" >&2
      exit 1
      ;;
  esac
}

require_macos_destination() {
  local dest_root="$1"
  local mount_point

  if [[ "$dest_root" == /Volumes/* ]]; then
    mount_point="/Volumes/$(printf "%s" "${dest_root#/Volumes/}" | cut -d/ -f1)"
    if [[ ! -d "$mount_point" ]]; then
      echo "Error: local archive volume is not mounted: $mount_point" >&2
      exit 1
    fi
  fi
}

remote_source_for_target() {
  local target="$1"

  if [[ -z "$target" ]]; then
    printf "%s\n" "$REMOTE_SCRATCH"
  elif [[ "$target" == /* ]]; then
    printf "%s\n" "${target%/}"
  else
    printf "%s/%s\n" "$REMOTE_SCRATCH" "${target#/}"
  fi
}

scratch_relative_path() {
  local remote_src="$1"

  if [[ "$remote_src" != "$REMOTE_SCRATCH" && "$remote_src" != "$REMOTE_SCRATCH/"* ]]; then
    echo "Error: remote source is not under $REMOTE_SCRATCH: $remote_src" >&2
    exit 1
  fi

  local rel="${remote_src#$REMOTE_SCRATCH}"
  rel="${rel#/}"
  printf "%s\n" "$rel"
}

do_archive_local() {
  local target=""
  local dry_run=0
  local copy_links=0
  local quiet=0
  local local_root="$LOCAL_ARCHIVE_ROOT"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --local)
        ;;
      --all)
        target=""
        ;;
      --status|--dry-run)
        dry_run=1
        ;;
      --dest)
        shift
        [[ $# -ge 1 ]] || usage
        local_root="$1"
        ;;
      --delete)
        echo "Error: --delete is disabled; remote absence must not delete archived data." >&2
        exit 1
        ;;
      --quiet)
        quiet=1
        ;;
      --copy-unsafe-links)
        copy_links=1
        ;;
      -h|--help)
        usage
        ;;
      *)
        if [[ -z "$target" ]]; then
          target="$1"
        else
          echo "Error: unexpected argument '$1'" >&2
          usage
        fi
        ;;
    esac
    shift
  done

  require_macos_destination "$local_root"

  local remote_src rel dest
  remote_src="$(remote_source_for_target "$target")"
  rel="$(scratch_relative_path "$remote_src")"

  if [[ -n "$rel" ]]; then
    dest="$local_root/scratch/$rel"
  else
    dest="$local_root/scratch"
  fi

  mkdir -p "$dest"

  local rsync_opts=(-rzlt --human-readable --partial --stats)
  [[ $quiet -eq 0 ]] && rsync_opts+=(--progress)
  rsync_opts+=(--exclude='._*' --exclude='.DS_Store')
  [[ $copy_links -eq 1 ]] && rsync_opts+=(--copy-unsafe-links)
  if [[ $dry_run -eq 1 ]]; then
    rsync_opts+=(--dry-run --itemize-changes)
    echo "=== DRY RUN -- no files will be transferred ==="
  fi

  echo "Remote:      ${REMOTE_USER}@${REMOTE_HOST}:${remote_src}/"
  echo "Destination: $dest/"
  if [[ $copy_links -eq 1 ]]; then
    echo "Symlinks:    copying unsafe/out-of-tree targets as real files"
  else
    echo "Symlinks:    preserving symlinks"
  fi
  echo ""

  COPYFILE_DISABLE=1 rsync "${rsync_opts[@]}" "${REMOTE_USER}@${REMOTE_HOST}:${remote_src}/" "$dest/"

  if [[ $dry_run -eq 0 ]]; then
    find "$local_root" \( -name '._*' -o -name '.DS_Store' \) -delete 2>/dev/null || true
    echo ""
    echo "Local archive complete: $dest/"
  fi
}

do_sync() {
  local direction=""
  local cluster=""
  local target=""
  local dry_run=0
  local copy_links=0
  local quiet=0
  local local_root="$LOCAL_ARCHIVE_ROOT"

  shift # consume sync
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --from|--to)
        direction="${1#--}"
        shift
        [[ $# -ge 1 ]] || usage
        cluster="$1"
        ;;
      --status|--dry-run)
        dry_run=1
        ;;
      --dest|--source)
        shift
        [[ $# -ge 1 ]] || usage
        local_root="$1"
        ;;
      --delete)
        echo "Error: --delete is disabled; source absence must not delete archived data." >&2
        exit 1
        ;;
      --quiet)
        quiet=1
        ;;
      --copy-unsafe-links)
        copy_links=1
        ;;
      -h|--help)
        usage
        ;;
      *)
        if [[ -z "$target" ]]; then
          target="$1"
        else
          echo "Error: unexpected argument '$1'" >&2
          usage
        fi
        ;;
    esac
    shift
  done

  [[ -n "$direction" && -n "$cluster" ]] || usage
  require_macos_destination "$local_root"

  local user host scratch remote_src rel local_path
  user="$(cluster_field "$cluster" user)"
  host="$(cluster_field "$cluster" host)"
  scratch="$(cluster_field "$cluster" scratch)"

  if [[ -z "$target" ]]; then
    remote_src="$scratch"
  elif [[ "$target" == /* ]]; then
    if [[ "$target" != "$scratch" && "$target" != "$scratch/"* ]]; then
      echo "Error: source path is not under $cluster scratch ($scratch): $target" >&2
      exit 1
    fi
    remote_src="${target%/}"
  else
    remote_src="$scratch/${target#/}"
  fi

  rel="${remote_src#$scratch}"
  rel="${rel#/}"
  if [[ -n "$rel" ]]; then
    local_path="$local_root/scratch/$rel"
  else
    local_path="$local_root/scratch"
  fi

  local rsync_opts=(-rzlt --human-readable --partial --stats)
  [[ $quiet -eq 0 ]] && rsync_opts+=(--progress)
  rsync_opts+=(--exclude='._*' --exclude='.DS_Store')
  [[ $copy_links -eq 1 ]] && rsync_opts+=(--copy-unsafe-links)
  if [[ $dry_run -eq 1 ]]; then
    rsync_opts+=(--dry-run --itemize-changes)
    echo "=== DRY RUN -- no files will be transferred ==="
  fi

  if [[ "$direction" == "from" ]]; then
    mkdir -p "$local_path"
    echo "Remote:      ${user}@${host}:${remote_src}/"
    echo "Destination: $local_path/"
    echo ""
    COPYFILE_DISABLE=1 rsync "${rsync_opts[@]}" "${user}@${host}:${remote_src}/" "$local_path/"
    if [[ $dry_run -eq 0 ]]; then
      find "$local_root" \( -name '._*' -o -name '.DS_Store' \) -delete 2>/dev/null || true
    fi
  else
    [[ -d "$local_path" ]] || {
      echo "Error: local source does not exist: $local_path" >&2
      exit 1
    }
    echo "Source:      $local_path/"
    echo "Remote:      ${user}@${host}:${remote_src}/"
    echo ""
    ssh "${user}@${host}" "mkdir -p '$remote_src'"
    COPYFILE_DISABLE=1 rsync "${rsync_opts[@]}" "$local_path/" "${user}@${host}:${remote_src}/"
  fi
}

main() {
  [[ $# -ge 1 ]] || usage

  case "$1" in
    archive)
      shift
      if [[ "${1:-}" == "--local" ]]; then
        do_archive_local "$@"
      else
        echo "Error: this Mac-side helper only implements 'fm archive --local'." >&2
        echo "Run the Bridges-side fm helper for regular ocean archiving." >&2
        exit 1
      fi
      ;;
    sync)
      do_sync "$@"
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Error: unknown command '$1'" >&2
      usage
      ;;
  esac
}

main "$@"
