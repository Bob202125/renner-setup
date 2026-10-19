#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def read_text_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def strip_newline(line: str) -> str:
    return line.rstrip("\r\n")


def is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    i = index - 1
    while i >= 0 and text[i] == "\\":
        backslashes += 1
        i -= 1
    return backslashes % 2 == 1


def line_end(text: str, index: int) -> int:
    end = text.find("\n", index)
    return len(text) if end == -1 else end + 1


def is_fence_line(text: str, index: int) -> bool:
    end = line_end(text, index)
    return text[index:end].lstrip(" \t").startswith(("```", "~~~"))


def scan_protected(text: str, index: int, in_display_math: bool) -> tuple[int, bool]:
    if in_display_math:
        if text.startswith("$$", index) and not is_escaped(text, index):
            return index + 2, False
        return index + 1, True

    if text.startswith("$$", index) and not is_escaped(text, index):
        return index + 2, True

    if text[index] == "$" and not is_escaped(text, index):
        j = index + 1
        while j < len(text):
            if text[j] == "$" and not is_escaped(text, j):
                return j + 1, in_display_math
            if text.startswith("\n", j):
                break
            j += 1
        return index + 1, in_display_math

    if text[index] == "`":
        tick_count = 1
        while index + tick_count < len(text) and text[index + tick_count] == "`":
            tick_count += 1
        delimiter = "`" * tick_count
        j = text.find(delimiter, index + tick_count)
        if j == -1:
            return index + tick_count, in_display_math
        return j + tick_count, in_display_math

    return index + 1, in_display_math


def parse_bracket_hint(text: str, start: int) -> tuple[str, int] | None:
    if not text.startswith("[Hint:", start):
        return None

    depth = 1
    i = start + 1
    in_display_math = False

    while i < len(text):
        if in_display_math or text.startswith("$$", i) or text[i] in "$`":
            i, in_display_math = scan_protected(text, i, in_display_math)
            continue

        if text[i] == "[" and not is_escaped(text, i):
            depth += 1
            i += 1
            continue

        if text[i] == "]" and not is_escaped(text, i):
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
            i += 1
            continue

        i += 1

    return None


def parse_bold_hint(text: str, start: int) -> tuple[str, int] | None:
    if not text.startswith("**(Hint:", start):
        return None

    depth = 1
    i = start + 3
    in_display_math = False

    while i < len(text):
        if in_display_math or text.startswith("$$", i) or text[i] in "$`":
            i, in_display_math = scan_protected(text, i, in_display_math)
            continue

        if text[i] == "(" and not is_escaped(text, i):
            depth += 1
            i += 1
            continue

        if text[i] == ")" and not is_escaped(text, i):
            depth -= 1
            if depth == 0 and text.startswith("**", i + 1):
                return text[start + 3 : i], i + 3
            i += 1
            continue

        i += 1

    return None


def transform_hints(text: str) -> tuple[str, int]:
    out: list[str] = []
    i = 0
    count = 0
    in_fenced_code = False
    in_display_math = False

    while i < len(text):
        at_line_start = i == 0 or text[i - 1] == "\n"

        if at_line_start and is_fence_line(text, i):
            end = line_end(text, i)
            out.append(text[i:end])
            in_fenced_code = not in_fenced_code
            i = end
            continue

        if in_fenced_code:
            end = line_end(text, i)
            out.append(text[i:end])
            i = end
            continue

        parsed_bold = parse_bold_hint(text, i)
        if parsed_bold is not None:
            content, end = parsed_bold
            out.append(text[i:end])
            i = end
            continue

        parsed_bracket = parse_bracket_hint(text, i)
        if parsed_bracket is not None:
            content, end = parsed_bracket
            out.append(f"**({content})**")
            count += 1
            i = end
            continue

        if in_display_math or text.startswith("$$", i) or text[i] in "$`":
            end, in_display_math = scan_protected(text, i, in_display_math)
            out.append(text[i:end])
            i = end
            continue

        out.append(text[i])
        i += 1

    return "".join(out), count


def normalize_hints(text: str) -> str:
    out: list[str] = []
    i = 0
    in_fenced_code = False
    in_display_math = False

    while i < len(text):
        at_line_start = i == 0 or text[i - 1] == "\n"

        if at_line_start and is_fence_line(text, i):
            end = line_end(text, i)
            out.append(text[i:end])
            in_fenced_code = not in_fenced_code
            i = end
            continue

        if in_fenced_code:
            end = line_end(text, i)
            out.append(text[i:end])
            i = end
            continue

        parsed_bold = parse_bold_hint(text, i)
        if parsed_bold is not None:
            content, end = parsed_bold
            out.append(f"[{content}]")
            i = end
            continue

        parsed_bracket = parse_bracket_hint(text, i)
        if parsed_bracket is not None:
            content, end = parsed_bracket
            out.append(f"[{content}]")
            i = end
            continue

        if in_display_math or text.startswith("$$", i) or text[i] in "$`":
            end, in_display_math = scan_protected(text, i, in_display_math)
            out.append(text[i:end])
            i = end
            continue

        out.append(text[i])
        i += 1

    return "".join(out)


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


def apply_formatting(target: Path, dry_run: bool) -> int:
    if not target.is_file():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    original = read_text_exact(target)
    transformed, converted = transform_hints(original)

    if not converted:
        print(f"No bracketed hints found in {target}")
        return 0

    normalized_original = normalize_hints(original)
    normalized_transformed = normalize_hints(transformed)
    if normalized_original != normalized_transformed:
        print("Validation failed: non-formatting text changed during transformation.", file=sys.stderr)
        print(short_diff(normalized_original, normalized_transformed), file=sys.stderr)
        return 1

    if dry_run:
        print(f"Would update {target}")
        print(f"Hints to format: {converted}")
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
        if normalize_hints(read_text_exact(backup)) != normalize_hints(written):
            print("Validation failed after writing temp file. Original file preserved.", file=sys.stderr)
            temp_path.unlink(missing_ok=True)
            return 1

        shutil.move(str(temp_path), str(target))
    finally:
        temp_path.unlink(missing_ok=True)

    print(f"Updated: {target}")
    print(f"Backup:  {backup}")
    print(f"Formatted {converted} hints")
    print("Validation passed: normalized non-formatting text is unchanged")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert bracketed [Hint: ...] spans into bold parenthesized hints."
    )
    parser.add_argument("file", help="Markdown file to update")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview how many hints would be formatted without writing changes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return apply_formatting(Path(args.file).expanduser().resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
