---
name: study-transcribe
description: Transcribe mathematical PDF chapters, including scans, to Markdown and JSON with local Pix2Text models and an offline review HTML. Use when preserving equations and minimizing hosted AI-token use matters.
---

# Study Transcribe

Use the local math workflow in [README.md](README.md). Run scripts relative to this skill folder with its `.venv-math` or an explicitly configured compatible Python runtime. `scripts/setup_math.py` installs a runtime with Python 3.11. Initial packages/models require network access; OCR inference runs locally with sockets disabled.

- Select inclusive **PDF page numbers**, not printed page numbers. Inspect the contents or source before choosing a chapter. `scripts/new_math_project.py` creates a project without changing its source. Multiple books can be represented in its `books` list.
- Default to Pix2Text for equation-rich pages and scanned books. Keep legacy `scripts/run.py --no-formula-ocr` for native prose extraction. Legacy `--allow-scanned` is not OCR.
- Prepare models with `scripts/local_math_batch.py --config PROJECT/pilot.json --prepare`, then run without `--prepare`. Resume completed pages. Use a new project for changed sources/settings; existing outputs are not silently regenerated. CPU is tested; do not assume GPU availability on another computer.
- Produce `chapter.md`, `chapter.json`, and `review.html` with `scripts/build_math_review.py`. Fetch offline assets with `scripts/setup_math.py --assets-only --assets PROJECT/vendor`. Preserve excerpts, raw outputs, figures, native text, coordinates and provenance.
- Review source-selected equations as well as detected equations to expose omissions. Optional `sample-source.json` entries contain book ID, source PDF page, label, y-coordinate in points and crop radius. Without that file the panel shows detections and cannot measure recall.
- Record user validation in `human-review.json` with date, scope, method and statement. Do not fabricate per-equation form entries or infer a measured accuracy percentage. Prior validation applies to its stated corpus, not future books.
- Keep books, transcripts, crops, weights and personal paths out of public commits. Publish reusable code and aggregate evidence. Read [LOCAL_MATH_PILOT.md](LOCAL_MATH_PILOT.md) for tested settings and [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md) for candidate experiments.

Keep source PDFs unchanged; never invent missing symbols. Docling is an optional comparison in a separate environment, not a default replacement. Its internal timeout did not bound formula enrichment in the pilot. Avoid hosted OCR/VLM calls unless requested. The coordinating assistant still consumes tokens; local OCR does not imply zero total assistant-token use.
