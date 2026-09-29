---
name: study-transcribe
description: Transcribe chapters or page ranges from born-digital academic PDFs to Markdown using local PyMuPDF4LLM extraction and optional pix2tex formula OCR. Use for study material when a local, inspectable PDF-to-Markdown workflow is wanted.
---

# Study Transcribe

Read [README.md](README.md) for installation and commands. Use this skill only after the repository's Python environment is installed.

1. For a new PDF, list its table of contents with `python scripts/toc.py <pdf>`; select a chapter by `--chapter` or an inclusive range by `--pages`.
2. Run `python scripts/run.py <pdf> --chapter <query>` or `--pages 1-10`. The default output is `~/Documents/StudyTranscriptions`; use `-o` to choose another folder.
3. If scanned pages are detected, the script stops after splitting the mini PDF. Ask whether the user wants to find a born-digital copy, use a separate OCR tool, or run `--allow-scanned` to save page images for manual/agent transcription. That flag does not perform OCR on scanned pages.
4. Inspect the Markdown and `manifest.json`. Resolve every `pending_image_refs` item against the source PDF: transcribe equations as LaTeX and describe figures faithfully. Run `python scripts/finalize.py <chapter-dir>` only after every image reference has been replaced.

Keep source PDFs unchanged. Do not invent unreadable symbols, figure values, or missing text. Formula OCR is fallible; check critical equations against the PDF. `--prose` omits formula OCR and replaces figures with source page references.
