#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit


def read_text_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text_exact(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def line_end(text: str, index: int) -> int:
    end = text.find("\n", index)
    return len(text) if end == -1 else end + 1


def parse_fence(line: str) -> tuple[str, int] | None:
    i = 0
    n = len(line)

    while i < n and line[i] in " \t":
        i += 1

    while True:
        if i + 1 < n and line[i] == ">" and line[i + 1] == " ":
            i += 2
            continue
        if i < n and line[i] == ">":
            i += 1
            if i < n and line[i] == " ":
                i += 1
            continue
        break

    if i >= n or line[i] not in "`~":
        return None

    ch = line[i]
    j = i
    while j < n and line[j] == ch:
        j += 1

    count = j - i
    if count < 3:
        return None

    return ch, count


def strip_fenced_code_blocks(text: str) -> tuple[str, int]:
    out: list[str] = []
    i = 0
    in_fence = False
    fence_char = ""
    fence_len = 0
    removed = 0

    while i < len(text):
        end = line_end(text, i)
        line = text[i:end]
        fence = parse_fence(line.rstrip("\r\n"))

        if not in_fence:
            if fence is not None:
                in_fence = True
                fence_char, fence_len = fence
                removed += 1
            else:
                out.append(line)
        else:
            if fence is not None and fence[0] == fence_char and fence[1] >= fence_len:
                in_fence = False
                fence_char = ""
                fence_len = 0

        i = end

    return "".join(out), removed


def rewrite_link_inner(inner: str, source_dir: Path, dest_dir: Path) -> str:
    stripped = inner.strip()
    if not stripped:
        return inner

    if stripped.startswith("<"):
        close = stripped.find(">")
        if close == -1:
            return inner
        dest = stripped[1:close]
        suffix = stripped[close + 1 :]
        wrapped = True
    else:
        parts = stripped.split(None, 1)
        dest = parts[0]
        suffix = f" {parts[1]}" if len(parts) == 2 else ""
        wrapped = False

    lower = dest.lower()
    if (
        not dest
        or dest.startswith(("/", "#"))
        or lower.startswith(("http://", "https://", "mailto:", "obsidian:", "data:", "file:", "app://"))
    ):
        return inner

    split = urlsplit(dest)
    if split.scheme or not split.path:
        return inner

    source_path = Path(unquote(split.path))
    candidate = (source_dir / source_path).resolve(strict=False)

    # Obsidian notes in this vault often use bare attachment names that are
    # resolved via the vault's attachment folder setting rather than by a
    # literal sibling path. If the literal source-relative path does not
    # exist, but source_dir/images/<path> does, preserve that intended image
    # target in the copied note.
    if candidate.exists():
        absolute_target = candidate
    else:
        image_candidate = (source_dir / "images" / source_path).resolve(strict=False)
        absolute_target = image_candidate if image_candidate.exists() else candidate

    relative_target = Path(shutil.os.path.relpath(absolute_target, dest_dir)).as_posix()
    encoded_relative_target = quote(relative_target, safe="/")
    rewritten_dest = urlunsplit(("", "", encoded_relative_target, split.query, split.fragment))

    if wrapped:
        rewritten = f"<{rewritten_dest}>{suffix}"
    else:
        rewritten = f"{rewritten_dest}{suffix}"

    left_padding = inner[: len(inner) - len(inner.lstrip())]
    right_padding = inner[len(inner.rstrip()) :]
    return f"{left_padding}{rewritten}{right_padding}"


def rewrite_relative_markdown_links(text: str, source_dir: Path, dest_dir: Path) -> str:
    out: list[str] = []
    i = 0

    while i < len(text):
        if text[i] == "[" or (text[i] == "!" and i + 1 < len(text) and text[i + 1] == "["):
            start = i
            if text[i] == "!":
                i += 1
            if text[i] != "[":
                out.append(text[start])
                i = start + 1
                continue

            depth = 0
            j = i
            while j < len(text):
                if text[j] == "[":
                    depth += 1
                elif text[j] == "]":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1

            if j >= len(text) or j + 1 >= len(text) or text[j + 1] != "(":
                out.append(text[start])
                i = start + 1
                continue

            k = j + 2
            paren_depth = 1
            while k < len(text):
                if text[k] == "(":
                    paren_depth += 1
                elif text[k] == ")":
                    paren_depth -= 1
                    if paren_depth == 0:
                        break
                k += 1

            if k >= len(text):
                out.append(text[start])
                i = start + 1
                continue

            link_prefix = text[start : j + 2]
            link_inner = text[j + 2 : k]
            link_suffix = ")"
            out.append(link_prefix)
            out.append(rewrite_link_inner(link_inner, source_dir, dest_dir))
            out.append(link_suffix)
            i = k + 1
            continue

        out.append(text[i])
        i += 1

    return "".join(out)


def apply_strip(target: Path, dry_run: bool) -> int:
    if not target.is_file():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    original = read_text_exact(target)
    stripped, removed = strip_fenced_code_blocks(original)

    dest_dir = target.parent / "No Code"
    dest_path = dest_dir / target.name
    rewritten = rewrite_relative_markdown_links(stripped, target.parent, dest_dir)

    if dry_run:
        print(f"Would create: {dest_dir}")
        print(f"Would write:  {dest_path}")
        print(f"Fenced code blocks removed: {removed}")
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=str(dest_dir),
        prefix=f".{target.stem}.",
        suffix=target.suffix or ".tmp",
    ) as handle:
        handle.write(rewritten)
        temp_name = handle.name

    temp_path = Path(temp_name)
    try:
        shutil.move(str(temp_path), str(dest_path))
    finally:
        temp_path.unlink(missing_ok=True)

    print(f"Created: {dest_path}")
    print(f"Fenced code blocks removed: {removed}")
    print("Relative markdown links rewritten for the No Code copy")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a No Code copy of a Markdown note by removing fenced code blocks."
    )
    parser.add_argument("file", help="Markdown file to copy into a sibling 'No Code' folder")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the destination and number of removed code blocks without writing changes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return apply_strip(Path(args.file).expanduser().resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
