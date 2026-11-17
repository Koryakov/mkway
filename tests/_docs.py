"""Reading the documents (VERSION, CHANGELOG) without pinning a release number (MW-040).

A card's test says «the changelog names the card», never «under release X»: the release moves, the card line does not.
"""
import re

from _engine import REPO

SEMVER = re.compile(r"\d+\.\d+\.\d+")


def version():
    """The text of the `VERSION` file, stripped."""
    return (REPO / "VERSION").read_text(encoding="utf-8").strip()


def assert_version_file():
    """`VERSION` is one line holding one semantic version; the number itself is read, never pinned."""
    text = (REPO / "VERSION").read_text(encoding="utf-8")
    assert SEMVER.fullmatch(text.strip()) and len(text.splitlines()) == 1, f"VERSION is not one semver line: {text!r}"


def changelog_section(text, card_id):
    """The release section of the changelog `text` that holds the line of `card_id`; exactly one section does."""
    found = [s for s in text.split("\n## ")[1:]
             if any(line.startswith(f"- {card_id}:") for line in s.splitlines())]
    assert len(found) == 1, f"{card_id} must be in exactly one changelog release section, found {len(found)}"
    return found[0]
