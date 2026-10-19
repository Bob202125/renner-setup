# Mathpix PDF → Obsidian Markdown (with offline images)

This directory contains small utilities for converting scanned/text PDFs into Markdown using the Mathpix Convert API.

The default method is still the chapter-based workflow that downloads **`md.zip`** from Mathpix so the output includes a local `images/` folder. That makes the resulting notes fully usable **offline** inside Obsidian.

## Which workflow to use

Use the standard chapter-based `md.zip` workflow for normal PDFs and clean scans.

Do not use the margin-heavy workflow for now. It has not worked well in practice, and there is no reliable fix yet. If a PDF has difficult marginalia, still start from the standard chapter-based `md.zip` workflow and then inspect/repair the Markdown manually.

The intended split is:

- Standard clean-book workflow: `/Users/gradyclopton/ObsidianVaults/me_510/tools/mathpix_chapters_to_obsidian.py`
- Deprecated margin-heavy scanned-book workflow: `/Users/gradyclopton/utils/mathpix/mathpix_margin_heavy_book.py`

The deprecated margin-heavy workflow is more specialized and more expensive because it combines page-wise OCR with a temporary `md.zip` reference pass for figures and tables. Leave it unused until the workflow is repaired and revalidated.

## Requirements

You need Mathpix API credentials available as environment variables:

- `MATHPIX_APP_ID`
- `MATHPIX_APP_KEY`

You also need Python 3 available.

## Recommended workflow (the default method)

This is the chapter-based method used for the Anderson book conversion.

### 1) Split the book into chapter PDFs

Mathpix works best when you submit one chapter PDF at a time (faster retries, cleaner output boundaries, easier organization).

You can split chapters using Adobe/PDFsam, or you can use the helper in the vault:

```bash
python3 /Users/gradyclopton/ObsidianVaults/me_510/tools/pdf_process.py split \
  --src "/path/to/Book.pdf" \
  --sections-json "/path/to/sections.json"
```

The result is a directory that contains one PDF per chapter (and no front/back matter PDFs unless you include them).

### 2) Convert those chapter PDFs into Obsidian-ready Markdown (with images)

Use the converter script in the vault:

```bash
python3 /Users/gradyclopton/ObsidianVaults/me_510/tools/mathpix_chapters_to_obsidian.py \
  --src-dir "/path/to/chapter_pdfs_dir" \
  --out-dir "/Users/gradyclopton/ObsidianVaults/me_510/Books/<BookName>"
```

What this script does (the key points):

It submits each chapter PDF to Mathpix `/v3/pdf`, waits for completion, and then downloads `md.zip` for each chapter (not just a `.md` file). The zip contains the Markdown plus an `images/` folder, and the Markdown uses relative links like `![](./images/...)`, so everything works in Obsidian even without internet.

It also normalizes MathJax delimiters so Obsidian renders math correctly:

- `\(...\)` → `$...$`
- `\[...\]` → `$$...$$`

It is resumable: it writes a small state file at:

`<out-dir>/.mathpix_state.json`

If you rerun the command, it will reuse the saved `pdf_id`s and skip already-written chapter folders unless you pass `--force`.

### Output layout inside Obsidian

For each chapter PDF, the script writes a folder like:

`<out-dir>/<chapter folder>/`

containing:

- one `*.md` file (the chapter text)
- `images/` (all extracted figures as local files)

This keeps each chapter self-contained and easy to move around.

## Margin-heavy workflow

Do not use this workflow for now. It has produced poor results, and the current guidance is to avoid it until it can be repaired and revalidated.

The script is:

`/Users/gradyclopton/utils/mathpix/mathpix_margin_heavy_book.py`

Typical invocation:

```bash
python3 /Users/gradyclopton/utils/mathpix/mathpix_margin_heavy_book.py \
  --src "/path/to/chapter.pdf" \
  --out-root "/path/to/vault/Books/<Author>" \
  --chapter-name "0 Preliminaries" \
  --chapter-number 0
```

What this script does:

- performs page-wise OCR on the chapter PDF,
- separates the main body from left and right margin regions,
- keeps local `images/` files for figures,
- converts detected `tabular` output into Obsidian-compatible Markdown tables,
- keeps the original PDF in `original copy/`,
- writes a full combined backup markdown file into `original copy/`,
- and splits the chapter into `0.1`, `0.2`, `1.1`, `1.2`, and similar section files at the top level of the chapter folder.

This section is retained only as a record of the deprecated tool. Do not use it for new conversions.

## About `mathpixpdf.sh`

`mathpixpdf.sh` is a convenience wrapper for basic conversions that downloads a single Markdown file from Mathpix. It is still useful for quick one-off conversions, but it is **not** the default method for Obsidian book workflows because it does not reliably produce an offline `images/` folder the way the `md.zip` approach does.
