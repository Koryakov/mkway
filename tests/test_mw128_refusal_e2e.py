"""Card MW-128 (rulings R301, R301a), through the REAL hook commands of an installed engine (one install per module, a scratch git
repository). The session `lead1` is a registered lead and the orderer of CARD-001; the session `build1` holds it. A refused engine
call (a write outside the root, judged by the real PreToolUse hook), then a Stop of `build1` through the real Stop hook: the engine
itself writes the refusal into the orderer's inbox and blocks once with the binding text. The block JSON is read from the hook's
stdout. Synthetic names only."""
import datetime
import json

import pytest

from _engine import jsonl
from _hook_driver import decision, install_project
from _mw017 import profile_of
import leads
import profiles
import register

pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw128_refusal_e2e")]

CLI = "python mkway/engine/mkway.py"
LEAD, BUILDER = "lead1", "build1"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("refusaldelivery"))
    p.owner("card", "new", "Work")
    p.owner("card", "resync", "--add-ordered-by", check=False)
    profile = profile_of(p.root)
    register.set_ordered(p.root, profile, "CARD-001", LEAD)
    register.set_status(p.root, profile, "CARD-001", "open", "`tests/`")
    for session in (LEAD, BUILDER):
        decision(p.fire("SessionStart", session))
    p.session_shell(LEAD, f"{CLI} lead register")
    p.session_shell(BUILDER, f"{CLI} card take CARD-001")
    return p


def _shared(p):
    return profiles.shared_state_dir(p.root, profile_of(p.root))


def _inbox(p):
    return leads.inbox_rows(_shared(p), LEAD)


def _refuse(p):
    """A turn that ends on a refused engine call: the prompt, then a write outside the root."""
    p.fire("UserPromptSubmit", BUILDER)
    got = decision(p.fire("PreToolUse", BUILDER, "Write", {"file_path": str(p.base / "another-checkout" / "x.txt"),
                                                            "content": "x"}))
    assert got.kind == "deny", got.text


def _stop(p, active=False):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")  # the turn starts now: earlier writes are of earlier turns
    fired = p.fire("Stop", BUILDER, stop_hook_active=active, transcript_path=p.transcript(BUILDER, user_at=now))
    return [run.json for run in fired.runs if run.json]


def test_a_turn_ending_refusal_is_delivered_to_the_orderer_and_the_stop_blocks_once_with_the_binding_text(proj):
    """Catches: a builder that stops after a refused call while its orderer sees an idle session and no refusal."""
    before = len(_inbox(proj))
    _refuse(proj)
    outputs = _stop(proj)
    row = _inbox(proj)[-1]
    assert (len(_inbox(proj)) - before, row["from"], row["kind"]) == (1, BUILDER, "notice")
    assert outputs == [{"decision": "block", "reason": f"your refusal was sent to your orderer as inbox row {row['id']}; "
                                                        f"tell your orderer: mkway inbox {row['id']}"}]


def test_the_orderers_inbox_record_holds_the_refusal_line_of_the_gate_refusal_row_exactly(proj):
    """Checks: the refusal line and the command in the record equal the gate refusal row's `message` and `target` of the calls log."""
    _refuse(proj)
    _stop(proj)
    rows = [r for r in jsonl(profiles.state_dir(proj.root, profile_of(proj.root)) / "gate_calls.jsonl")
            if r.get("verdict") == "refuse"]
    body = _inbox(proj)[-1]["body"]
    line = body.split("\nrefusal: ", 1)[1].rsplit("\ngate refusal row: ", 1)[0]
    command = body.split("\ncommand: ", 1)[1].split("\nrefusal: ", 1)[0]
    assert (line, command, body.endswith("gate refusal row: " + rows[-1]["id"]), f"session: {BUILDER}" in body) == (
        rows[-1]["message"], rows[-1]["target"], True, True)
    assert line.startswith("[mkway outside.edit write-outside-root]")
    assert "another-checkout" in command
    assert command == str(proj.base / "another-checkout" / "x.txt")  # the exact target the refused write named


def test_a_real_send_after_the_refusal_means_no_record_and_no_block(proj):
    """Catches: a session that sent its refusal on itself with a real `mkway send` told again by the hook, or blocked."""
    before = len(_inbox(proj))
    _refuse(proj)
    proj.session_shell(BUILDER, f"{CLI} send --to {LEAD} --kind question --text hello")
    assert (_stop(proj), [r["body"] for r in _inbox(proj)[before:]]) == ([], ["hello"])


def test_a_second_stop_on_the_same_refusal_with_stop_hook_active_true_allows_and_writes_nothing(proj):
    """Catches: a second block (a loop) or a second inbox record when Claude Code already continues because of the hook."""
    _refuse(proj)
    _stop(proj)
    after_first = len(_inbox(proj))
    outputs = _stop(proj, active=True)
    assert (outputs, len(_inbox(proj)) - after_first) == ([], 0)


def test_a_stop_after_a_later_allowed_engine_call_allows_and_writes_nothing(proj):
    """Checks: the nearest allow: the session went on after the refusal, so its stop is not blocked and nothing is delivered."""
    before = len(_inbox(proj))
    _refuse(proj)
    got = decision(proj.fire("PreToolUse", BUILDER, "Bash", {"command": "ls"}))
    assert got.kind == "allow", got.text
    proj.session_shell(BUILDER, f"{CLI} send --to {LEAD} --kind question --text hello")
    assert (_stop(proj), len(_inbox(proj)) - before) == ([], 1)


def test_the_block_json_is_a_single_object_with_exactly_decision_and_reason(proj):
    """Pins: the hook's stdout for the one block carries `decision` and `reason` and no other key."""
    _refuse(proj)
    (output,) = _stop(proj)
    assert sorted(output) == ["decision", "reason"]
    assert json.dumps(output).startswith('{"decision": "block", "reason": "your refusal was sent to your orderer as inbox row ')
