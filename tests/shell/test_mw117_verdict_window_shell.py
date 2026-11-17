"""Card MW-117 (decisions: R272 G3, R287 Q4, MW117-D1), layer shell, on a real small git repository and real state files: the
red-proof fact the command reads, the Acceptance extract and its sha256 in the verdict record, and the close-time proof that a
verdict is stale when the test file or the Acceptance rows of its node changed after it. Synthetic sessions and names only."""
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw080 as w  # noqa: E402
import cardtool  # noqa: E402
import logs  # noqa: E402
import verdicts  # noqa: E402

LATER = 300  # seconds after T0: a commit after the record
TABLE = ("## Acceptance examples\n\n| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
         "| E1 | first | was a | must a | tests/test_a.py::test_one |\n"
         "| E2 | second | was b | must b | tests/test_a.py::test_two |\n\n## 8. Log\n")


def _card_text(root) -> str:
    return cardtool.card_file(root, w.profile_of(root), w.CARD).read_text(encoding="utf-8")


def _put_card(root, text):
    cardtool.card_file(root, w.profile_of(root), w.CARD).write_text(text, encoding="utf-8")


def _added(root, monkeypatch):
    """One real `verdict add` of the first node by session `reader`, after a fresh reader run, its record at T0 plus 125 s."""
    w.reader(root, "reader", "agent-1")
    monkeypatch.setattr(logs, "now", lambda: w.at(125))
    assert w.apply(root, "reader", [w.N1]).allowed


def _problems(root, card_text=None):
    extra = {} if card_text is None else {"card_text": card_text}
    return verdicts.proof_problems(root, w.state_of(root), [w.CHECKER], w.CARD, verdicts.rows_of(root, w.CARD), **extra)


def _commit(root, text):
    (Path(root) / w.FILE).write_text(text, encoding="utf-8")
    w.git(root, "add", "-f", "--", w.FILE)
    w.git(root, "commit", "-q", "-m", f"{w.CARD} the file changes", when=LATER)


# ---- the red-proof fact -----------------------------------------------------------------------------------------------

def test_a_red_record_whose_tree_is_a_commit_of_head_reads_red_proven(tmp_path):
    """Checks: the card's red-proof row of a commit of HEAD gives the fact red_proven."""
    root = w.make_root(tmp_path)
    assert w.read(root, "reader", [w.N1]).red_proven is True


def test_a_card_with_no_red_record_reads_not_red_proven(tmp_path):
    """Catches: a card that never had a red commit read as proven."""
    root = w.make_root(tmp_path, red=False)
    assert w.read(root, "reader", [w.N1]).red_proven is False


def test_a_red_record_of_another_card_reads_not_red_proven(tmp_path):
    """Catches: the red-proof row of another card counted for this one."""
    root = w.make_root(tmp_path, red=False)
    from _red_project import seed_record_at
    seed_record_at(root, "CARD-009", lambda *args: w.git(root, *args))
    assert w.read(root, "reader", [w.N1]).red_proven is False


def test_a_red_record_whose_tree_is_no_commit_of_head_reads_not_red_proven(tmp_path):
    """Catches: a row of a commit that was never made counted as a red commit."""
    root = w.make_root(tmp_path, red=False)
    logs.append_jsonl(w.state_of(root) / "red_proof.jsonl",
                      {"card": w.CARD, "tree": "0" * 40, "red": [w.N1], "pins": [], "checks": [], "missing": {},
                       "would_refuse": [], "mode": "trip"})
    assert w.read(root, "reader", [w.N1]).red_proven is False


def test_the_way_out_of_verdict_no_red_proof_is_the_red_commit(tmp_path):
    """Checks: the call is refused verdict-no-red-proof with no red-proof row; once the red commit of the card's tests is
    recorded the same call writes the row, the card still held (R272 G3)."""
    root = w.make_root(tmp_path, red=False, status="open")
    w.took(root, "builder")
    w.reader(root, "reader", "agent-1")
    refused = w.apply(root, "reader", [w.N1])
    assert [r.reason for r in refused.refusals] == ["verdict-no-red-proof"]
    w.seed_red(root)
    allowed = w.apply(root, "reader", [w.N1])
    assert allowed.allowed
    assert f"| {w.N1} | true |" in w.verdict_text(root)


# ---- the Acceptance extract -------------------------------------------------------------------------------------------

def test_the_extract_of_a_node_is_its_acceptance_rows_as_one_text():
    """Checks: the extract of one node is the Acceptance row that names it, cells trimmed, joined by ` | `."""
    assert verdicts.acceptance_extract(TABLE, ["tests/test_a.py::test_one"]) == "E1 | first | was a | must a | tests/test_a.py::test_one"


def test_a_changed_must_be_cell_changes_the_extract_of_its_node():
    """Catches: an Acceptance row reworded after the verdict that leaves the extract unchanged."""
    node = ["tests/test_a.py::test_one"]
    assert verdicts.acceptance_extract(TABLE.replace("must a", "must a2"), node) != verdicts.acceptance_extract(TABLE, node)


def test_a_change_in_the_row_of_another_node_leaves_the_extract_unchanged():
    """Checks: the nearest allow of the reworded row: the row of the other node changed, this node's extract is the same."""
    node = ["tests/test_a.py::test_one"]
    assert verdicts.acceptance_extract(TABLE.replace("must b", "must b2"), node) == verdicts.acceptance_extract(TABLE, node)


def test_extra_spaces_in_a_row_leave_the_extract_unchanged():
    """Checks: spacing around the cells is no change of the row's words."""
    node = ["tests/test_a.py::test_one"]
    spaced = TABLE.replace("| first |", "|   first   |")
    assert verdicts.acceptance_extract(spaced, node) == verdicts.acceptance_extract(TABLE, node)


def test_the_add_record_holds_the_sha256_of_each_nodes_extract(tmp_path, monkeypatch):
    """Checks: R287 Q4, the verdict-written record carries `acceptance_sha`, one sha256 per node of the call."""
    root = w.make_root(tmp_path)
    _added(root, monkeypatch)
    extract = verdicts.acceptance_extract(_card_text(root), [w.N1])
    assert extract
    assert w.written(root)[-1]["acceptance_sha"] == {w.N1: hashlib.sha256(extract.encode("utf-8")).hexdigest()}


# ---- stale at close ---------------------------------------------------------------------------------------------------

def test_a_test_edited_after_the_verdict_is_stale_at_close(tmp_path, monkeypatch):
    """Pin, green before the code (R272 G3, the binding of MW-101 at verdicts.py _meaning_problem): the node's own assert is
    edited and committed after the verdict, the row reads unproven at close and the text names the node."""
    root = w.make_root(tmp_path)
    _added(root, monkeypatch)
    _commit(root, w.SRC.replace("def test_one():\n    assert True", "def test_one():\n    assert 1 == 2"))
    w.old(root)
    assert w.N1 in _problems(root)


def test_an_acceptance_row_changed_after_the_verdict_is_verdict_stale_and_names_the_node(tmp_path, monkeypatch):
    """Catches: R287 Q4, the words of the node's Acceptance row changed after the reader judged them, the verdict still holds."""
    root = w.make_root(tmp_path)
    _added(root, monkeypatch)
    changed = _card_text(root).replace("| item | was | must |", "| item | was | must be different |", 1)
    text = _problems(root, changed).get(w.N1, "")
    assert text.startswith("verdict-stale") and w.N1 in text and "Acceptance" in text


def test_an_unchanged_acceptance_row_leaves_the_verdict_proven(tmp_path, monkeypatch):
    """Checks: the nearest allow of the stale row: the card text is the one the reader judged."""
    root = w.make_root(tmp_path)
    _added(root, monkeypatch)
    assert _problems(root, _card_text(root)) == {}


def test_a_change_in_the_acceptance_row_of_another_node_leaves_the_verdict_proven(tmp_path, monkeypatch):
    """Checks: one node's row reworded does not stale the verdict of another node."""
    root = w.make_root(tmp_path)
    _added(root, monkeypatch)
    text = re.sub(r"(\| E2 \| item \| was \| )must", r"\1must be other", _card_text(root))
    assert text != _card_text(root)
    assert _problems(root, text) == {}


def test_a_record_with_no_acceptance_sha_is_not_judged_by_the_extract(tmp_path, monkeypatch):
    """Checks: a record written before MW-117 holds no extract sha; what the reader judged cannot be compared, so the
    acceptance binding stays out of it (named gap; the test-file binding still judges it)."""
    root = w.make_root(tmp_path)
    _added(root, monkeypatch)
    path = w.state_of(root) / w.PROOF
    lines = [re.sub(r', "acceptance_sha": \{[^}]*\}', "", line) for line in path.read_text(encoding="utf-8").splitlines()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert "acceptance_sha" not in path.read_text(encoding="utf-8")
    changed = _card_text(root).replace("| item | was | must |", "| item | was | must be different |", 1)
    assert _problems(root, changed) == {}


def test_no_card_text_skips_the_acceptance_binding(tmp_path, monkeypatch):
    """Checks: a caller that passes no card text keeps the close proof as before (the extract is not judged)."""
    root = w.make_root(tmp_path)
    _added(root, monkeypatch)
    assert _problems(root) == {}
