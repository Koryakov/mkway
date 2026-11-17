"""Card MW-132 (rulings R337, R337a, R338), through the REAL hook commands of an installed engine (one install per module, a scratch git
repository). The session `lead1` is a registered lead and the orderer of CARD-001; the session `build1` holds it. A turn with a
prompt, a tool call and no `mkway send`, then a Stop of `build1` through the real Stop hook: the engine itself writes the last message
into the orderer's inbox and blocks once with the binding text; the orderer reads the row with `mkway inbox <id>`; the next stop
passes. The block JSON is read from the hook's stdout. Synthetic names only."""
import datetime
import json

import pytest

from _hook_driver import decision, install_project
from _mw017 import profile_of
import leads
import profiles
import register

pytestmark = [pytest.mark.engine_repo, pytest.mark.xdist_group("test_mw132_handoff_e2e")]

CLI = "python mkway/engine/mkway.py"
LEAD, BUILDER = "lead1", "build1"
LAST = "Should I change those four nodes, then fix the three query files?"
BODY = f"{BUILDER} ended its turn holding CARD-001 without a message to you\nlast message: {LAST}"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("handoffnotice"))
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


def _turn(p):
    """A turn of the builder that ends with text and no send: first the ping stop that ends the earlier test's blocked turn (flag true:
    R342, a blocked stop cannot end a turn), then the prompt and one allowed engine call."""
    _stop(p, active=True)
    p.fire("UserPromptSubmit", BUILDER)
    got = decision(p.fire("PreToolUse", BUILDER, "Bash", {"command": "ls"}))
    assert got.kind == "allow", got.text


def _stop(p, active=False, last=LAST):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    fired = p.fire("Stop", BUILDER, stop_hook_active=active, last_assistant_message=last,
                   transcript_path=p.transcript(BUILDER, user_at=now))
    return [run.json for run in fired.runs if run.json]


def test_a_turn_ending_with_no_send_writes_the_last_message_to_the_orderer_and_blocks_once_with_the_binding_text(proj):
    """Catches: a builder that ends a turn with a question in its own chat while its orderer sees an idle session (the live case)."""
    before = len(_inbox(proj))
    _turn(proj)
    outputs = _stop(proj)
    row = _inbox(proj)[-1]
    assert (len(_inbox(proj)) - before, row["from"], row["kind"], row["body"]) == (1, BUILDER, "notice", BODY)
    assert outputs == [{"decision": "block", "reason": (
        f"you ended your turn holding CARD-001 without a message to your orderer; your last message was sent to your orderer "
        f"as inbox row {row['id']}; tell your orderer: mkway inbox {row['id']}")}]


def test_the_orderer_reads_the_notice_with_the_printed_ping_and_the_next_stop_passes_with_no_second_row(proj):
    """Checks: R2-21: the orderer's inbox holds the notice; `mkway inbox <id>` shows it; the next stop (flag true) passes and writes no second row."""
    before = len(_inbox(proj))
    _turn(proj)
    _stop(proj)
    row = _inbox(proj)[-1]
    shown = proj.session_shell(LEAD, f"{CLI} inbox {row['id']}")
    after_ping = _stop(proj, active=True)
    assert (LAST in shown.stdout, after_ping, len(_inbox(proj)) - before) == (True, [], 1)


def test_a_real_send_to_the_orderer_in_the_turn_means_no_notice_and_no_block(proj):
    """Checks: (h) a session with a handoff pays nothing, through the real hooks."""
    before = len(_inbox(proj))
    _turn(proj)
    proj.session_shell(BUILDER, f"{CLI} send --to {LEAD} --kind question --text hello")
    assert (_stop(proj), [r["body"] for r in _inbox(proj)[before:]]) == ([], ["hello"])


def test_a_second_stop_right_after_the_noticed_one_writes_nothing(proj):
    """Checks: the stop that follows the noticed one in the same turn (flag true) passes and writes no second row."""
    _turn(proj)
    _stop(proj)
    before = len(_inbox(proj))
    assert (_stop(proj, active=True), len(_inbox(proj)) - before) == ([], 0)


def test_the_block_json_is_a_single_object_with_exactly_decision_and_reason(proj):
    """Pins: the hook's stdout for the one block carries `decision` and `reason` and no other key."""
    _turn(proj)
    (output,) = _stop(proj)
    assert sorted(output) == ["decision", "reason"]


def test_a_new_turn_after_a_noticed_one_is_noticed_again(proj):
    """Checks: R2-3: a turn that ended with a notice does not silence the next turn."""
    _turn(proj)
    _stop(proj)
    before = len(_inbox(proj))
    _turn(proj)
    assert (len(_stop(proj)), len(_inbox(proj)) - before) == (1, 1)


def test_a_turn_ending_with_a_sendmessage_call_to_the_orderer_is_still_noticed_through_the_installed_hooks(proj):
    """Pins: R2-9: a SendMessage call goes through the installed PreToolUse hooks and leaves no send record with a recipient: the notice and the block fire."""
    before = len(_inbox(proj))
    _turn(proj)
    proj.fire("PreToolUse", BUILDER, "SendMessage", {"to": LEAD, "message": "my question"})
    assert (len(_stop(proj)), len(_inbox(proj)) - before) == (1, 1)


def test_a_subagent_stop_through_the_installed_hooks_writes_no_notice_and_no_block(proj):
    """Checks: R2-10: a SubagentStop event of the builder's session, fired through the installed hooks, writes nothing and blocks nothing."""
    before = len(_inbox(proj))
    _turn(proj)
    fired = proj.fire("SubagentStop", BUILDER, stop_hook_active=False, last_assistant_message=LAST, agent_id="agent-1",
                      agent_type="helper")
    assert ([run.json for run in fired.runs if run.json and run.json.get("decision")], len(_inbox(proj)) - before) == ([], 0)
