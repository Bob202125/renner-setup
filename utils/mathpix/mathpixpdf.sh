#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  mathpixpdf [--outdir DIR] [--obsidian] [--assets] PDF_OR_DIR [PDF_OR_DIR...]

Environment variables (required):
  MATHPIX_APP_ID
  MATHPIX_APP_KEY

Notes:
  - Converts PDFs via Mathpix Convert API (/v3/pdf) and downloads the .mmd result.
  - Output files default to <outdir>/<basename>.md (Mathpix Markdown-flavored Markdown).
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

OUTDIR="."
OBSIDIAN=0
ASSETS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --outdir)
      OUTDIR="${2:-}"
      shift 2
      ;;
    --obsidian)
      OBSIDIAN=1
      shift 1
      ;;
    --assets)
      ASSETS=1
      shift 1
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if [[ -z "${MATHPIX_APP_ID:-}" || -z "${MATHPIX_APP_KEY:-}" ]]; then
  echo "Missing Mathpix credentials. Set MATHPIX_APP_ID and MATHPIX_APP_KEY in your shell environment." >&2
  exit 2
fi

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi

mkdir -p "$OUTDIR"

collect_pdfs() {
  local path="$1"
  if [[ -d "$path" ]]; then
    find "$path" -maxdepth 1 -type f \( -iname '*.pdf' \) -print
  else
    printf '%s\n' "$path"
  fi
}

postprocess_obsidian() {
  # Very light normalization for Obsidian/MathJax:
  # - Convert \( \) -> $ $
  # - Convert \[ \] -> $$ $$
  # This is intentionally conservative; users can disable with no flag.
  python3 -c 'import sys; t=sys.stdin.read(); t=t.replace(r"\\(","$").replace(r"\\)","$").replace(r"\\[","$$").replace(r"\\]","$$"); sys.stdout.write(t)'
}

convert_one() {
  local pdf="$1"
  if [[ ! -f "$pdf" ]]; then
    echo "Not a file: $pdf" >&2
    return 1
  fi

  local base
  base="$(basename "$pdf")"
  base="${base%.pdf}"

  local out_md="$OUTDIR/$base.md"
  local tmp_json tmp_mmd tmp_md
  tmp_json="$(mktemp)"
  tmp_mmd="$(mktemp)"
  tmp_md="$(mktemp)"

  # Submit job
  curl -sS -f -X POST "https://api.mathpix.com/v3/pdf" \
    -H "app_id: ${MATHPIX_APP_ID}" \
    -H "app_key: ${MATHPIX_APP_KEY}" \
    --form "file=@${pdf}" \
    --form 'options_json={"math_inline_delimiters":["$","$"]}' \
    > "$tmp_json"

  local pdf_id
  pdf_id="$(jq -r '.pdf_id // empty' < "$tmp_json")"
  if [[ -z "$pdf_id" || "$pdf_id" == "null" ]]; then
    echo "Mathpix submission failed for: $pdf" >&2
    cat "$tmp_json" >&2
    rm -f "$tmp_json" "$tmp_mmd" "$tmp_md"
    return 1
  fi

  # Poll status
  local status=""
  local attempt=0
  while :; do
    attempt=$((attempt+1))
    curl -sS "https://api.mathpix.com/v3/pdf/${pdf_id}" \
      -H "app_id: ${MATHPIX_APP_ID}" \
      -H "app_key: ${MATHPIX_APP_KEY}" \
      > "$tmp_json"

    status="$(jq -r '.status // empty' < "$tmp_json")"
    if [[ "$status" == "completed" ]]; then
      break
    fi
    if [[ "$status" == "error" || "$status" == "failed" ]]; then
      echo "Mathpix conversion failed for: $pdf" >&2
      cat "$tmp_json" >&2
      rm -f "$tmp_json" "$tmp_mmd" "$tmp_md"
      return 1
    fi

    # show light progress if available
    local percent
    percent="$(jq -r '.percent_done // empty' < "$tmp_json" 2>/dev/null || true)"
    if [[ -n "$percent" && "$percent" != "null" ]]; then
      echo "Converting $(basename "$pdf") … ${percent}%"
    else
      echo "Converting $(basename "$pdf") … (status: ${status:-unknown})"
    fi

    # basic backoff, capped
    if [[ $attempt -lt 10 ]]; then
      sleep 2
    else
      sleep 5
    fi
  done

  # Download Markdown (Mathpix Markdown-flavored)
  curl -sS -f "https://api.mathpix.com/v3/pdf/${pdf_id}.md" \
    -H "app_id: ${MATHPIX_APP_ID}" \
    -H "app_key: ${MATHPIX_APP_KEY}" \
    > "$tmp_mmd"

  if [[ ! -s "$tmp_mmd" ]]; then
    echo "Downloaded empty Markdown for: $pdf" >&2
    rm -f "$tmp_json" "$tmp_mmd" "$tmp_md"
    return 1
  fi

  if [[ $OBSIDIAN -eq 1 ]]; then
    postprocess_obsidian < "$tmp_mmd" > "$tmp_md"
  else
    cat "$tmp_mmd" > "$tmp_md"
  fi

  mv "$tmp_md" "$out_md"

  if [[ $ASSETS -eq 1 ]]; then
    # Best-effort: some accounts return an assets zip at .zip
    local out_zip="$OUTDIR/$base.assets.zip"
    if curl -sS -f "https://api.mathpix.com/v3/pdf/${pdf_id}.zip" \
      -H "app_id: ${MATHPIX_APP_ID}" \
      -H "app_key: ${MATHPIX_APP_KEY}" \
      -o "$out_zip"; then
      : # ok
    else
      rm -f "$out_zip" 2>/dev/null || true
    fi
  fi

  rm -f "$tmp_json" "$tmp_mmd"
  echo "Wrote: $out_md"
}

exit_code=0
while [[ $# -gt 0 ]]; do
  in="$1"
  shift
  while IFS= read -r pdf; do
    convert_one "$pdf" || exit_code=1
  done < <(collect_pdfs "$in")
done

exit "$exit_code"
