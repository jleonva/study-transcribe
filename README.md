# Study Transcribe

Convert a chapter or page range from an academic PDF to study-ready Markdown. Native text is extracted locally with PyMuPDF4LLM; image formulas can be recognized locally with pix2tex. The script keeps a mini PDF and a JSON manifest so you can inspect the result.

**Best for:** born-digital PDFs with selectable text. **Scanned pages:** detected and stopped by default. `--allow-scanned` saves page images for a person or an agent to transcribe; it does not run general OCR. Figures and uncertain formulas may also need review. The script cannot guarantee a complete transcription without checking `manifest.json`.

## Install on Windows

Install [Python 3.11](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win), then open PowerShell:

```powershell
git clone https://github.com/jleonva/study-transcribe.git
cd study-transcribe
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The dependency installation includes PyTorch and can take significant disk space and time. On the first formula-OCR run, pix2tex may download model weights. An internet connection is needed for installation and that first download; processing after setup is local. For text-only extraction, you can install `requirements-core.txt` instead and pass `--no-formula-ocr` or `--prose` on every run.

Formula OCR requires PyTorch to load successfully on the target computer. Check it with `.\.venv\Scripts\python.exe -c "from pix2tex.cli import LatexOCR"`. If it fails, text extraction still works with `--no-formula-ocr`; any equation images remain in `pending_image_refs` for review.

Check the installation with `.\.venv\Scripts\python.exe tests\smoke.py`. The check creates its own temporary PDF and verifies that its text appears in Markdown.

## Use

```powershell
$python = .\.venv\Scripts\python.exe
& $python scripts\toc.py "C:\path\book.pdf"
& $python scripts\run.py "C:\path\book.pdf" --chapter "Probability"
& $python scripts\run.py "C:\path\book.pdf" --pages 43-66
& $python scripts\run.py "C:\path\book.pdf" --pages 43-66 -o "C:\path\outputs"
& $python scripts\run.py "C:\path\book.pdf" --pages 43-66 --no-formula-ocr
```

The default destination is `Documents\StudyTranscriptions` under your Windows user folder. Each run creates a folder with a Markdown file, the split mini PDF, and `manifest.json`. Check `pending_image_refs` in the manifest. If it is nonempty, the Markdown still contains image placeholders. Replace these using the source PDF, then run:

```powershell
& $python scripts\finalize.py "C:\path\outputs\book\chapter"
```

For a prose book, use `--prose`; figures are replaced by page references. For multiple page ranges, run `scripts\transcribe_book.ps1 -Pdf "C:\path\book.pdf" -Ranges "1-20,21-40"` in PowerShell. The script uses this repository's `.venv`.

To use it as an agent skill, clone the repository into your agent's skills folder or point the agent to [SKILL.md](SKILL.md). The Python scripts work independently of any agent.

## Limits and privacy

The original PDF is read, never overwritten. By default, the program does not send PDF contents to a service. It uses installed Python packages and local model weights. `--allow-scanned` only creates page images; if you later give them to a cloud agent or OCR service, that is a separate action. Formula recognition and PDF layout extraction can make mistakes. Check equations, figures, and column order before relying on the output.

## Source and license

The `vendor/pdf_to_markdown/converter` directory contains code from [mbackschat/pdf-to-markdown-skill](https://github.com/mbackschat/pdf-to-markdown-skill), distributed under its own [MIT license](vendor/pdf_to_markdown/LICENSE). The project scripts and documentation are MIT licensed under [LICENSE](LICENSE). PyMuPDF, PyMuPDF4LLM, pix2tex, and their dependencies keep their own licenses.
