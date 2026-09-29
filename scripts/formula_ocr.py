#!/usr/bin/env python3
"""Local formula-only OCR (pix2tex / LaTeX-OCR) for the equation crops that
pymupdf4llm produces when math is rendered as font glyphs/vector paths.

Cherry-picked from the mathpix-transcribe skill's pipeline (same calibrated
heuristic and lazy model loading) — this is the piece that replaces the
Mathpix API in study-transcribe: equations become $$latex$$ text blocks,
entirely offline, at ~15s/formula on CPU.

The color heuristic decides which images are equations: every observed
equation crop in the calibration corpus was near-perfectly grayscale, while
every real chart had visible color. Real figures are left as image
references untouched (cheap in tokens — analyzable later on demand).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from PIL import Image

MAX_NONGRAY_FRACTION = 0.005
MIN_INK_FRACTION = 0.01
MAX_PIXEL_AREA = 700_000

IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def looks_like_formula(image_path: Path) -> bool:
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return False
    w, h = img.size
    if w * h == 0 or w * h > MAX_PIXEL_AREA:
        return False
    sample = img.resize((min(w, 200), min(h, 200)))
    pixels = list(sample.getdata())
    if not pixels:
        return False
    nongray = sum(1 for r, g, b in pixels if max(abs(r - g), abs(g - b), abs(r - b)) > 20) / len(pixels)
    ink = sum(1 for r, g, b in pixels if (r + g + b) / 3 < 200) / len(pixels)
    return nongray < MAX_NONGRAY_FRACTION and ink > MIN_INK_FRACTION


class FormulaOCR:
    """Lazily loaded pix2tex wrapper. Model weights download on first use."""

    def __init__(self) -> None:
        self._model = None
        self._unavailable = False

    def _ensure_model(self):
        if self._model is not None or self._unavailable:
            return self._model
        try:
            from pix2tex.cli import LatexOCR

            self._model = LatexOCR()
        except Exception as exc:  # pragma: no cover
            print(f"Warning: pix2tex unavailable ({exc}); leaving formula crops as images.")
            self._unavailable = True
        return self._model

    def recognize(self, image_path: Path, upscale: int = 1) -> str | None:
        model = self._ensure_model()
        if model is None:
            return None
        try:
            img = Image.open(image_path)
            if upscale > 1:
                img = img.resize((img.width * upscale, img.height * upscale), Image.LANCZOS)
            result = model(img)
        except Exception as exc:  # pragma: no cover
            print(f"Warning: formula OCR failed for {image_path.name}: {exc}")
            return None
        result = (result or "").strip()
        return result or None


def latex_is_sane(latex: str) -> bool:
    """Reject pix2tex garbage before it replaces an image reference. A real
    figure that slips past the color heuristic (grayscale bar charts do)
    produces telltale output: very long, brace-imbalanced, or degenerate
    repetition of sizing/product tokens. Pilot calibration: every genuine
    equation in the test chapter was <500 chars with balanced braces; the
    one misclassified figure produced ~800 chars of unbalanced noise."""
    if len(latex) > 500:
        return False
    if latex.count("{") != latex.count("}"):
        return False
    if sum(latex.count(tok) for tok in (r"\prod", r"\left", r"\right")) > 12:
        return False
    return True


@dataclass
class FormulaOcrStats:
    candidates: int = 0
    recognized: int = 0
    rejected: int = 0  # OCR output failed the sanity check; image ref kept

    def __add__(self, other: "FormulaOcrStats") -> "FormulaOcrStats":
        return FormulaOcrStats(
            self.candidates + other.candidates,
            self.recognized + other.recognized,
            self.rejected + other.rejected,
        )


_shared_ocr = FormulaOCR()


def ocr_formula_images(md_text: str, images_dir: Path) -> tuple[str, FormulaOcrStats]:
    """Replace formula-like image references with $$latex$$ blocks in place.
    Non-formula images and OCR failures stay as image references."""
    stats = FormulaOcrStats()

    def replace(match: re.Match[str]) -> str:
        ref = match.group(2)
        basename = Path(unquote(ref)).name
        image_path = images_dir / basename
        if not image_path.exists() or not looks_like_formula(image_path):
            return match.group(0)
        stats.candidates += 1
        latex = _shared_ocr.recognize(image_path)
        if latex is None or not latex_is_sane(latex):
            # CPU-first policy (user preference 2026-08-16): before giving
            # up and leaving the crop for token-costly agent resolution,
            # retry locally on a 2x-upscaled image — extra CPU seconds are
            # explicitly cheaper than Claude tokens in this workflow.
            latex = _shared_ocr.recognize(image_path, upscale=2)
        if latex is None:
            return match.group(0)
        if not latex_is_sane(latex):
            stats.rejected += 1
            return match.group(0)
        stats.recognized += 1
        return f"$${latex}$$"

    return IMAGE_REF_RE.sub(replace, md_text), stats
