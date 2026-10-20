# Study Transcribe

Local mathematical PDF transcription for agent-assisted study: **PDF → Markdown + JSON + offline HTML**. Pix2Text handles scanned or native pages using local CPU models; no hosted OCR API is used. The coordinating assistant can still consume tokens.

## Math agent: use on another computer

Clone into your agent's skills directory (Codex: `~/.agents/skills/study-transcribe`; Claude Code: `~/.claude/skills/study-transcribe`), or clone anywhere and point the agent to `SKILL.md`:

```sh
git clone https://github.com/jleonva/study-transcribe.git
cd study-transcribe
```

With **Python 3.11**, install the isolated CPU runtime. Windows PowerShell:

```powershell
py -3.11 scripts/setup_math.py
$python = '.\.venv-math\Scripts\python.exe'
& $python scripts/new_math_project.py 'C:\books\book.pdf' --pages 16-39 --output 'C:\transcripts\chapter'
& $python scripts/setup_math.py --assets-only --assets 'C:\transcripts\chapter\vendor'
& $python scripts/local_math_batch.py --config 'C:\transcripts\chapter\pilot.json' --prepare
& $python scripts/local_math_batch.py --config 'C:\transcripts\chapter\pilot.json'
& $python scripts/build_math_review.py --config 'C:\transcripts\chapter\pilot.json'
& $python scripts/audit_math_pilot.py --config 'C:\transcripts\chapter\pilot.json' --verify-originals
```

On Linux/macOS, use `python3.11 scripts/setup_math.py`, then `.venv-math/bin/python` with your local paths. **Windows CPU is tested; other operating systems are not yet validated.** No Python executable, drive letter, user account or existing model cache is assumed on another computer. An internet connection is needed for initial installation and model/HTML-asset downloads. Documents remain local. Books, runtimes and weights are not included in GitHub.

Open `review.html` in the output folder. Each book has `chapter.md`, `chapter.json`, source excerpts and raw outputs. The reader embeds figures, math rendering and review controls. Model files default to `~/.cache/study-transcribe`; `--model-root` chooses another location. Configured model budget is 5 GB; the pilot's two engines occupied about 1.1 GB.

Ask the agent: **“Usa $study-transcribe para transcribir este capítulo con modelos locales.”** Start a new agent session after installing the skill so it can be discovered. Update the checkout with `git pull --ff-only`; update the runtime deliberately when dependency pins change. The scripts can also run without an agent.

New projects show detected equations by default. The original pilot additionally used a fixed 15-equation source sample. A `human-review.json` declaration can record global user acceptance without fabricating individual HTML answers. Preserve raw OCR separately.

## Observed pilot

79 pages completed across Shreve, Boyd and Williams; 262 display-formula blocks detected. On **2026-10-19 the user accepted all equations in the delivered pilot**, through a global conversation statement rather than individual form entries. This is qualitative user validation, not a measured accuracy percentage or a guarantee for other PDFs. See [pilot evidence and limits](LOCAL_MATH_PILOT.md) and [possible improvements](docs/IMPROVEMENTS.md).

## Legacy native-text workflow

The commands below describe the older PyMuPDF4LLM/pix2tex route. Use the math workflow above for scanned mathematical chapters.

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

The original PDF is read, never overwritten. By default, the program does not send PDF contents to a service. It uses installed Python packages and local model weights. `--allow-scanned` only creates page images; if you later give them to a cloud agent or OCR service, that is a separate action. Formula recognition only attempts image crops selected by a heuristic; vector/display equations may be missed, and diagrams may be false positives. Check equations, figures, and column order before relying on the output.

Repeated lines are preserved during document-wide cleanup because repetition without page-position evidence can also be meaningful content.

## Source and license

The `vendor/pdf_to_markdown/converter` directory contains code from [mbackschat/pdf-to-markdown-skill](https://github.com/mbackschat/pdf-to-markdown-skill), distributed under its own [MIT license](vendor/pdf_to_markdown/LICENSE). The project scripts and documentation are MIT licensed under [LICENSE](LICENSE). PyMuPDF, PyMuPDF4LLM, pix2tex, and their dependencies keep their own licenses.
