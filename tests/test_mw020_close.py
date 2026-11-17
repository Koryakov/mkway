"""Card MW-020, rows E6 and E7: `card close` refuses `close-deliverable-unbuilt` while an Acceptance row names a
deliverable path with no provenance of its current hash, and `base-unknown` while a path of `deliverables.require_base`
has no base that was delivered. Synthetic git task roots only."""
import re

import pytest

import _mw098_mw011 as c11
from _commit_fixture import save
from _engine import cli
from _mw020 import OUT, deliverable, green, make_root, ready, rows, sha_of, state

TEST = "tests/test_a.py::test_one"


def _reason(err):
    m = re.search(r"mkway: ([a-z-]+):", err)
    return m.group(1) if m else None


def _rows(root, items):
    """The Acceptance rows of CARD-001: one per item text, each with a real test node."""
    path = c11._card_file(root)
    text = path.read_text(encoding="utf-8")
    head = "| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
    start = text.index(head) + len(head)
    end = text.index("\n\n", start)
    body = "".join(f"| E{i} | {item} | a | b | {TEST} |\n" for i, item in enumerate(items, 1))
    path.write_text(text[:start] + body.rstrip("\n") + text[end:], encoding="utf-8")


@pytest.fixture
def task(tmp_path):
    root = make_root(tmp_path, test_roots=["tests"])
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    return root


def _close(root):
    return cli(root, "card", "close", "CARD-001")


def _unbuilt_problems(task, rel, item):
    """The problems of one unbuilt row: none when the close is refused as the rule says and the card stays open."""
    _rows(task, ["x", item])
    code, out, err = _close(task)
    problems = []
    if code == 0 or _reason(err) != "close-deliverable-unbuilt":
        problems.append((rel, item, err))
    if rel not in err or f"mkway built {rel}" not in err:
        problems.append((rel, item, err))
    if c11._row(task)["status"] != "open":
        problems.append((rel, item, "card not open"))
    return problems


def test_a_close_is_refused_while_a_named_deliverable_is_not_built(task):
    """Catches: a card closed on a result nobody built from tested code. E6: an Acceptance row that names a path of deliverables.paths (any cell, backticks or not, either slash) keeps the card open while no provenance row holds that file's current sha256: never built, or built and changed since; the refusal is close-deliverable-unbuilt, names the file and mkway built path, and the card stays open."""
    never = deliverable(task, "never.md")
    changed = deliverable(task, "changed.md")
    ready(task, changed)
    deliverable(task, "changed.md", "Edited after it was built.\n")
    targets = [(rel, item) for rel in (never, changed)
               for item in (f"`{rel}`", rel.replace("/", "\\"), f"the file {rel} reaches the customer")]
    problems = [p for rel, item in targets for p in _unbuilt_problems(task, rel, item)]
    assert problems == [], problems


def test_a_close_goes_through_with_a_provenance_of_the_current_hash(task):
    """Catches: a gate that refuses a built result, or one that wants the head to be exactly HEAD. E6: with a provenance row that holds the file's current sha256 and whose head is HEAD, or an ancestor of HEAD (later commits were made), card close closes the card."""
    first = deliverable(task, "a.md")
    ready(task, first)
    _rows(task, ["x", f"`{first}`"])
    save(task, "src/later.py")  # HEAD moved on; the head of the provenance is an ancestor
    code, out, err = _close(task)
    assert code == 0, err
    assert c11._row(task)["status"] == "closed"


def test_a_head_that_is_not_an_ancestor_of_head_is_refused(task):
    """Catches: a provenance copied from another branch or typed by hand. E6: a provenance row whose head is not HEAD or an ancestor of HEAD (a commit that is not in this history, or an unreadable one) is no provenance."""
    rel = deliverable(task, "a.md")
    ready(task, rel)
    path = state(task) / "deliverables.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace(rows(task, "deliverables.jsonl")[0]["head"], "f" * 40),
                    encoding="utf-8")
    _rows(task, ["x", f"`{rel}`"])
    code, out, err = _close(task)
    assert code != 0
    assert _reason(err) == "close-deliverable-unbuilt", err
    assert "mkway built" in err


def test_rows_that_name_no_deliverable_are_not_judged(task):
    """Catches: a gate that judges the whole folder or reads a prefix as a folder. E6: a file outside deliverables.paths, a folder whose name only starts like the deliverable folder, the folder itself, and an unbuilt deliverable that no row names all close."""
    deliverable(task, "unbuilt.md")  # no row names it
    _rows(task, ["notes/a.md", f"{OUT}2/a.md", f"{OUT}", "a deliverable is explained in the README"])
    code, out, err = _close(task)
    assert code == 0, err


def test_a_path_that_requires_a_base_is_refused_until_a_delivered_base_is_named(task):
    """Catches: a comparison against a base nobody delivered, an internal run as the base. E7: a row that names a path of deliverables.require_base (built, with provenance) still refuses base-unknown while its check file has no base line, or names a sha8 that no delivered row holds; the text names mkway delivered and the line to write; with a delivered base it closes."""
    old = deliverable(task, "old.md", "The delivered text.\n")
    assert cli(task, "delivered", old)[0] == 0
    new = deliverable(task, "base-new.md")
    ready(task, new)
    _rows(task, ["x", f"`{new}`"])
    code, out, err = _close(task)
    assert code != 0
    assert _reason(err) == "base-unknown", err
    assert "mkway delivered" in err, err
    assert "base: <sha8>" in err, err
    assert new in err, err
    check = task / (new + ".check.md")
    check.write_text("base: deadbeef\n", encoding="utf-8")
    code, out, err = _close(task)
    assert code != 0, err
    assert _reason(err) == "base-unknown", err
    assert "deadbeef" in err, err
    check.write_text(f"base: {sha_of(task / old)[:8]}\n", encoding="utf-8")
    code, out, err = _close(task)
    assert code == 0, err
