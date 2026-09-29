#!/usr/bin/env python3
"""Locate the bundled, MIT-licensed PDF converter in this repository."""

from __future__ import annotations

import sys
from pathlib import Path

VENDOR_CONVERTER_ROOT = Path(__file__).resolve().parents[1] / "vendor" / "pdf_to_markdown"


def require_engine() -> None:
    """Fail fast if the bundled converter was not cloned."""
    if not (VENDOR_CONVERTER_ROOT / "converter" / "convert.py").is_file():
        raise SystemExit(
            f"Bundled converter missing: {VENDOR_CONVERTER_ROOT}. "
            "Clone the complete repository, including vendor/."
        )


def add_vendor_to_path() -> None:
    if str(VENDOR_CONVERTER_ROOT) not in sys.path:
        sys.path.insert(0, str(VENDOR_CONVERTER_ROOT))
