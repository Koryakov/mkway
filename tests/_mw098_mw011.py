"""Helper of card MW-098: the task, card and close helpers that the card-close tests of MW-011 share. The functions are copied
verbatim from tests/test_mw011_close.py (lines 24 to 120), so that test files no longer import another test module (S5).
Synthetic task roots and synthetic session ids only."""
import json
import re

from _engine import cli, gate_call, task_root
import gate_lock
import gate_records
import records
import register

ORD, HOLD, THIRD = "s-ord", "s-hold", "s-third"
OK = "tests/test_ok.py::test_ok"
ALSO = "tests/test_ok.py::test_also_ok"
BAD = "tests/test_bad.py::test_bad"


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _state(root):
    return root / "mkway" / "state"


def _row(root, card_id="CARD-001"):
    return register.find(register.read(root, _profile(root)), card_id)


def _card_file(root, card_id="CARD-001"):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    return folder / "CARD.md"


def _log(root, card_id="CARD-001"):
    return _card_file(root, card_id).read_text(encoding="utf-8").split("## 8. Log", 1)[1]


def _reason(err):
    m = re.search(r"mkway: ([a-z-]+):", err)
    return m.group(1) if m else None


def _set_paths(root, card_id, value):
    path = _card_file(root, card_id)
    path.write_text(re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {value} |", path.read_text(encoding="utf-8"),
                           flags=re.M), encoding="utf-8")


def _set_tests(root, card_id, cells):
    path = _card_file(root, card_id)
    text = path.read_text(encoding="utf-8")
    head = "| # | Item | Was | Must be | Test |\n|---|---|---|---|---|\n"
    start = text.index(head) + len(head)
    end = text.index("\n\n", start)
    rows = "".join(f"| E{i} | x | a | b | {c} |\n" for i, c in enumerate(cells, 1))
    path.write_text(text[:start] + rows.rstrip("\n") + text[end:], encoding="utf-8")


def _task(tmp_path, approver="orderer", **over):
    cards = {"verdicts": "off", **dict(over.pop("cards", {}))}  # MW-068: these tests judge the orderer rules, not the verdict check
    if approver:
        cards["approver"] = approver
    if cards:
        over["cards"] = cards
    root = task_root(tmp_path, test_roots=["tests"], **over)
    (root / "tests").mkdir()
    (root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n\n\ndef test_also_ok():\n"
                                               "    assert 1 + 1 == 2\n", encoding="utf-8")
    (root / "tests" / "test_bad.py").write_text("def test_bad():\n    assert False\n", encoding="utf-8")
    return root


def _ready(tmp_path, cells=(OK, ALSO), creator=ORD, holder=HOLD, opened=True, approver="orderer", **over):
    """CARD-001 with Acceptance rows `cells`, made by session `creator` (None: the owner's terminal), opened by the
    owner, taken by `holder`, and the owner's baseline set."""
    root = _task(tmp_path, approver, **over)
    if creator:
        code, out, err = cli(root, "card", "new", "Work", session=True)
        assert code == 0, err
        gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=creator,
                  event="PostToolUse")
    else:
        assert cli(root, "card", "new", "Work")[0] == 0
    _set_paths(root, "CARD-001", "`src/a.py`")
    _set_tests(root, "CARD-001", list(cells))
    if opened:
        assert cli(root, "card", "open", "CARD-001")[0] == 0
    if holder:
        records.append(_state(root), holder, "take", "CARD-001")
    assert cli(root, "card", "resync")[0] == 0
    return root


def _close(root, session, card="CARD-001", via="close"):
    """The gate first (the hook), then the CLI as the session's shell runs it, then the `post` group: (where it
    stopped or `ok`, reason id, text)."""
    command = f"python mkway/engine/mkway.py card {via} {card}"
    verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=session)
    if verdict.kind == "refuse":
        return "gate", verdict.reason_id, verdict.message
    code, out, err = cli(root, "card", via, card, session=True)
    if code == 0:
        gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=session,
                  event="PostToolUse")
        return "ok", None, out
    return "cli", _reason(err), err
