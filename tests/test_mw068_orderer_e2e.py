"""Card MW-068, layer e2e: the verdict check on the orderer's close (`cards.approver: orderer`) and the holder rule, through
the lock gate and the real CLI as a session's shell runs it. Synthetic task roots, synthetic session ids. No test file is
imported."""
import re

import pytest

from _engine import cli, gate_call, task_root
from _mw068 import prove
import gate_lock
import gate_records
import records

ORD, HOLD, READER = "s-ord", "s-hold", "s-reader"
NODE = "tests/test_ok.py::test_ok"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _card_file(root):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith("CARD-001-")]
    return folder / "CARD.md"


def _verdicts(root, *rows, proved=True):
    """The verdict file, and (R173 item 2) the proof of each reader session in it: its write record and a fresh reader
    agent. `proved=False` leaves the rows with no proof."""
    folder = root / "tests" / "verdicts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CARD-001.md").write_text(HEADER + "".join(f"| {r} |\n" for r in rows), encoding="utf-8")
    if proved:
        for by in dict.fromkeys(r.rsplit("|", 1)[1].strip().removeprefix("session:") for r in rows):
            prove(root, "CARD-001", "tests/test_ok.py", by)


def _status(root):
    return re.search(r"\| CARD-001 \| .*? \| (\S+) \|", (root / "mkway" / "cards" / "REGISTER.md").read_text(
        encoding="utf-8")).group(1)


def _reason(err):
    found = re.search(r"mkway: ([a-z-]+):", err)
    return found.group(1) if found else None


def _ready(tmp_path, **cards):
    """CARD-001 ordered by `ORD`, open, held by `HOLD`, its one row naming a passing test; the verdict check is on."""
    root = task_root(tmp_path, test_roots=["tests"], cards={"approver": "orderer", "verdicts": "required", **cards},
                     outbox={"checkers": ["critic"]})
    (root / "tests").mkdir()
    (root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    code, out, err = cli(root, "card", "new", "Work", session=True)
    assert code == 0, err
    gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=ORD, event="PostToolUse")
    path = _card_file(root)
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", "| **Paths** | `src/a.py` |", path.read_text(encoding="utf-8"), flags=re.M)
    head = "| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
    start = text.index(head) + len(head)
    end = text.index("\n\n", start)
    path.write_text(text[:start] + f"| E1 | x | a | b | {NODE} |" + text[end:], encoding="utf-8")
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    records.append(root / "mkway" / "state", HOLD, "take", "CARD-001")
    assert cli(root, "card", "resync")[0] == 0
    return root


def _orderer_close(root):
    """The gate (the hook) first, then the CLI the way the session's shell runs it: (where it stopped, reason id)."""
    command = "python mkway/engine/mkway.py card close CARD-001"
    verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=ORD)
    if verdict.kind == "refuse":
        return "gate", verdict.reason_id, verdict.message
    code, out, err = cli(root, "card", "close", "CARD-001", session=True)
    return ("ok", None, out) if code == 0 else ("cli", _reason(err), err)


def test_the_orderers_close_is_refused_while_a_named_node_has_no_verdict_row(tmp_path):
    """Catches: the orderer's close path skipping the verdict check (it is a second call site of the check)."""
    root = _ready(tmp_path)
    how, reason, text = _orderer_close(root)
    assert (how, reason) == ("cli", "verdict-missing"), text
    assert NODE in text, text
    assert _status(root) == "open"


def test_a_true_row_by_another_reader_lets_the_orderer_close(tmp_path):
    """Checks: a true row by another reader lets the orderer close, the nearest allow of the denies around it."""
    root = _ready(tmp_path)
    _verdicts(root, f"{NODE} | true | one clause, one case | session:{READER}")
    how, reason, text = _orderer_close(root)
    assert (how, reason) == ("ok", None), text
    assert _status(root) == "closed"


def test_the_orderers_close_is_refused_when_the_true_row_has_no_proof(tmp_path):
    """Catches: the orderer's close accepting a true row nobody proved, a second call site of the proof rule."""
    root = _ready(tmp_path)
    _verdicts(root, f"{NODE} | true | one clause, one case | session:{READER}", proved=False)
    how, reason, text = _orderer_close(root)
    assert (how, reason) == ("cli", "verdict-unproven"), text
    assert NODE in text, text
    assert _status(root) == "open"


def test_the_orderers_close_is_refused_when_the_reader_is_the_holder_session(tmp_path):
    """Catches: the session that built the card (its holder) giving the verdict on its own tests."""
    root = _ready(tmp_path)
    _verdicts(root, f"{NODE} | true | fine | session:{HOLD}")
    how, reason, text = _orderer_close(root)
    assert (how, reason) == ("cli", "verdict-by-holder"), text
    assert NODE in text, text
    assert HOLD in text, text
    assert _status(root) == "open"


def test_the_owners_close_is_refused_when_the_reader_is_the_holder_session(tmp_path):
    """Catches: the holder rule applied on the orderer's close only, so the owner's close lets the holder judge."""
    root = _ready(tmp_path)
    _verdicts(root, f"{NODE} | true | fine | session:{HOLD}")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert code != 0
    assert _reason(err) == "verdict-by-holder"
    assert NODE in err, err
    assert _status(root) == "open"


def test_the_holder_rule_is_skipped_on_a_card_nobody_holds(tmp_path):
    """Catches: a refusal on a card with no holder (the nearest allow of the holder deny: no one holds it)."""
    root = _ready(tmp_path)
    records.append(root / "mkway" / "state", HOLD, "release", "CARD-001")
    _verdicts(root, f"{NODE} | true | fine | session:{HOLD}")
    code, _out, err = cli(root, "card", "close", "CARD-001")
    assert code == 0, err
