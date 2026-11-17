"""Card MW-075, layer shell: the real dispatcher on a synthetic task root with a real state folder. A lead's Stop warning
is shown to the user once per session for the same text, the record row is written every time, and no Stop output
carries additionalContext or a block. Files only under tmp_path."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _engine import jsonl, task_root  # noqa: E402
import dispatch  # noqa: E402
import leads  # noqa: E402
import profiles  # noqa: E402

TEXT = "blind verdict not enforced: outbox.checkers missing in profile"


def _root(tmp_path, session="lead-1", **over):
    root = task_root(tmp_path, **over)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    leads.register_lead(profiles.shared_state_dir(root, profile), session)
    return root


def _stop(root, session="lead-1"):
    payload = {"session_id": session, "hook_event_name": "Stop", "stop_hook_active": False}
    return dispatch.run("Stop", "stop", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def _rows(root):
    return [r for r in jsonl(root / "mkway" / "state" / "refusals.jsonl") if r.get("reason_id") == "verdict-not-enforced"]


def test_the_first_stop_warning_is_a_system_message_with_no_context_and_no_block(tmp_path):
    """Catches: the lead's Stop warning sent as additionalContext or a block, which re-invokes the lead."""
    root = _root(tmp_path)
    res = _stop(root)
    out = json.loads(res.stdout)
    assert (res.exit_code, list(out), TEXT in out["systemMessage"]) == (0, ["systemMessage"], True)


def test_the_second_stop_of_the_same_session_prints_nothing(tmp_path):
    """Catches: the same Stop warning printed at every stop of one session (the session is woken again each time)."""
    root = _root(tmp_path)
    _stop(root)
    res = _stop(root)
    assert (res.exit_code, res.stdout) == (0, "")


def test_the_record_row_is_written_at_every_stop_even_when_nothing_is_printed(tmp_path):
    """Catches: a reminder that writes a row at every Stop (MW112-D1 changes MW-075: the name is kept because the card row names
    it, the rule is now once per session and event), or one that writes none at all, so the first Stop must write exactly one
    row and the second Stop neither a row nor a line."""
    root = _root(tmp_path)
    first = _stop(root)
    second = _stop(root)
    assert (bool(first.stdout), second.stdout, [r["kind"] for r in _rows(root)]) == (True, "", ["warn"])


def test_another_session_is_warned_again(tmp_path):
    """Checks: the nearest allow of the second-stop silence: once is per session, a second lead sees the warning."""
    root = _root(tmp_path)
    leads.register_lead(profiles.shared_state_dir(root, json.loads(
        (root / "mkway" / "profile.json").read_text(encoding="utf-8"))), "lead-2")
    _stop(root, "lead-1")
    out = json.loads(_stop(root, "lead-2").stdout)
    assert TEXT in out["systemMessage"]
