"""Small installation check using a synthetic PDF; no user documents needed."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="study_transcribe_smoke_") as tmp:
        base = Path(tmp)
        pdf = base / "sample.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        expected = "Chapter 1: A local transcription test with enough words to classify native text."
        page.insert_text((72, 72), expected)
        doc.set_toc([[1, "Chapter 1", 1]])
        doc.save(pdf)

        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / "run.py"), str(pdf),
             "--pages", "1-1", "--no-formula-ocr", "-o", str(base / "out")],
            capture_output=True, text=True, encoding="utf-8"
        )
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
        result = base / "out" / "sample" / "sample-p1-1"
        markdown = (result / "sample-p1-1.md").read_text(encoding="utf-8")
        manifest = json.loads((result / "manifest.json").read_text(encoding="utf-8"))
        assert expected in markdown, "Expected PDF text was missing from Markdown"
        assert manifest["page_classification"] == {"1": "native"}
        assert not manifest["pending_image_refs"]

        scan = base / "scan.pdf"
        scan_doc = pymupdf.open()
        scan_page = scan_doc.new_page()
        scan_page.draw_rect(pymupdf.Rect(72, 72, 400, 400), color=(0, 0, 0))
        scan_doc.save(scan)
        stopped = subprocess.run(
            [sys.executable, str(root / "scripts" / "run.py"), str(scan),
             "--pages", "1-1", "--no-formula-ocr", "-o", str(base / "out")],
            capture_output=True, text=True, encoding="utf-8"
        )
        assert stopped.returncode != 0 and "PAGINAS ESCANEADAS" in stopped.stderr
        assert (base / "out" / "scan" / "scan-p1-1" / "scan-p1-1.pdf").is_file()
        print("Smoke test passed: native text is preserved and scanned pages stop for review.")


if __name__ == "__main__":
    main()
