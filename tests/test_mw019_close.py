"""Card MW-019, part 3: `card close` refuses `close-unchecked-outbox` while an Acceptance row names a file under
`outbox.dir` whose check is not valid. Synthetic task roots only. The orderer's close (card MW-011) goes through the
same check."""
import re

import pytest

import test_mw011_close as c11
from _engine import cli, jsonl, task_root
from _mw019 import OUT, SUFFIX, make_root, refusal_rows, valid_file, write_doc

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
    root = task_root(tmp_path, test_roots=["tests"], outbox={"dir": OUT, "checkers": ["critic"]},
                     cards={"verdicts": "off"})  # MW-068: this file judges the outbox check only
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    (root / OUT).mkdir()
    assert cli(root, "card", "new", "First")[0] == 0
    c11._set_paths(root, "CARD-001", "`src/a.py`")
    _rows(root, ["x"])
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    return root


def _refused_close(task, rel, state, item):
    """One refused close: the row names the file in the form `item`; the refusal names the file, the state and `mkway outbox`, and the card stays open."""
    _rows(task, ["x", item])
    code, out, err = cli(task, "card", "close", "CARD-001")
    assert code != 0, (rel, item, err)
    assert _reason(err) == "close-unchecked-outbox", (rel, item, err)
    assert rel in err, err
    assert state in err, err
    assert "mkway outbox" in err, err
    assert c11._row(task)["status"] == "open"


def test_a_close_is_refused_while_an_outbox_file_of_an_acceptance_row_is_unchecked(task):
    """Catches: a card closed on a result file no fresh reader has read, one whose Acceptance row names an outbox file with a missing, stale or unproven check (E12)."""
    # the row names the file in any cell, with or without backticks, with either slash; the refusal is close-unchecked-outbox, names the file, the state and
    # `mkway outbox`, leaves one refusal row, and the card stays open. The nine closes share one root, so they are a sequence (R237), not parametrized.
    bare = write_doc(task, "missing.md")
    stale = valid_file(task, "stale.md")
    write_doc(task, "stale.md", "Changed after its check.\n", when=400)
    unproven = valid_file(task, "unproven.md", agent=None, doc_when=500, check_when=900)
    _refused_close(task, bare, "missing", f"`{bare}`")
    _refused_close(task, bare, "missing", bare.replace("/", "\\"))
    _refused_close(task, bare, "missing", f"the file {bare} reaches the customer")
    _refused_close(task, stale, "stale", f"`{stale}`")
    _refused_close(task, stale, "stale", stale.replace("/", "\\"))
    _refused_close(task, stale, "stale", f"the file {stale} reaches the customer")
    _refused_close(task, unproven, "unproven", f"`{unproven}`")
    _refused_close(task, unproven, "unproven", unproven.replace("/", "\\"))
    _refused_close(task, unproven, "unproven", f"the file {unproven} reaches the customer")
    assert [r["reason_id"] for r in refusal_rows(task)] == ["close-unchecked-outbox"] * 9
    code, out, err = cli(task, "card", "set", "CARD-001", "closed")  # the other way to close is judged too
    assert code != 0
    assert _reason(err) == "close-unchecked-outbox"
    assert c11._row(task)["status"] == "open"


def test_a_close_goes_through_with_a_valid_check(task):
    """Checks: with a valid check for every outbox file the rows name, card close closes the card (E12)."""
    # guards a gate that refuses a card whose files were checked
    first = valid_file(task, "a.md")
    second = valid_file(task, "b.md")
    _rows(task, [f"`{first}`", f"{second}"])
    code, out, err = cli(task, "card", "close", "CARD-001")
    assert code == 0, err
    assert c11._row(task)["status"] == "closed"


def test_a_row_naming_a_file_outside_the_outbox_is_not_judged(task):
    """Checks: rows that name no file under the outbox dir are not judged, so a file in another folder, a folder that only starts with the outbox name, the outbox folder itself and an unchecked file no row names all close (E12)."""
    # guards a gate that reads a prefix as a folder or judges the whole outbox
    write_doc(task, "unchecked.md")  # not named by any row
    _rows(task, ["notes/a.md", f"{OUT}2/a.md", f"{OUT}", "the outbox is explained in the README"])
    code, out, err = cli(task, "card", "close", "CARD-001")
    assert code == 0, err
    assert c11._row(task)["status"] == "closed"


def test_the_orderers_close_is_judged_too(tmp_path):
    """Catches: a second door that lets an orderer close what the owner could not: the orderer is refused the same way, then closes once the check is valid (E12)."""
    # with cards.approver orderer the session that ordered the card is refused after the hook has let it through; the refusal comes from the command
    root = c11._ready(tmp_path, outbox={"dir": OUT, "checkers": ["critic"]})
    (root / OUT).mkdir(exist_ok=True)
    rel = write_doc(root, "a.md")
    path = c11._card_file(root)
    path.write_text(path.read_text(encoding="utf-8").replace("| E1 | x |", f"| E1 | {rel} |"), encoding="utf-8")
    how, reason, text = c11._close(root, c11.ORD)
    assert (how, reason) == ("cli", "close-unchecked-outbox"), text
    assert rel in text
    assert "mkway outbox" in text
    assert c11._row(root)["status"] == "open"
    valid_file(root, "a.md")
    how, reason, text = c11._close(root, c11.ORD)
    assert (how, reason) == ("ok", None), text
    assert c11._row(root)["status"] == "closed"
