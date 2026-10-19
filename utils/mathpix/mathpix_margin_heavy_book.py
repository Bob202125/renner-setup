#!/usr/bin/env python3
"""Margin-heavy book converter for Obsidian-ready Mathpix markdown.

Use this script for scanned books whose margin notes or side commentary cause
Mathpix's normal PDF reading order to drop text or splice marginalia into the
main body. For clean chapter PDFs, prefer the standard md.zip workflow instead.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image


def _mathpix_headers() -> dict[str, str]:
    app_id = os.environ.get("MATHPIX_APP_ID", "").strip()
    app_key = os.environ.get("MATHPIX_APP_KEY", "").strip()
    if not app_id or not app_key:
        raise RuntimeError("Mathpix credentials missing: set MATHPIX_APP_ID and MATHPIX_APP_KEY")
    return {"app_id": app_id, "app_key": app_key}


def _request_json(method: str, url: str, body: bytes | None = None, content_type: str | None = None) -> object:
    headers = dict(_mathpix_headers())
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _request_bytes(method: str, url: str) -> bytes:
    req = urllib.request.Request(url, headers=_mathpix_headers(), method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _multipart_form(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = "----mathpixform-" + str(int(time.time() * 1000000))
    crlf = "\r\n"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}{crlf}".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}'.encode())
        parts.append(value.encode())
        parts.append(crlf.encode())
    for name, (filename, content, mimetype) in files.items():
        parts.append(f"--{boundary}{crlf}".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"{crlf}'.encode())
        parts.append(f"Content-Type: {mimetype}{crlf}{crlf}".encode())
        parts.append(content)
        parts.append(crlf.encode())
    parts.append(f"--{boundary}--{crlf}".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _submit_pdf_for_reference(pdf_path: Path) -> str:
    pdf_bytes = pdf_path.read_bytes()
    options = {"math_inline_delimiters": ["$", "$"]}
    body, ctype = _multipart_form(
        fields={"options_json": json.dumps(options)},
        files={"file": (pdf_path.name, pdf_bytes, "application/pdf")},
    )
    result = _request_json("POST", "https://api.mathpix.com/v3/pdf", body=body, content_type=ctype)
    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected Mathpix pdf response type: {type(result)!r}")
    pdf_id = result.get("pdf_id")
    if not isinstance(pdf_id, str) or not pdf_id:
        raise RuntimeError(f"Unexpected submission response: keys={sorted(result.keys())}")
    return pdf_id


def _wait_reference_complete(pdf_id: str, *, label: str) -> None:
    while True:
        status = _request_json("GET", f"https://api.mathpix.com/v3/pdf/{pdf_id}")
        if not isinstance(status, dict):
            raise RuntimeError(f"Unexpected Mathpix status response type: {type(status)!r}")
        state = status.get("status")
        if state == "completed":
            return
        if state in ("error", "failed"):
            raise RuntimeError(f"Mathpix reference conversion failed for {label}: {json.dumps(status)[:500]}")
        time.sleep(2)


def _download_reference_zip(pdf_id: str) -> bytes:
    for ext in ("md.zip", "mmd.zip"):
        try:
            return _request_bytes("GET", f"https://api.mathpix.com/v3/pdf/{pdf_id}.{ext}")
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                continue
            raise
    raise RuntimeError("No markdown zip format available for reference extraction.")


def _mathpix_ocr_png(png_bytes: bytes) -> str:
    payload = {
        "src": "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii"),
        "ocr": ["math", "text"],
        "formats": ["text"],
        "math_inline_delimiters": ["$", "$"],
        "rm_spaces": True,
        "skip_recrop": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.mathpix.com/v3/text",
        data=data,
        headers={**_mathpix_headers(), "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read()
    result = json.loads(body.decode("utf-8"))
    text = result.get("text")
    if not isinstance(text, str):
        raise RuntimeError(f"Unexpected Mathpix response keys: {sorted(result.keys())}")
    return text


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(r"\(", "$").replace(r"\)", "$")
    text = text.replace(r"\[", "$$").replace(r"\]", "$$")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_for_obsidian(text: str) -> str:
    return (
        text.replace(r"\(", "$")
        .replace(r"\)", "$")
        .replace(r"\[", "$$")
        .replace(r"\]", "$$")
    )


def _format_margin_block(title: str, text: str, images: list[str] | None = None) -> str:
    text = _normalize_text(text)
    images = images or []
    if not text and not images:
        return ""
    lines = text.splitlines() if text else []
    out = [title]
    image_idx = 0
    figure_line_re = re.compile(r"^\s*Figures?\b", re.I)

    def caption_image_count(line: str, remaining: int) -> int:
        if not re.match(r"^\s*Figures\b", line, re.I):
            return min(1, remaining)
        subfigs = re.findall(r"\([a-z]\)", line, flags=re.I)
        if subfigs:
            return min(len(subfigs), remaining)
        return min(1, remaining)

    if lines:
        out.append("")
        for line in lines:
            if figure_line_re.match(line) and image_idx < len(images):
                count = caption_image_count(line, len(images) - image_idx)
                out.extend(images[image_idx:image_idx + count])
                image_idx += count
                out.append("")
            out.append(line)
    if image_idx < len(images):
        out.append("")
        out.extend(images[image_idx:])
    return "\n".join(out)


def _nonwhite_ratio(img: Image.Image, *, threshold: int = 245) -> float:
    gray = img.convert("L")
    px = gray.load()
    width, height = gray.size
    dark = 0
    total = width * height
    for y in range(height):
        for x in range(width):
            if px[x, y] < threshold:
                dark += 1
    return dark / total if total else 0.0


@dataclass
class RegionResult:
    label: str
    text: str
    image_path: str | None


@dataclass
class ReferenceMaterial:
    md_path: Path
    image_map: dict[str, str]
    page_images: dict[int, list[str]]


def _save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def _ocr_region(
    img: Image.Image,
    *,
    label: str,
    image_path: Path | None,
    dark_ratio_threshold: float,
) -> RegionResult:
    ratio = _nonwhite_ratio(img)
    if ratio < dark_ratio_threshold:
        return RegionResult(label=label, text="", image_path=str(image_path) if image_path else None)
    if image_path is not None:
        _save_png(img, image_path)
    try:
        text = _mathpix_ocr_png(_image_to_png_bytes(img))
    except Exception as exc:
        if label in {"left", "right"}:
            print(f"Warning: skipping failed {label} margin OCR: {exc}", file=sys.stderr)
            return RegionResult(label=label, text="", image_path=str(image_path) if image_path else None)
        raise
    return RegionResult(label=label, text=_normalize_text(text), image_path=str(image_path) if image_path else None)


def _image_to_png_bytes(img: Image.Image) -> bytes:
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render_page(page: fitz.Page, zoom: float) -> Image.Image:
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def _crop(img: Image.Image, rect: tuple[int, int, int, int]) -> Image.Image:
    return img.crop(rect).convert("RGB")


def _find_text_spans(
    img: Image.Image,
    *,
    threshold: int = 235,
    min_dark_ratio_per_col: float = 0.01,
    merge_gap_px: int = 18,
    min_width_px: int = 30,
) -> list[tuple[int, int]]:
    gray = img.convert("L")
    width, height = gray.size
    px = gray.load()
    active = []
    for x in range(width):
        dark = 0
        for y in range(height):
            if px[x, y] < threshold:
                dark += 1
        active.append((dark / height) >= min_dark_ratio_per_col)

    spans: list[tuple[int, int]] = []
    in_span = False
    start = 0
    for x, is_active in enumerate(active):
        if is_active and not in_span:
            start = x
            in_span = True
        elif not is_active and in_span:
            spans.append((start, x))
            in_span = False
    if in_span:
        spans.append((start, width))

    merged: list[tuple[int, int]] = []
    for span in spans:
        if not merged:
            merged.append(span)
            continue
        prev = merged[-1]
        if span[0] - prev[1] <= merge_gap_px:
            merged[-1] = (prev[0], span[1])
        else:
            merged.append(span)

    return [span for span in merged if (span[1] - span[0]) >= min_width_px]


def _choose_regions(
    img: Image.Image,
    *,
    fallback_body_left: float,
    fallback_body_right: float,
    fallback_margin_width: float,
) -> dict[str, tuple[int, int, int, int]]:
    width, height = img.size
    body_left_bound = int(width * fallback_body_left)
    body_right_bound = int(width * fallback_body_right)
    spans = _find_text_spans(img)
    if not spans:
        return {
            "body": (body_left_bound, 0, body_right_bound, height),
            "left": (0, 0, body_left_bound, height),
            "right": (body_right_bound, 0, width, height),
        }

    center_x = width / 2
    center_candidates = [s for s in spans if s[0] <= center_x <= s[1]]
    if center_candidates:
        body_span = max(center_candidates, key=lambda s: s[1] - s[0])
    else:
        body_span = min(spans, key=lambda s: abs(((s[0] + s[1]) / 2) - center_x))

    pad = max(12, width // 100)
    body_left = max(body_left_bound, max(0, body_span[0] - pad))
    body_right = min(body_right_bound, min(width, body_span[1] + pad))
    if body_left >= body_right:
        body_left, body_right = body_left_bound, body_right_bound

    body = (body_left, 0, body_right, height)
    left = (0, 0, body_left, height)
    right = (body_right, 0, width, height)

    return {"body": body, "left": left, "right": right}


FIGURE_LINE_RE = re.compile(r"^(Figure\s+\d+(?:\.\d+)*)(?:\.|\b)(.*)$")
IMAGE_LINE_RE = re.compile(r"^!\[\]\(\./images/(?P<image>[^)]+)\)\s*$")


def _section_heading_re(chapter_number: int) -> re.Pattern[str]:
    return re.compile(rf"^(#+\s*)?{chapter_number}\.\d+\b")


def _extract_reference_markdown_zip(zip_bytes: bytes, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(dest_dir)
    md_files = sorted(dest_dir.rglob("*.md"))
    if not md_files:
        raise RuntimeError(f"No .md found after extracting reference zip into {dest_dir}")
    return md_files[0]


def _ensure_reference_material(src: Path, chapter_dir: Path, *, force: bool) -> ReferenceMaterial:
    ref_dir = chapter_dir / ".reference_mdzip"
    ref_md_path = ref_dir / "reference.md"
    if force and ref_dir.exists():
        shutil.rmtree(ref_dir)

    if not ref_md_path.exists():
        with tempfile.TemporaryDirectory(prefix="mathpix_margin_ref_") as tmp:
            tmp_dir = Path(tmp)
            pdf_id = _submit_pdf_for_reference(src)
            _wait_reference_complete(pdf_id, label=src.name)
            md_path = _extract_reference_markdown_zip(_download_reference_zip(pdf_id), tmp_dir)
            text = _normalize_for_obsidian(md_path.read_text(encoding="utf-8", errors="replace"))
            ref_dir.mkdir(parents=True, exist_ok=True)
            for item in tmp_dir.iterdir():
                shutil.move(str(item), str(ref_dir / item.name))
            extracted_md_files = sorted(ref_dir.rglob("*.md"))
            if not extracted_md_files:
                raise RuntimeError(f"No markdown found in extracted reference directory: {ref_dir}")
            main_md = extracted_md_files[0]
            if main_md != ref_md_path:
                if ref_md_path.exists():
                    ref_md_path.unlink()
                main_md.rename(ref_md_path)
            ref_md_path.write_text(text, encoding="utf-8")

    chapter_images_dir = chapter_dir / "images"
    ref_images_dir = ref_dir / "images"
    if ref_images_dir.exists():
        for image_path in ref_images_dir.iterdir():
            if not image_path.is_file():
                continue
            target = chapter_images_dir / image_path.name
            if force or not target.exists():
                shutil.copy2(image_path, target)

    text = ref_md_path.read_text(encoding="utf-8", errors="replace")
    image_map: dict[str, str] = {}
    page_images: dict[int, list[str]] = {}
    page_image_re = re.compile(r"-(?P<page>\d+)_")
    lines = text.splitlines()
    for image_line in lines:
        image_match = IMAGE_LINE_RE.match(image_line.strip())
        if not image_match:
            continue
        image_name = image_match.group("image")
        page_match = page_image_re.search(image_name)
        if not page_match:
            continue
        page_no = int(page_match.group("page"))
        md = f"![](./images/{image_name})"
        page_images.setdefault(page_no, [])
        if md not in page_images[page_no]:
            page_images[page_no].append(md)

    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        figure_match = FIGURE_LINE_RE.match(line)
        if not figure_match:
            continue

        image_name = None
        for offset in (-2, -1, 1, 2):
            other_idx = idx + offset
            if other_idx < 0 or other_idx >= len(lines):
                continue
            other = lines[other_idx].strip()
            if not other:
                continue
            image_match = IMAGE_LINE_RE.match(other)
            if image_match:
                image_name = image_match.group("image")
                break

        if image_name is None:
            continue

        label = figure_match.group(1)
        image_map[label] = f"![](./images/{image_name})"

    return ReferenceMaterial(md_path=ref_md_path, image_map=image_map, page_images=page_images)


def _split_tabular_rows(body: str) -> list[list[str]]:
    cleaned = re.sub(r"\\hline\b", "", body)
    cleaned = cleaned.replace("\n", " ")
    raw_rows = [row.strip() for row in re.split(r"\\\\", cleaned) if row.strip()]
    rows: list[list[str]] = []
    for row in raw_rows:
        cells = [re.sub(r"\s+", " ", cell.strip()) for cell in re.split(r"(?<!\\)&", row)]
        if any(cell for cell in cells):
            rows.append(cells)
    return rows


def _alignment_markers(spec: str, count: int) -> list[str]:
    markers: list[str] = []
    for token in re.findall(r"[lcr]|p\{[^}]+\}|m\{[^}]+\}|b\{[^}]+\}", spec):
        if token.startswith("r"):
            markers.append("---:")
        elif token.startswith("c"):
            markers.append(":---:")
        else:
            markers.append(":---")
    while len(markers) < count:
        markers.append(":---")
    return markers[:count]


def _tabular_to_markdown(spec: str, body: str) -> str:
    rows = _split_tabular_rows(body)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (width - len(row)) for row in rows]
    align = _alignment_markers(spec, width)

    def fmt_row(row: list[str]) -> str:
        cells = [cell.replace("|", r"\|").strip() for cell in row]
        return "| " + " | ".join(cells) + " |"

    lines = [fmt_row(normalized_rows[0]), "| " + " | ".join(align) + " |"]
    for row in normalized_rows[1:]:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def _convert_tabular_blocks(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        converted = _tabular_to_markdown(match.group("spec"), match.group("body"))
        return converted if converted else match.group(0)

    return re.sub(
        r"\\begin\{tabular\}\{(?P<spec>[^}]*)\}(?P<body>.*?)\\end\{tabular\}",
        repl,
        text,
        flags=re.S,
    )


def _insert_reference_images(text: str, image_map: dict[str, str]) -> str:
    lines = text.splitlines()
    out: list[str] = []
    labels = sorted(image_map.items(), key=lambda item: len(item[0]), reverse=True)
    in_margin_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Left margin note (page ") or stripped.startswith("Right margin note (page "):
            in_margin_block = True
        elif stripped == "++++":
            in_margin_block = False
        inserted = False
        if not in_margin_block:
            for label, image_md in labels:
                if re.match(rf"^{re.escape(label)}(?:\.|\b|\s)", stripped):
                    if not out or out[-1].strip() != image_md:
                        out.append(image_md)
                    inserted = True
                    break
        out.append(line)

    return "\n".join(out)


def _postprocess_full_markdown(text: str, reference: ReferenceMaterial | None) -> str:
    text = _normalize_text(text)
    text = _convert_tabular_blocks(text)
    if reference is not None:
        text = _insert_reference_images(text, reference.image_map)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip() + "\n"


def _clean_reference_heading(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text)
    text = text.replace("$", "")
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _reference_section_titles(chapter_dir: Path, chapter_number: int) -> dict[str, str]:
    ref_md = chapter_dir / ".reference_mdzip" / "reference.md"
    if not ref_md.exists():
        return {}
    text = ref_md.read_text(encoding="utf-8", errors="replace")
    titles: dict[str, str] = {}
    for match in re.finditer(rf"(?m)^#+\s*({chapter_number}\.\d+)\s+(.+)$", text):
        number = match.group(1)
        if number.count(".") != 1:
            continue
        titles[number] = _clean_reference_heading(match.group(2)) or "Section"
    return titles


def _split_sections(
    chapter_number: int,
    chapter_dir: Path,
    full_md_name: str,
    *,
    section_filter: str | None = None,
) -> None:
    full_md = chapter_dir / "original copy" / full_md_name
    text = full_md.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    reference_titles = _reference_section_titles(chapter_dir, chapter_number)
    section_start_re = re.compile(
        rf"^(?:#+\s*)?(?:Section\s+)?({chapter_number}\.\d+)(?!\.)\s+(.+)$"
    )
    page_marker_re = re.compile(r"^<!-- Page \d+ -->$")
    page_starts = [idx for idx, line in enumerate(lines) if page_marker_re.match(line.strip())]

    def page_start_at_or_before(idx: int) -> int:
        candidate = 0
        for page_idx in page_starts:
            if page_idx > idx:
                break
            candidate = page_idx
        return candidate

    starts: list[tuple[str, int, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        m = section_start_re.match(stripped)
        if not m:
            continue
        number = m.group(1)
        if number.count(".") != 1:
            continue
        if reference_titles and number not in reference_titles:
            continue
        title = reference_titles.get(number, m.group(2).strip() or "Section")
        if any(existing[0] == number for existing in starts):
            continue
        starts.append((number, page_start_at_or_before(idx), title))

    if not starts:
        main_out = chapter_dir / full_md_name
        main_out.write_text(text, encoding="utf-8")
        return

    if section_filter is None:
        for md in chapter_dir.glob("*.md"):
            md.unlink()
    else:
        for md in chapter_dir.glob(f"{section_filter} *.md"):
            md.unlink()

    for i, (number, start, title) in enumerate(starts):
        if section_filter is not None and number != section_filter:
            continue
        end = starts[i + 1][1] if i + 1 < len(starts) else len(lines)
        chunk = "\n".join(lines[start:end]).rstrip() + "\n"
        safe_title = re.sub(r'[\\/:*?"<>|]', "-", title)
        safe_title = re.sub(r"\s+", " ", safe_title).strip()
        safe_title = safe_title[:120].rstrip()
        out = chapter_dir / f"{number} {safe_title}.md"
        out.write_text(chunk, encoding="utf-8")


def _page_block(
    page_no: int,
    body_text: str,
    left_text: str,
    right_text: str,
    *,
    page_images: list[str] | None = None,
) -> str:
    parts = [f"<!-- Page {page_no} -->", ""]
    page_images = page_images or []
    margin_text = "\n".join(piece for piece in (left_text, right_text) if piece.strip())
    margin_images = page_images if re.search(r"\bFigures?\b", margin_text, flags=re.I) else []
    if left_text:
        parts.append(_format_margin_block(f"Left margin note (page {page_no})", left_text, margin_images))
        parts.append("")
        margin_images = []
    if right_text:
        parts.append(_format_margin_block(f"Right margin note (page {page_no})", right_text, margin_images))
        parts.append("")
        margin_images = []
    if body_text and (left_text or right_text):
        parts.append("++++")
        parts.append("")
    if body_text:
        parts.append(body_text)
        parts.append("")
    return "\n".join(parts).rstrip()


def _load_cache(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_cache(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert margin-heavy scanned book chapters into Obsidian-ready Markdown."
    )
    p.add_argument("--src", required=True, help="Source chapter PDF.")
    p.add_argument("--out-root", required=True, help="Root directory for the converted chapter folders.")
    p.add_argument("--chapter-name", required=True, help="Chapter folder and main markdown name, e.g. '0 Preliminaries'.")
    p.add_argument("--zoom", type=float, default=2.0, help="Render zoom factor for OCR.")
    p.add_argument("--body-left", type=float, default=0.20, help="Body crop left boundary as fraction of page width.")
    p.add_argument("--body-right", type=float, default=0.92, help="Body crop right boundary as fraction of page width.")
    p.add_argument("--margin-width", type=float, default=0.26, help="Margin crop width as fraction of page width.")
    p.add_argument("--dark-ratio-threshold", type=float, default=0.003, help="Skip OCR for nearly blank margin crops.")
    p.add_argument("--chapter-number", type=int, default=0, help="Chapter number used to split 0.x/1.x/etc section files.")
    p.add_argument("--section-filter", default=None, help="Optional section number to rebuild, e.g. '6.3'.")
    p.add_argument("--split-only", action="store_true", help="Rebuild split markdown from the saved combined markdown without rerunning OCR.")
    p.add_argument("--max-pages", type=int, default=None, help="Optional limit for testing.")
    p.add_argument("--force", action="store_true", help="Re-run OCR even if cached per-page results exist.")
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    src = Path(args.src).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    chapter_dir = out_root / args.chapter_name
    original_copy_dir = chapter_dir / "original copy"
    images_dir = chapter_dir / "images"
    region_dir = images_dir / "ocr_regions"
    cache_dir = chapter_dir / ".ocr_cache"

    original_copy_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    original_pdf_copy = original_copy_dir / src.name
    if not original_pdf_copy.exists():
        original_pdf_copy.write_bytes(src.read_bytes())

    full_md_name = f"{args.chapter_name}.md"
    full_md_path = original_copy_dir / full_md_name

    if args.split_only:
        if not full_md_path.exists():
            raise RuntimeError(f"Combined markdown not found for split-only mode: {full_md_path}")
        _split_sections(
            args.chapter_number,
            chapter_dir,
            full_md_name,
            section_filter=args.section_filter,
        )
        print(chapter_dir)
        return 0

    print("Preparing reference figures/tables ...", file=sys.stderr)
    reference = _ensure_reference_material(src, chapter_dir, force=args.force)

    doc = fitz.open(src)
    try:
        limit = min(len(doc), args.max_pages) if args.max_pages else len(doc)
        page_chunks: list[str] = []

        for page_index in range(limit):
            page_no = page_index + 1
            page = doc[page_index]
            cache_path = cache_dir / f"page_{page_no:03d}.json"

            if cache_path.exists() and not args.force:
                cached = _load_cache(cache_path)
                assert cached is not None
                body_text = str(cached.get("body_text", ""))
                left_text = str(cached.get("left_text", ""))
                right_text = str(cached.get("right_text", ""))
            else:
                print(f"OCR page {page_no}/{limit} ...", file=sys.stderr)
                img = _render_page(page, args.zoom)
                width, height = img.size
                rects = _choose_regions(
                    img,
                    fallback_body_left=args.body_left,
                    fallback_body_right=args.body_right,
                    fallback_margin_width=args.margin_width,
                )
                body_rect = rects["body"]
                left_rect = rects["left"]
                right_rect = rects["right"]

                body = _ocr_region(
                    _crop(img, body_rect),
                    label="body",
                    image_path=region_dir / f"page_{page_no:03d}_body.png",
                    dark_ratio_threshold=0.0,
                )
                left = _ocr_region(
                    _crop(img, left_rect) if left_rect[2] > left_rect[0] else Image.new("RGB", (1, height), "white"),
                    label="left",
                    image_path=region_dir / f"page_{page_no:03d}_left.png",
                    dark_ratio_threshold=args.dark_ratio_threshold,
                )
                right = _ocr_region(
                    _crop(img, right_rect) if right_rect[2] > right_rect[0] else Image.new("RGB", (1, height), "white"),
                    label="right",
                    image_path=region_dir / f"page_{page_no:03d}_right.png",
                    dark_ratio_threshold=args.dark_ratio_threshold,
                )

                body_text = body.text
                left_text = left.text
                right_text = right.text

                _save_cache(
                    cache_path,
                    {
                        "page": page_no,
                        "body_text": body_text,
                        "left_text": left_text,
                        "right_text": right_text,
                        "body_image": body.image_path,
                        "left_image": left.image_path,
                        "right_image": right.image_path,
                    },
                )

            page_chunks.append(
                _page_block(
                    page_no,
                    body_text,
                    left_text,
                    right_text,
                    page_images=reference.page_images.get(page_no, []),
                )
            )

        merged = "\n\n---\n\n".join(page_chunks)
        full_md_path.write_text(_postprocess_full_markdown(merged, reference), encoding="utf-8")
        _split_sections(
            args.chapter_number,
            chapter_dir,
            full_md_name,
            section_filter=args.section_filter,
        )
        print(chapter_dir)
        return 0
    finally:
        doc.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
