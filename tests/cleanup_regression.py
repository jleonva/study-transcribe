"""Regression checks for conservative document-wide cleanup."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cleanup_study import remove_running_banners  # noqa: E402


def main() -> None:
    source = """header fragment
<preceding_content>
Scoring Criteria:
equation label
7
<preceding_content>
Scoring Criteria:
equation label
"""
    cleaned, removed = remove_running_banners(source)
    for repeated_content in ("<preceding_content>", "Scoring Criteria:", "equation label"):
        assert cleaned.count(repeated_content) == 2, repeated_content
    assert "\n7\n" not in f"\n{cleaned}\n"
    assert removed == []
    print("Cleanup regression checks passed.")


if __name__ == "__main__":
    main()
