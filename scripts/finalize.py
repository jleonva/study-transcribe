#!/usr/bin/env python3
"""Final step of the text-only output contract: once the agent has replaced
every remaining image reference in the chapter Markdown (LaTeX for equation
crops, a bracketed textual description for figures/scanned pages), this
deletes the staging images dir and clears pending_image_refs in the manifest.

Refuses to delete anything while the Markdown still references an image —
running it early loses nothing.

Usage:
  python finalize.py <chapter-output-dir>   # the dir holding <slug>.md
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out_root = Path(sys.argv[1])
    md_files = list(out_root.glob("*.md"))
    if len(md_files) != 1:
        raise SystemExit(f"Expected exactly one .md in {out_root}, found {len(md_files)}.")
    md_path = md_files[0]

    refs = IMAGE_REF_RE.findall(md_path.read_text(encoding="utf-8"))
    if refs:
        listing = "\n".join(f"  - {ref}" for _alt, ref in refs)
        raise SystemExit(
            f"{md_path.name} still references {len(refs)} image(s):\n{listing}\n"
            "Resolve them (LaTeX or textual description) before finalizing."
        )

    removed = False
    for images_dir in out_root.glob("*_images"):
        shutil.rmtree(images_dir)
        print(f"Removed {images_dir}")
        removed = True
    if not removed:
        print("No images dir present — already finalized.")

    manifest_path = out_root / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("pending_image_refs"):
            manifest["pending_image_refs"] = []
            manifest["finalized_text_only"] = True
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("Manifest updated: pending_image_refs cleared, finalized_text_only=true.")

    print(f"Text-only output confirmed: {md_path}")


if __name__ == "__main__":
    main()
