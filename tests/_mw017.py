"""Shared helpers for the MW-017 tests (the lead role). Not a test module. Synthetic roots and session ids only."""
import json
import re
from pathlib import Path

from _engine import cli, gate_call, task_root
import gate_lock
import gate_records
import register

NOTICE_FIELDS = ["id", "from", "to", "kind", "reply_to", "ts", "ack_ts", "body"]  # changed by MW-018: `reply_to`


def lead_root(tmp_path, **over):
    """A synthetic task root whose register has the `Ordered by` column (`cards.approver: orderer`)."""
    over.setdefault("cards", {"approver": "orderer"})
    return task_root(tmp_path, **over)


def profile_of(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def state(root):
    return root / "mkway" / "state"


def leads_file(root) -> Path:
    return state(root) / "leads.json"


def leads_data(root) -> dict:
    return json.loads(leads_file(root).read_text(encoding="utf-8"))


def row_of(root, card_id):
    return register.find(register.read(root, profile_of(root)), card_id)


def reason_of(err):
    m = re.search(r"mkway: ([a-z-]+):", err)
    return m.group(1) if m else None


def session_run(root, session, *args):
    """A session's mkway command as the hooks run it: the lock gate (it leaves the one-use permit that names the
    session) first, then the CLI in a session's shell, then the `post` record step. Returns (code, out, err); a gate
    refusal is (None, "", "<reason id>: <message>")."""
    command = "python mkway/engine/mkway.py " + " ".join(args)
    verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=session)
    if verdict.kind == "refuse":
        return None, "", f"{verdict.reason_id}: {verdict.message}"
    code, out, err = cli(root, *args, session=True)
    if code == 0:
        gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=session,
                  event="PostToolUse")
    return code, out, err


def new_card(root, session, title="Work"):
    """A session's `card new`, with its `Ordered by` cell written by the post step; returns the card id."""
    code, out, err = session_run(root, session, "card", "new", title)
    assert code == 0, err
    return re.search(r"(CARD-\d{3})", out).group(1)


def register_lead(root, session):
    code, _out, err = session_run(root, session, "lead", "register")
    assert code == 0, err


def inbox(root, lead):
    path = state(root) / "inbox" / f"{lead}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
