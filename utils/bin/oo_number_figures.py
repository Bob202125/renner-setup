#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HEADER_RE = re.compile(r"^(\s*)((?:>\s*)+)\[!([^\]\s]+)\]([+-])?(?:\s+(.*?))?\s*$")
QUOTE_RE = re.compile(r"^(\s*)((?:>\s*)+)(.*)$")
FENCE_RE = re.compile(r"^(?:```+|~~~+)")
FIGURE_PREFIX_RE = re.compile(
    r"^Figure\s+(\d+)(?:(?:\(([A-Za-z])\))|(?:\.([A-Za-z]))|(?:([A-Za-z])))?(?:\s*[:.-]\s*(.*)|\s+(.*)|$)",
    re.IGNORECASE,
)


def read_text_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_type(value: str) -> str:
    return str(value or "").strip().lower()


def quote_depth(prefix: str) -> int:
    return prefix.count(">")


def backup_path_for(target: Path) -> Path:
    backup_dir = target.parent if target.parent.name == "backups" else target.parent / "backups"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = target.suffix
    stem = target.stem if suffix else target.name
    return backup_dir / f"{stem}.backup-{timestamp}{suffix}"


def short_diff(before: str, after: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(True),
        after.splitlines(True),
        fromfile="before-normalized",
        tofile="after-normalized",
        n=3,
    )
    return "".join(diff[:80])


def parse_figure_title(title: str) -> tuple[str, str]:
    clean_title = collapse_whitespace(title)
    if not clean_title:
        return "", ""

    match = FIGURE_PREFIX_RE.match(clean_title)
    if not match:
        return "", clean_title

    letter = match.group(2) or match.group(3) or match.group(4) or ""
    suffix = f"({letter})" if letter else ""
    return suffix, collapse_whitespace(match.group(5) or match.group(6) or "")


def rewrite_header(match: re.Match[str], number: int) -> str:
    indent, prefix, raw_type, fold, raw_title = match.groups()
    suffix, suffix_text = parse_figure_title(raw_title or "")
    label = f"Figure {number}{suffix}"
    title = f"{label}: {suffix_text}" if suffix_text else label
    fold = fold or ""
    return f"{indent}{prefix}[!{raw_type}]{fold} {title}"


def normalize_figure_headers(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    fence_depths: list[int] = []

    for line in lines:
        raw = line.rstrip("\r\n")
        newline = line[len(raw) :]
        quote_match = QUOTE_RE.match(raw)
        depth = quote_depth(quote_match.group(2)) if quote_match else 0

        while fence_depths and fence_depths[-1] > depth:
            fence_depths.pop()

        if not quote_match:
            out.append(line)
            continue

        body = quote_match.group(3).lstrip()
        in_fence = fence_depths and depth >= fence_depths[-1]
        is_fence_marker = bool(FENCE_RE.match(body))

        if in_fence:
            if is_fence_marker and depth == fence_depths[-1]:
                fence_depths.pop()
            out.append(line)
            continue

        if is_fence_marker:
            fence_depths.append(depth)
            out.append(line)
            continue

        header_match = HEADER_RE.match(raw)
        if not header_match or normalize_type(header_match.group(3)) != "figure":
            out.append(line)
            continue

        indent, prefix, raw_type, fold, raw_title = header_match.groups()
        _, suffix_text = parse_figure_title(raw_title or "")
        fold = fold or ""
        canonical = f"{indent}{prefix}[!{raw_type}]{fold}"
        if suffix_text:
            canonical += f" {suffix_text}"
        out.append(canonical + newline)

    return "".join(out)


def renumber_figure_headers(text: str) -> tuple[str, int, int]:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    fence_depths: list[int] = []
    figure_count = 0
    changed_count = 0

    for line in lines:
        raw = line.rstrip("\r\n")
        newline = line[len(raw) :]
        quote_match = QUOTE_RE.match(raw)
        depth = quote_depth(quote_match.group(2)) if quote_match else 0

        while fence_depths and fence_depths[-1] > depth:
            fence_depths.pop()

        if not quote_match:
            out.append(line)
            continue

        body = quote_match.group(3).lstrip()
        in_fence = fence_depths and depth >= fence_depths[-1]
        is_fence_marker = bool(FENCE_RE.match(body))

        if in_fence:
            if is_fence_marker and depth == fence_depths[-1]:
                fence_depths.pop()
            out.append(line)
            continue

        if is_fence_marker:
            fence_depths.append(depth)
            out.append(line)
            continue

        header_match = HEADER_RE.match(raw)
        if not header_match or normalize_type(header_match.group(3)) != "figure":
            out.append(line)
            continue

        figure_count += 1
        rewritten = rewrite_header(header_match, figure_count)
        if rewritten != raw:
            changed_count += 1
        out.append(rewritten + newline)

    return "".join(out), figure_count, changed_count


def apply_numbering(target: Path, dry_run: bool) -> int:
    if not target.is_file():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    original = read_text_exact(target)
    transformed, figure_count, changed_count = renumber_figure_headers(original)

    if figure_count == 0:
        print(f"No figure callouts found in {target}")
        return 0

    normalized_original = normalize_figure_headers(original)
    normalized_transformed = normalize_figure_headers(transformed)
    if normalized_original != normalized_transformed:
        print("Validation failed: text outside figure header numbering changed.", file=sys.stderr)
        print(short_diff(normalized_original, normalized_transformed), file=sys.stderr)
        return 1

    if dry_run:
        print(f"Would update {target}")
        print(f"Figure callouts found: {figure_count}")
        print(f"Figure headers to rewrite: {changed_count}")
        return 0

    if changed_count == 0:
        print(f"Figure callouts already numbered in {target} (found {figure_count})")
        return 0

    backup = backup_path_for(target)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(transformed)
        temp_name = handle.name

    temp_path = Path(temp_name)
    try:
        written = read_text_exact(temp_path)
        if normalize_figure_headers(read_text_exact(backup)) != normalize_figure_headers(written):
            print("Validation failed after writing temp file. Original file preserved.", file=sys.stderr)
            temp_path.unlink(missing_ok=True)
            return 1

        shutil.move(str(temp_path), str(target))
    finally:
        temp_path.unlink(missing_ok=True)

    final_text = read_text_exact(target)
    if normalize_figure_headers(read_text_exact(backup)) != normalize_figure_headers(final_text):
        print("Validation failed after final write. Please restore from backup.", file=sys.stderr)
        return 1

    print(f"Updated: {target}")
    print(f"Backup:  {backup}")
    print(f"Renumbered {figure_count} figure callouts")
    print(f"Rewrote {changed_count} figure header lines")
    print("Validation passed: only figure header numbering changed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Renumber [!figure] callout headers in source order within a Markdown note."
    )
    parser.add_argument("file", help="Markdown file to update")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview how many figure headers would be rewritten without writing changes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return apply_numbering(Path(args.file).expanduser().resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
