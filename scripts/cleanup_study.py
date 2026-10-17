#!/usr/bin/env python3
"""Study-oriented text cleanup for Markdown extracted from LaTeX-built PDFs.

Fixes the extraction artifacts this corpus actually shows (calibrated on the
Polytechnique probability course PDF) without ever paraphrasing content:

1. Spacing-accent recomposition — LaTeX PDFs place a *spacing* accent glyph
   before the letter, so the text layer reads "al´eatoire", "d´enombrable",
   "ˆetre". Recomposed to proper precomposed characters (aléatoire, être).
2. Ligature expansion — ﬁ ﬂ ﬀ ﬃ ﬄ → fi fl ff ffi ffl.
3. Known math-glyph mojibake — "7→" is how \\mapsto extracts from Computer
   Modern fonts; restored to "↦" when preceded by whitespace.
4. Conservative page-number removal — repeated lines are retained because
   this assembled-text pass has no page-position metadata.
5. Blank-line collapsing.

Everything here is a pure text transform: no reordering, no rewording.
"""

from __future__ import annotations

import re
import unicodedata

# spacing accent char -> combining accent char
_SPACING_TO_COMBINING = {
    "´": "́",  # ´ acute
    "`": "̀",  # ` grave
    "ˆ": "̂",  # ˆ circumflex
    "^": "̂",  # ^ ascii circumflex (some fonts extract this)
    "¨": "̈",  # ¨ diaeresis
    "¸": "̧",  # ¸ cedilla
    "˜": "̃",  # ˜ tilde
}

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬆ": "st"}

_ACCENT_CHARS = "".join(_SPACING_TO_COMBINING)
# accent glyph immediately followed by a letter it should sit on
_ACCENT_RE = re.compile(f"([{re.escape(_ACCENT_CHARS)}])([A-Za-zıi])")


def _recompose(match: re.Match[str]) -> str:
    combining = _SPACING_TO_COMBINING[match.group(1)]
    base = match.group(2)
    if base == "ı":  # dotless i takes the accent as plain i
        base = "i"
    return unicodedata.normalize("NFC", base + combining)


def fix_glyph_artifacts(text: str) -> str:
    for lig, repl in _LIGATURES.items():
        text = text.replace(lig, repl)
    text = _ACCENT_RE.sub(_recompose, text)
    # \mapsto mojibake: "p 7→H(p)" -> "p ↦ H(p)". Require whitespace before
    # the 7 so genuine numbers like "17→" (rare, but possible) are untouched.
    text = re.sub(r"(?<=\s)7→", "↦", text)
    return text


def fix_escaped_markup(text: str) -> str:
    """pymupdf4llm emits <sup>/<sub>/<u>/<br> markup that arrives
    HTML-escaped in the Markdown ("&lt;sup&gt;1&lt;/sup&gt;") — pure noise
    for an AI reader. Unescape and convert to compact notation: sup -> ^{},
    sub -> _{}, underline dropped, <br> -> newline."""
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"</?u>", "", text)
    text = re.sub(r"<sup>(.*?)</sup>", r"^{\1}", text, flags=re.S)
    text = re.sub(r"<sub>(.*?)</sub>", r"_{\1}", text, flags=re.S)
    return text.replace("<br>", "\n")


# pix2tex misreadings observed repeatedly on this corpus's fonts, safe to
# auto-correct in probability/statistics material: the blackboard-bold
# expectation symbol 𝔼( reads as "lis(" or "li(". (\operatorname{li} the
# logarithmic integral doesn't occur in this corpus; drop this rule if a
# corpus ever genuinely uses it.)
_KNOWN_MISREADINGS = [
    (re.compile(r"\\operatorname\{lis?\}\("), r"\\mathbb{E}("),
]


def fix_known_ocr_misreadings(text: str) -> str:
    for pattern, repl in _KNOWN_MISREADINGS:
        text = pattern.sub(repl, text)
    return text


_PAGE_NUMBER_LINE = re.compile(r"^\s*(?:\d{1,4}|[ivxlcdm]{1,7})\s*$", re.IGNORECASE)
def remove_running_banners(text: str, min_repeats: int = 3) -> tuple[str, list[str]]:
    """Drop standalone page-number lines only.

    This function receives assembled text without page-position metadata.
    Repetition alone is not enough evidence to classify content as a banner.
    The legacy argument remains for API compatibility.
    """
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        if _PAGE_NUMBER_LINE.match(line):
            continue
        kept.append(line)

    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned, []


_DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.S)


def normalize_math_blocks(text: str) -> str:
    """Rewrite every display-math span into the most widely compatible
    block form — `$$` alone on its own line, LaTeX between, blank lines
    around (user feedback 2026-08-16: single-line `$$eq$$` and adjacent
    blocks don't render in his Markdown compiler):

        $$
        <latex>
        $$
    """
    def repl(m: re.Match[str]) -> str:
        latex = m.group(1).strip()
        return f"\n\n$$\n{latex}\n$$\n\n"

    # never touch YAML frontmatter — a $$ appearing there (or a stray one)
    # would pair with the body's first delimiter and corrupt the header
    frontmatter = ""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            frontmatter, text = text[: end + 5], text[end + 5:]

    text = _DISPLAY_MATH_RE.sub(repl, text)
    return frontmatter + re.sub(r"\n{3,}", "\n\n", text)


def cleanup_study_markdown(text: str) -> tuple[str, list[str]]:
    """Full study cleanup. Returns (markdown, removed_banner_examples)."""
    text = fix_glyph_artifacts(text)
    text = fix_escaped_markup(text)
    text = fix_known_ocr_misreadings(text)
    text, banners = remove_running_banners(text)
    return normalize_math_blocks(text), banners
