#!/usr/bin/env python3
"""Chapter lookup against a PDF's table of contents (PDF outline/bookmarks).

Given a free-text chapter query (accents, punctuation and word order are
forgiven), finds the best-matching TOC entry and returns its 1-based page
range: from the entry's page to the page before the next entry at the same
or shallower level.

CLI:
  python toc.py <pdf>                 # print the whole TOC with page ranges
  python toc.py <pdf> --find "query"  # print best match + range as JSON
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass


def _normalize(s: str) -> str:
    """Lowercase, strip accents/punctuation, collapse whitespace."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class ChapterMatch:
    title: str
    level: int
    page_start: int  # 1-based, inclusive
    page_end: int    # 1-based, inclusive
    score: float


def _score(query_norm: str, title_norm: str) -> float:
    """Token-overlap score: fraction of query tokens found in the title,
    with a bonus if the title is a substring of the query (the user often
    pastes 'chapter title: subsection & subsection' style strings)."""
    q_tokens = set(query_norm.split())
    t_tokens = set(title_norm.split())
    if not q_tokens or not t_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens) / len(q_tokens)
    substring_bonus = 0.5 if title_norm and title_norm in query_norm else 0.0
    return overlap + substring_bonus


def find_chapter(pdf_path: str, query: str) -> ChapterMatch:
    import pymupdf

    doc = pymupdf.open(pdf_path)
    toc = doc.get_toc()
    if not toc:
        raise SystemExit(
            "This PDF has no embedded table of contents (outline). "
            "Pass an explicit page range with --pages instead."
        )

    query_norm = _normalize(query)
    best: ChapterMatch | None = None
    for i, (level, title, page) in enumerate(toc):
        s = _score(query_norm, _normalize(title))
        if s <= 0:
            continue
        # end = page before the next entry at the same or shallower level
        end = doc.page_count
        for lvl2, _t2, p2 in toc[i + 1:]:
            if lvl2 <= level:
                end = p2 - 1
                break
        m = ChapterMatch(title=title, level=level, page_start=page, page_end=end, score=s)
        # prefer higher score; on ties prefer shallower (chapter over subsection)
        if best is None or (m.score, -m.level) > (best.score, -best.level):
            best = m

    if best is None or best.score < 0.3:
        raise SystemExit(
            f"No TOC entry matches {query!r} well enough. "
            "Run without --find to list the TOC and pick a range manually."
        )
    return best


def print_toc(pdf_path: str) -> None:
    import pymupdf

    doc = pymupdf.open(pdf_path)
    toc = doc.get_toc()
    if not toc:
        print("(no embedded TOC)")
        return
    for level, title, page in toc:
        print(f"{'  ' * (level - 1)}[L{level}] p{page}  {title}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf")
    ap.add_argument("--find", help="chapter query to locate")
    args = ap.parse_args()
    if args.find:
        m = find_chapter(args.pdf, args.find)
        print(json.dumps(m.__dict__, ensure_ascii=False, indent=2))
    else:
        print_toc(args.pdf)


if __name__ == "__main__":
    main()
