"""Card MW-112 part (i), layer shell (decision MW112-D1): the real dispatcher on a synthetic task root. A reminder fires once per
session and event: the first call writes the log row and prints the line, a later call with the same event writes neither,
and a new event (a new unacked item) fires again. Files only under tmp_path; synthetic session ids."""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _engine import jsonl, task_root  # noqa: E402
import dispatch  # noqa: E402
import leads  # noqa: E402
import profiles  # noqa: E402

BURST = 33  # the size of the Stop burst the order replays


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _shared(root):
    return profiles.shared_state_dir(root, _profile(root))


def _call(root, event, group, session):
    name = {"Stop": {"hook_event_name": "Stop", "stop_hook_active": False},
            "UserPromptSubmit": {"hook_event_name": "UserPromptSubmit", "prompt": "go"}}[event]
    payload = {"session_id": session, **name}
    return dispatch.run(event, group, json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def _rows(root, reason):
    return [r for r in jsonl(root / "mkway" / "state" / "refusals.jsonl") if r.get("reason_id") == reason]


def _order(root, session, number, hours_old=3):
    """One unacked order of `session`, older than the reminder minutes."""
    moment = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_old)
    leads.write_row(_shared(root), {"id": f"m-{number}", "from": "lead-x", "to": session, "kind": "order", "reply_to": None,
                                    "ts": moment.isoformat(timespec="milliseconds"), "ack_ts": None,
                                    "body": f"order {number}"})


def _notice(root, lead, number):
    leads.append_notice(_shared(root), lead, f"notice {number}")


def _burst(root, event, group, session):
    return [_call(root, event, group, session) for _ in range(BURST)]


def test_a_stop_burst_with_one_old_order_writes_one_orders_unacked_row(tmp_path):
    """Catches: the order reminder logged at every one of 33 Stops (147 rows in the real run), not once per event."""
    root = task_root(tmp_path)
    _order(root, "b-1", 1)
    _burst(root, "Stop", "stop", "b-1")
    assert [r["kind"] for r in _rows(root, "orders-unacked")] == ["warn"]


def test_a_stop_burst_prints_the_orders_line_once(tmp_path):
    """Catches: the same Stop line printed again at every Stop of the burst, which wakes the session again."""
    root = task_root(tmp_path)
    _order(root, "b-1", 1)
    printed = [bool(r.stdout) for r in _burst(root, "Stop", "stop", "b-1")]
    assert printed == [True] + [False] * (BURST - 1)


def test_a_new_old_order_fires_the_orders_reminder_again(tmp_path):
    """Checks: the nearest allow of the once rule: a new event (a second old order) is a new line and a new row."""
    root = task_root(tmp_path)
    _order(root, "b-1", 1)
    _call(root, "Stop", "stop", "b-1")
    _order(root, "b-1", 2)
    again = _call(root, "Stop", "stop", "b-1")
    assert (len(_rows(root, "orders-unacked")), bool(again.stdout)) == (2, True)


def test_a_prompt_burst_with_one_unacked_item_writes_one_inbox_unacked_row(tmp_path):
    """Catches: the inbox reminder logged at every prompt while the item stays unacked."""
    root = task_root(tmp_path)
    _order(root, "b-1", 1)
    _burst(root, "UserPromptSubmit", "prompt", "b-1")
    assert [r["kind"] for r in _rows(root, "inbox-unacked")] == ["warn"]


def test_a_new_unacked_item_fires_the_inbox_reminder_again(tmp_path):
    """Checks: the nearest allow of the once rule for the inbox reminder: a second item is a new event."""
    root = task_root(tmp_path)
    _order(root, "b-1", 1)
    _call(root, "UserPromptSubmit", "prompt", "b-1")
    _order(root, "b-1", 2)
    _call(root, "UserPromptSubmit", "prompt", "b-1")
    assert len(_rows(root, "inbox-unacked")) == 2


def test_a_prompt_burst_with_one_unacked_notice_writes_one_lead_notices_row(tmp_path):
    """Catches: the lead's notice reminder logged at every prompt while the notice stays unacked."""
    root = task_root(tmp_path)
    leads.register_lead(_shared(root), "lead-1")
    _notice(root, "lead-1", 1)
    _burst(root, "UserPromptSubmit", "prompt", "lead-1")
    assert [r["kind"] for r in _rows(root, "lead-notices-unacked")] == ["warn"]


def test_a_new_notice_fires_the_lead_reminder_again(tmp_path):
    """Checks: the nearest allow of the once rule for the lead reminder: a second notice is a new event."""
    root = task_root(tmp_path)
    leads.register_lead(_shared(root), "lead-1")
    _notice(root, "lead-1", 1)
    _call(root, "UserPromptSubmit", "prompt", "lead-1")
    _notice(root, "lead-1", 2)
    _call(root, "UserPromptSubmit", "prompt", "lead-1")
    assert len(_rows(root, "lead-notices-unacked")) == 2


def test_a_stop_burst_of_a_lead_without_checkers_writes_one_verdict_not_enforced_row(tmp_path):
    """Catches: the lead's verdict reminder logged at every Stop while the key stays missing (MW112-D1 changes MW-075)."""
    root = task_root(tmp_path)
    leads.register_lead(_shared(root), "lead-1")
    _burst(root, "Stop", "stop", "lead-1")
    assert [r["kind"] for r in _rows(root, "verdict-not-enforced")] == ["warn"]

