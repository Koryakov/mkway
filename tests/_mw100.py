"""Shared helpers for the MW-100 tests (a weak or wrong verdict is answered by a re-cut). Not a test module. Synthetic
sessions, agents, files and names only; built on the MW-080 helper `_mw080`.

`lead_root` builds the MW-080 git task root (the test files committed an hour before `_mw019.T0`), commits the card file, and
makes the session `LEAD` the card's orderer. `weak_run` is one reader run (agent `agent-1`, session `reader`, started at T0
plus 60 s and ended at T0 plus 120 s) and the weak verdict row it wrote through the real `verdict add`. `change_cut` is a
commit that changes the test file (or only the card file) at a given number of seconds after T0."""
import json
from pathlib import Path

import _mw080 as w
import cardtool
import ledger
import logs
import register
import verdict_recut
import verdicts

LEAD, READER = "lead", "reader"
CARD, N1, N2, B1, FILE = w.CARD, w.N1, w.N2, w.B1, w.FILE
RECUT_KIND = "verdict-recut"


def card_rel(root) -> str:
    return cardtool.card_file(root, w.profile_of(root), CARD).relative_to(root).as_posix()


def lead_root(tmp_path, **kw):
    """The MW-080 root with the card file committed (before the reader runs) and `LEAD` as the card's orderer."""
    root = w.make_root(tmp_path, **kw)
    w.git(root, "add", "-f", "--", card_rel(root))
    w.git(root, "commit", "-q", "-m", f"{CARD} the card", when=-3000)
    assert w.cli(root, "card", "resync", "--add-ordered-by")[0] == 0  # the owner adds the `Ordered by` column
    register.set_ordered(root, w.profile_of(root), CARD, LEAD)
    return root


def weak_run(root, word="weak", node=N1, agent="agent-1", session=READER, **times):
    """One fresh reader run and its verdict row, written by the real command in process."""
    w.add_agent(root, session=session, agent_type=w.CHECKER, agent_id=agent, guard=w.CARD, **(times or w.FRESH))
    done = w.apply(root, session, [node], word, "row E4 says byte for byte, but the test replaces CRLF with LF")
    assert done.allowed, [r.text for r in done.refusals]
    return done


def change_cut(root, when=300, card_only=False):
    """A commit at `when` seconds after T0 that changes the test file, or the card file alone."""
    if card_only:
        path = cardtool.card_file(root, w.profile_of(root), CARD)
        path.write_text(path.read_text(encoding="utf-8") + "\nthe row was reworded\n", encoding="utf-8")
        w.git(root, "add", "-f", "--", card_rel(root))
    else:
        (Path(root) / FILE).write_text((Path(root) / FILE).read_text(encoding="utf-8") + "\n# the test was reworked\n",
                                       encoding="utf-8")
        w.git(root, "add", "-f", "--", FILE)
    w.git(root, "commit", "-q", "-m", f"{CARD} the cut changes", when=when)


def recut(root, monkeypatch=None, caller=LEAD, node=N1, reason="the row now says LF line ends", at=200):
    """The whole recut in process; the clock of the record is `at` seconds after T0 when `monkeypatch` is given."""
    if monkeypatch is not None:
        monkeypatch.setattr(logs, "now", lambda: w.at(at))
    return verdict_recut.apply(root, w.profile_of(root), w.state_of(root), CARD, node, reason, caller)


def facts(root, caller=LEAD, node=N1, owner=False):
    return verdict_recut.read_facts(root, w.profile_of(root), w.state_of(root), CARD, node, caller, owner)


def recut_records(root) -> list:
    return [r for r in w.proof_rows(root) if r.get("kind") == RECUT_KIND]


def add_record(root, agent=None, session=READER, **extra):
    """An add record in the proof file, as an older engine wrote it (no `nodes`), with `agent` when given."""
    row = {"kind": "verdict-written", "doc": w.VERDICT_REL, "session": session, "rows": ["k"], **extra}
    if agent:
        row["agent"] = agent
    logs.append_jsonl(w.state_of(root) / w.PROOF, row)


def cuts(root, nodes=(N1,)):
    return verdicts.cuts(w.state_of(root), CARD, list(nodes))


def ledger_text(root) -> str:
    path = ledger.path(root, w.profile_of(root))
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def card_ledger_rows(root) -> list:
    return [line for line in ledger_text(root).splitlines() if "verdict recut" in line]


def clock(monkeypatch, seconds):
    """The engine's clock, for the time of the next record, at `seconds` after T0."""
    monkeypatch.setattr(logs, "now", lambda: w.at(seconds))


def old_mtimes(root):
    """Both test files' mtime at T0, before every reader run (the close check reads the mtime)."""
    w.old(root, w.FILE)
    w.old(root, w.OTHER_FILE)


def strip_nodes(root):
    """Make every add record look as an older engine wrote it: no `nodes` key (it keeps `tests`)."""
    path = w.state_of(root) / w.PROOF
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    path.write_text("".join(json.dumps({k: v for k, v in r.items() if k != "nodes"}) + "\n" for r in rows),
                    encoding="utf-8")


def close_reason(root):
    """(reason id, text) the close-time verdict check refuses with; ("", "") when it passes."""
    profile = w.profile_of(root)
    text = cardtool.card_file(root, profile, CARD).read_text(encoding="utf-8")
    try:
        cardtool.unverdicted_tests(root, profile, CARD, text)
    except cardtool.CardError as exc:
        return exc.reason, str(exc)
    return "", ""


def dumps(value) -> str:
    return json.dumps(value, sort_keys=True)
