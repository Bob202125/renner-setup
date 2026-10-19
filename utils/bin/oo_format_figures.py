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

IMAGE_RE = re.compile(r"^!(\[[^\n]*\]\([^\n]*\)|\[\[[^\n]+\]\])\s*$")
FIGURE_NUMBER_RE = r"\d+(?:\([A-Za-z]\))?"
FIGURE_ID_RE = rf"Figure {FIGURE_NUMBER_RE}"
FIGURE_MENTION_BODY_RE = (
    rf"Figures?\s+{FIGURE_NUMBER_RE}"
    rf"(?:(?:\s*[-–]\s*|\s*,\s*|\s+and\s+|\s+or\s+){FIGURE_NUMBER_RE})*"
)
CAPTION_RE = re.compile(rf"^({FIGURE_ID_RE})(.*)$")
CALLOUT_HEADER_RE = re.compile(r"^> \[!figure\](?:\s+(.*))?\s*$")
FIGURE_MENTION_RE = re.compile(rf"(?<![\w`])({FIGURE_MENTION_BODY_RE})(?=$|[\s\.,;:!?\)\]])")
ITALICIZED_FIGURE_MENTION_RE = re.compile(rf"_({FIGURE_MENTION_BODY_RE})_")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")


def read_text_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text_exact(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def strip_newline(line: str) -> str:
    return line.rstrip("\r\n")


def detect_newline(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def transform_figures(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines(keepends=True)
    newline = detect_newline(text)
    converted: list[str] = []
    out: list[str] = []
    i = 0

    while i < len(lines):
        current = strip_newline(lines[i])
        if IMAGE_RE.match(current):
            if i + 1 < len(lines):
                next_line = strip_newline(lines[i + 1])
                caption_match = CAPTION_RE.match(next_line)
                if caption_match:
                    out.extend(
                        [
                            f"> [!figure]{newline}",
                            f"> {newline}",
                            f"> {current}{newline}",
                            f"> {next_line}{newline}",
                        ]
                    )
                    converted.append(caption_match.group(1))
                    i += 2
                    continue

            if i + 2 < len(lines) and strip_newline(lines[i + 1]).strip() == "":
                caption_line = strip_newline(lines[i + 2])
                caption_match = CAPTION_RE.match(caption_line)
                if caption_match:
                    out.extend(
                        [
                            f"> [!figure]{newline}",
                            f"> {newline}",
                            f"> {current}{newline}",
                            f"> {caption_line}{newline}",
                        ]
                    )
                    converted.append(caption_match.group(1))
                    i += 3
                    continue

        out.append(lines[i])
        i += 1

    return "".join(out), converted


def is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    i = index - 1
    while i >= 0 and text[i] == "\\":
        backslashes += 1
        i -= 1
    return backslashes % 2 == 1


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []

    spans = sorted(spans)
    merged = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def find_inline_protected_spans(
    line: str, in_display_math: bool
) -> tuple[list[tuple[int, int]], bool]:
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(line)

    while i < n:
        if in_display_math:
            end = line.find("$$", i)
            while end != -1 and is_escaped(line, end):
                end = line.find("$$", end + 2)
            if end == -1:
                spans.append((i, n))
                return merge_spans(spans), True
            spans.append((i, end + 2))
            i = end + 2
            in_display_math = False
            continue

        if line.startswith("$$", i) and not is_escaped(line, i):
            end = line.find("$$", i + 2)
            while end != -1 and is_escaped(line, end):
                end = line.find("$$", end + 2)
            if end == -1:
                spans.append((i, n))
                return merge_spans(spans), True
            spans.append((i, end + 2))
            i = end + 2
            continue

        if line[i] == "$" and not is_escaped(line, i):
            end = i + 1
            while end < n:
                if line[end] == "$" and not is_escaped(line, end):
                    break
                end += 1
            if end >= n:
                spans.append((i, n))
                return merge_spans(spans), in_display_math
            spans.append((i, end + 1))
            i = end + 1
            continue

        if line[i] == "`":
            tick_count = 1
            while i + tick_count < n and line[i + tick_count] == "`":
                tick_count += 1
            closing = line.find("`" * tick_count, i + tick_count)
            if closing == -1:
                spans.append((i, n))
                return merge_spans(spans), in_display_math
            spans.append((i, closing + tick_count))
            i = closing + tick_count
            continue

        i += 1

    return merge_spans(spans), in_display_math


def wrap_mentions_in_segment(segment: str) -> tuple[str, int]:
    out: list[str] = []
    count = 0
    last = 0

    for match in FIGURE_MENTION_RE.finditer(segment):
        start, end = match.span(1)
        before = segment[start - 1] if start > 0 else ""
        after = segment[end] if end < len(segment) else ""
        if before in "_*" or after in "_*":
            continue

        out.append(segment[last:start])
        out.append(f"_{match.group(1)}_")
        last = end
        count += 1

    out.append(segment[last:])
    return "".join(out), count


def transform_figure_mentions(text: str) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    converted = 0
    in_figure_callout = False
    in_fenced_code = False
    in_display_math = False

    for line in lines:
        raw = strip_newline(line)
        newline = line[len(raw) :]

        if in_figure_callout:
            if raw.startswith(">"):
                out.append(line)
                continue
            in_figure_callout = False

        if CALLOUT_HEADER_RE.match(raw):
            in_figure_callout = True
            out.append(line)
            continue

        if FENCE_RE.match(raw):
            in_fenced_code = not in_fenced_code
            out.append(line)
            continue

        if in_fenced_code or IMAGE_RE.match(raw) or CAPTION_RE.match(raw):
            out.append(line)
            continue

        protected_spans, in_display_math = find_inline_protected_spans(raw, in_display_math)
        if not protected_spans:
            transformed, count = wrap_mentions_in_segment(raw)
            out.append(transformed + newline)
            converted += count
            continue

        pieces: list[str] = []
        cursor = 0
        count = 0
        for start, end in protected_spans:
            if cursor < start:
                transformed, local_count = wrap_mentions_in_segment(raw[cursor:start])
                pieces.append(transformed)
                count += local_count
            pieces.append(raw[start:end])
            cursor = end

        if cursor < len(raw):
            transformed, local_count = wrap_mentions_in_segment(raw[cursor:])
            pieces.append(transformed)
            count += local_count

        out.append("".join(pieces) + newline)
        converted += count

    return "".join(out), converted


def normalize_figure_blocks(text: str) -> str:
    lines = text.splitlines(keepends=True)
    normalized: list[str] = []
    i = 0

    while i < len(lines):
        current = strip_newline(lines[i])

        callout_match = CALLOUT_HEADER_RE.match(current)
        if callout_match:
            header_title = (callout_match.group(1) or "").strip()
            figure_name = None
            header_caption_match = CAPTION_RE.match(header_title)
            if header_caption_match:
                figure_name = header_caption_match.group(1)

            i += 1
            while i < len(lines) and strip_newline(lines[i]).startswith(">"):
                quoted = strip_newline(lines[i])[1:].lstrip()
                caption_match = CAPTION_RE.match(quoted)
                if caption_match and figure_name is None:
                    figure_name = caption_match.group(1)
                i += 1

            normalized.append(f"<<{figure_name or 'FIGURE'}>>\n")
            continue

        if IMAGE_RE.match(current):
            if i + 1 < len(lines):
                caption_match = CAPTION_RE.match(strip_newline(lines[i + 1]))
                if caption_match:
                    normalized.append(f"<<{caption_match.group(1)}>>\n")
                    i += 2
                    continue

            if i + 2 < len(lines) and strip_newline(lines[i + 1]).strip() == "":
                caption_match = CAPTION_RE.match(strip_newline(lines[i + 2]))
                if caption_match:
                    normalized.append(f"<<{caption_match.group(1)}>>\n")
                    i += 3
                    continue

        normalized.append(lines[i])
        i += 1

    return "".join(normalized)


def normalize_transformations(text: str) -> str:
    text = normalize_figure_blocks(text)
    text = ITALICIZED_FIGURE_MENTION_RE.sub(r"\1", text)
    return text


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
    figure_transformed, figure_converted = transform_figures(original)
    transformed, mention_converted = transform_figure_mentions(figure_transformed)

    if not figure_converted and not mention_converted:
        print(f"No standalone figure blocks or unitalicized figure mentions found in {target}")
        return 0

    normalized_original = normalize_transformations(original)
    normalized_transformed = normalize_transformations(transformed)
    if normalized_original != normalized_transformed:
        print("Validation failed: non-formatting text changed during transformation.", file=sys.stderr)
        print(short_diff(normalized_original, normalized_transformed), file=sys.stderr)
        return 1

    if dry_run:
        print(f"Would update {target}")
        print(f"Figure callouts to add: {len(figure_converted)}")
        if figure_converted:
            print(", ".join(figure_converted))
        print(f"Figure mentions to italicize: {mention_converted}")
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
        if normalize_transformations(read_text_exact(backup)) != normalize_transformations(written):
            print("Validation failed after writing temp file. Original file preserved.", file=sys.stderr)
            temp_path.unlink(missing_ok=True)
            return 1

        shutil.move(str(temp_path), str(target))
    finally:
        temp_path.unlink(missing_ok=True)

    final_text = read_text_exact(target)
    bare_images = sum(
        1 for line in final_text.splitlines() if IMAGE_RE.match(line)
    )
    callouts = sum(
        1 for line in final_text.splitlines() if CALLOUT_HEADER_RE.match(line)
    )
    italicized_mentions = len(ITALICIZED_FIGURE_MENTION_RE.findall(final_text))

    print(f"Updated: {target}")
    print(f"Backup:  {backup}")
    print(f"Converted {len(figure_converted)} figures: {', '.join(figure_converted)}")
    print(f"Italicized {mention_converted} figure mentions")
    print(f"Validation passed: normalized non-formatting text is unchanged")
    print(
        f"Final counts: {callouts} figure callouts, {bare_images} bare image lines, "
        f"{italicized_mentions} italicized figure mentions"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Wrap standalone Obsidian image+Figure caption blocks in [!figure] callouts "
            "and italicize figure mentions in prose."
        )
    )
    parser.add_argument("file", help="Markdown file to update")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which figures would be converted without writing changes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return apply_formatting(Path(args.file).expanduser().resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
