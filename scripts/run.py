#!/usr/bin/env python3
"""study-transcribe — chapter-aware, fully local PDF→Markdown for AI study.

Pipeline (all offline/open-source, no Mathpix, no network):
  1. Resolve the requested chapter to a page range via the PDF's TOC
     (or take an explicit --pages range).
  2. Split those pages into a standalone mini-PDF (kept as a study artifact).
  3. Classify each page: blank (dropped), native (has text layer), scanned.
  4. Native runs → vendored PyMuPDF4LLM converter (free, local).
     Scanned pages → saved as page PNGs + a placeholder note in the
     Markdown (no generic OCR; analyze the PNG later on demand).
  5. Equation image crops → pix2tex (LaTeX-OCR) locally → $$latex$$ text.
  6. Study cleanup: recompose LaTeX-PDF accents/ligatures, fix \\mapsto
     mojibake, strip running headers/footers and page numbers.
  7. Write <slug>.md (YAML frontmatter) + <slug>_images/ + manifest.json.

Usage (run with the project venv Python; see README.md):
  python run.py <pdf> --chapter "query"   [-o outdir] [--no-formula-ocr]
  python run.py <pdf> --pages 43-66       [-o outdir] [--no-formula-ocr]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from urllib.parse import unquote

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_paths  # noqa: E402

engine_paths.require_engine()
engine_paths.add_vendor_to_path()

from converter.convert import extract_markdown  # noqa: E402
from converter.cleanup import cleanup_markdown  # noqa: E402
from converter.models import ConversionContext  # noqa: E402

from cleanup_study import cleanup_study_markdown  # noqa: E402
from formula_ocr import IMAGE_REF_RE, FormulaOcrStats, ocr_formula_images  # noqa: E402
from toc import find_chapter  # noqa: E402

DEFAULT_OUTDIR = Path.home() / "Documents" / "StudyTranscriptions"
MIN_CHARS_DEFAULT = 30


def slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w]+", "-", text.lower()).strip("-")
    return text[:max_len].rstrip("-") or "extract"


# Font names used only by OCR engines to hide a recognized-text layer behind
# a scan (Acrobat: HiddenHorzOCR/HiddenVertOCR; Tesseract: GlyphLessFont).
# Their presence means the "text layer" is OCR output of unknown quality, not
# born-digital text — treat the page as scanned so the agent transcribes the
# page image instead of inheriting OCR noise ("X rv Gamma", "IP'(A)", "<:::").
_HIDDEN_OCR_FONTS = ("hiddenhorzocr", "hiddenvertocr", "glyphlessfont")


def classify_page(page, min_chars: int) -> str:
    """'native' | 'scanned' | 'blank' for one page."""
    fonts = {str(f[3]).lower() for f in page.get_fonts()}
    if any(h in name for name in fonts for h in _HIDDEN_OCR_FONTS):
        return "scanned"
    meaningful = re.sub(r"\s+", "", page.get_text("text"))
    if len(meaningful) >= min_chars:
        return "native"
    if not page.get_images() and not page.get_drawings():
        return "blank"
    return "scanned"


def group_runs(kinds: list[str]) -> list[tuple[str, list[int]]]:
    """Maximal contiguous same-kind runs of 0-based page indices, blanks
    dropped entirely (they carry nothing worth a placeholder)."""
    runs: list[tuple[str, list[int]]] = []
    for i, kind in enumerate(kinds):
        if kind == "blank":
            continue
        if runs and runs[-1][0] == kind and runs[-1][1][-1] == i - 1:
            runs[-1][1].append(i)
        else:
            runs.append((kind, [i]))
    return runs


def fix_image_refs(md_text: str, images_dir: Path, output_dir: Path) -> str:
    """Rewrite image references by basename to the final images dir —
    separator-agnostic, avoids the vendored converter's Windows-path no-op
    (same workaround the mathpix-transcribe pipeline uses)."""
    rel_images = images_dir.relative_to(output_dir).as_posix()

    def replace(match: re.Match[str]) -> str:
        alt, ref = match.group(1), match.group(2)
        basename = Path(unquote(ref)).name
        if (images_dir / basename).exists():
            return f"![{alt}]({rel_images}/{basename})"
        return match.group(0)

    return IMAGE_REF_RE.sub(replace, md_text)


def extract_native_run(mini_pdf: Path, pages_0based: list[int], images_dir: Path, output_path: Path) -> str:
    # Short-named temp copy: pymupdf4llm derives temp paths from the source
    # filename stem, and long names can exceed Windows MAX_PATH.
    with tempfile.TemporaryDirectory(prefix="study_") as tmp:
        short_pdf = Path(tmp) / "src.pdf"
        shutil.copyfile(mini_pdf, short_pdf)
        context = ConversionContext(pdf_path=short_pdf, page_numbers=pages_0based)
        md_text, extracted_images_dir = extract_markdown(
            context=context, force_ocr=False, backend=None, langs=["en"], images_dir=images_dir
        )
        md_text = cleanup_markdown(
            md_text, context, images_dir, output_path,
            source_images_dir=extracted_images_dir,
            skip_heading_pipeline=False, skip_text_cleanup=False, skip_all_cleanup=False,
        )
    # The heading/contents cleanup can mistake a short one-page document for
    # a contents page. Never emit an empty transcription of nonempty pages.
    import pymupdf
    with pymupdf.open(mini_pdf) as source:
        raw_text = "\n\n".join(source[i].get_text("text").strip() for i in pages_0based)
    if len(md_text.strip()) < min(30, len(raw_text.strip()) // 3):
        print("  Converter returned too little text; using native PDF text as fallback")
        return raw_text
    return fix_image_refs(md_text, images_dir, output_path.parent)


def save_scanned_pages(doc, pages_0based: list[int], images_dir: Path, rel_images: str) -> str:
    import pymupdf

    parts = []
    for i in pages_0based:
        name = f"scanned_page_{i + 1:03d}.png"
        pix = doc[i].get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72))
        images_dir.mkdir(parents=True, exist_ok=True)
        pix.save(images_dir / name)
        parts.append(
            f"<!-- page {i + 1}: scanned, no text layer — page image saved "
            f"for later AI analysis -->\n![scanned page {i + 1}]({rel_images}/{name})"
        )
    return "\n\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--chapter", help="chapter query to locate via the PDF's TOC")
    ap.add_argument("--pages", help="explicit 1-based inclusive range, e.g. 43-66")
    ap.add_argument("-o", "--outdir", default=str(DEFAULT_OUTDIR))
    ap.add_argument("--min-chars", type=int, default=MIN_CHARS_DEFAULT)
    ap.add_argument("--no-formula-ocr", action="store_true",
                    help="leave equation crops as images (fast; not recommended for AI study output)")
    ap.add_argument("--force-scanned", action="store_true",
                    help="treat every page as scanned regardless of text layer — use for scanned "
                         "books whose OCR text layer is too noisy to trust even where fonts look normal")
    ap.add_argument("--allow-scanned", action="store_true",
                    help="proceed despite scanned pages (renders page PNGs for the agent to "
                         "transcribe multimodally). Without this flag, scanned pages STOP the "
                         "pipeline with an alert; the preferred fix is a born-digital copy")
    ap.add_argument("--prose", action="store_true",
                    help="cheap mode for prose books (novels, pop-science — no math): skips "
                         "formula OCR entirely, turns every figure reference into a "
                         "page-referenced stub instead of an image (zero agent image reads), "
                         "and treats near-empty art pages (cover, chapter-opener art) as "
                         "decorative markers rather than scanned pages, so no alert fires")
    args = ap.parse_args()

    if bool(args.chapter) == bool(args.pages):
        ap.error("pass exactly one of --chapter or --pages")

    import pymupdf

    t0 = time.time()
    src = Path(args.pdf)
    doc = pymupdf.open(src)

    if args.chapter:
        match = find_chapter(str(src), args.chapter)
        start, end = match.page_start, match.page_end
        title = match.title
        print(f"Chapter matched: {title!r} (TOC level {match.level}, score {match.score:.2f}) -> pages {start}-{end}")
    else:
        m = re.fullmatch(r"(\d+)-(\d+)", args.pages.strip())
        if not m:
            ap.error("--pages must look like 43-66")
        start, end = int(m.group(1)), int(m.group(2))
        title = f"pages {start}-{end}"
    if not (1 <= start <= end <= doc.page_count):
        raise SystemExit(f"Range {start}-{end} outside document (1-{doc.page_count}).")

    # keep the page suffix out of slugify's truncation so two chapters of the
    # same long-named book can never collide
    slug = slugify(title) if args.chapter else f"{slugify(src.stem, 45)}-p{start}-{end}"
    out_root = Path(args.outdir) / slugify(src.stem) / slug
    out_root.mkdir(parents=True, exist_ok=True)
    mini_pdf = out_root / f"{slug}.pdf"
    output_md = out_root / f"{slug}.md"
    images_dir = out_root / f"{slug}_images"

    # 2. split
    mini = pymupdf.open()
    mini.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
    mini.save(mini_pdf)
    print(f"Split PDF: {mini_pdf} ({mini.page_count} pages)")

    # 3. classify (indices are 0-based within the mini PDF)
    if args.force_scanned:
        kinds = ["scanned"] * mini.page_count
    else:
        kinds = [classify_page(mini[i], args.min_chars) for i in range(mini.page_count)]

    # In prose mode, a "scanned" page without a hidden-OCR font and with
    # almost no text is decorative art (cover, chapter-opener), not content:
    # emit a marker instead of alerting or rendering a PNG.
    if args.prose:
        args.no_formula_ocr = True
        for i, kind in enumerate(kinds):
            if kind == "scanned":
                fonts = {str(f[3]).lower() for f in mini[i].get_fonts()}
                has_hidden = any(h in name for name in fonts for h in _HIDDEN_OCR_FONTS)
                if not has_hidden and len(re.sub(r"\s+", "", mini[i].get_text("text"))) < args.min_chars:
                    kinds[i] = "decorative"

    runs = group_runs(kinds)
    counts = {k: kinds.count(k) for k in ("native", "scanned", "blank", "decorative")}
    print(f"Classification: {counts}  runs: {[(k, f'{p[0]+1}-{p[-1]+1}') for k, p in runs]}")

    if counts["scanned"] and not args.allow_scanned:
        scanned_ranges = ", ".join(
            f"{start + p[0]}-{start + p[-1]}" if len(p) > 1 else str(start + p[0])
            for k, p in runs if k == "scanned"
        )
        raise SystemExit(
            "\n" + "=" * 70 + "\n"
            "ALERTA: PAGINAS ESCANEADAS DETECTADAS — PROCESO DETENIDO\n"
            + "=" * 70 + "\n"
            f"  {counts['scanned']} de {mini.page_count} paginas son escaneadas "
            f"(paginas fuente: {scanned_ranges}).\n"
            "  Transcribir escaneos localmente produce baja calidad u alto costo.\n\n"
            "  Opciones:\n"
            "  1. Buscar una version digital nativa del documento.\n"
            "  2. Usar otra herramienta OCR local para esas paginas.\n"
            "  3. Re-ejecutar con --allow-scanned para guardar imagenes de\n"
            "     paginas que podras transcribir manualmente o con un agente.\n"
            + "=" * 70
        )

    # 4-5. extract per run, in order
    blocks: list[str] = []
    formula_stats = FormulaOcrStats()
    rel_images = images_dir.relative_to(out_root).as_posix()
    for kind, pages in runs:
        marker = f"<!-- source pages {start + pages[0]}-{start + pages[-1]} ({kind}) -->"
        if kind == "native":
            md = extract_native_run(mini_pdf, pages, images_dir, output_md)
            if not args.no_formula_ocr:
                md, stats = ocr_formula_images(md, images_dir)
                formula_stats += stats
                print(f"  pages {pages[0]+1}-{pages[-1]+1}: formula OCR "
                      f"{stats.recognized}/{stats.candidates} ({stats.rejected} rejected as garbage)")
        elif kind == "decorative":
            md = "\n\n".join(
                f"<!-- decorative/art page (source page {start + i}) -->"
                + (f"\n\n{t}" if (t := mini[i].get_text('text').strip()) else "")
                for i in pages
            )
        else:
            md = save_scanned_pages(mini, pages, images_dir, rel_images)
        blocks.append(f"{marker}\n\n{md.strip()}")

    assembled = "\n\n".join(blocks)

    figure_stubs = 0
    if args.prose:
        # replace every remaining figure reference with a page-referenced
        # stub — zero agent image reads, reader can consult the mini-PDF
        def _stub(m: re.Match[str]) -> str:
            nonlocal figure_stubs
            figure_stubs += 1
            page_m = re.search(r"-(\d{4})-", m.group(2))
            src_page = start + int(page_m.group(1)) - 1 if page_m else "?"
            return f"> [Figura no transcrita — ver página {src_page} del PDF original]"

        assembled = IMAGE_REF_RE.sub(_stub, assembled)
        if figure_stubs:
            print(f"  figures stubbed: {figure_stubs}")

    # 6. study cleanup
    assembled, removed_banners = cleanup_study_markdown(assembled)

    # 7. write outputs. The contract is a text-only deliverable: if nothing
    # in the Markdown references an image anymore, the staging images dir is
    # deleted outright. Any refs that DO remain (guard-rejected formulas,
    # real figures, scanned pages) are listed in the manifest as
    # pending_image_refs — the agent running the skill resolves them
    # multimodally (LaTeX for equations, a bracketed description for
    # figures) and then runs finalize.py, which deletes the images dir.
    pending_refs = sorted({
        Path(unquote(m.group(2))).name for m in IMAGE_REF_RE.finditer(assembled)
    })
    if not pending_refs and images_dir.exists():
        shutil.rmtree(images_dir)
    frontmatter = "\n".join([
        "---",
        f"source_pdf: {src}",
        f"chapter: \"{title}\"",
        f"source_pages: {start}-{end}",
        f"extracted: {_dt.date.today().isoformat()}",
        "pipeline: study-transcribe (pymupdf4llm + pix2tex, fully local)",
        "math_delimiters: \"inline: single-dollar; display: double-dollar blocks on their own lines\"",
        "---",
        "",
    ])
    output_md.write_text(frontmatter + assembled + "\n", encoding="utf-8")

    manifest = {
        "source_pdf": str(src),
        "chapter": title,
        "source_pages": [start, end],
        "page_classification": {str(start + i): k for i, k in enumerate(kinds)},
        "formula_ocr": {"candidates": formula_stats.candidates, "recognized": formula_stats.recognized,
                        "rejected_as_garbage": formula_stats.rejected,
                        "enabled": not args.no_formula_ocr},
        "removed_running_banners": removed_banners,
        "pending_image_refs": [str(images_dir / n) for n in pending_refs],
        "figure_stubs": figure_stubs,
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nDone in {manifest['elapsed_seconds']}s")
    print(f"  markdown : {output_md}")
    print(f"  manifest : {out_root / 'manifest.json'}")
    print(f"  formulas : {formula_stats.recognized}/{formula_stats.candidates} recognized as LaTeX")
    if pending_refs:
        print(f"  PENDING  : {len(pending_refs)} image ref(s) need multimodal resolution "
              f"(see manifest pending_image_refs), then run finalize.py")
    else:
        print("  images   : none left — text-only output, staging dir removed")


if __name__ == "__main__":
    main()
