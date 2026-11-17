"""Card MW-078: the inbox waiter on a synthetic task root. Real inbox files, a real leads file, real card records.

Most cases run `waiter.run` in this process with a clock that never waits (`Clock`); the rows that the card names as a
real process (S1 to S6, R1) start the real `mkway.py hook-wait` command with a deadline of 3 s and a poll of 1 s and
wait with a bounded poll. Pure decisions are in `tests/core/test_wake_decide.py`."""
import json

import pytest

import _wake_world as wake
from _mw017 import state
import leads
import register
import waiter


@pytest.fixture
def pool():
    processes = wake.Pool()
    yield processes
    processes.kill_all()


@pytest.fixture
def lead_world(tmp_path):
    """A root with the registered leads `lead-1` and `lead-2`."""
    root = wake.waiter_root(tmp_path)
    wake.make_lead(root, "lead-1")
    wake.make_lead(root, "lead-2")
    return root


# ---- a real process (S1 to S6) ---------------------------------------------------------------------------------------

def test_a_row_appended_after_arm_wakes_the_lead_with_exit_2_and_its_line(lead_world, pool):
    """Checks: S1, a real lead waiter proven waiting by its pid file exits 2 with the appended row's line."""
    proc = pool.start(lead_world, "lead-1")
    assert wake.wait_for(lambda: wake.pid_text(lead_world, "lead-1") != "")
    wake.put(lead_world, wake.row())
    assert wake.finish(proc) == (2, "", wake.LINE)


def test_a_waiter_with_no_row_ends_in_the_heartbeat_at_its_deadline(lead_world, pool):
    """Checks: S2, nothing arrives for the 3 s deadline: exit 2 and exactly the heartbeat line on stderr."""
    proc = pool.start(lead_world, "lead-1")
    assert wake.finish(proc) == (2, "", wake.HEARTBEAT)


def test_a_second_waiter_of_a_session_makes_the_first_exit_silently(lead_world, pool):
    """Catches: S3, two live waiters for one session (each wakes it, and each Stop would add one more)."""
    first = pool.start(lead_world, "lead-1")
    assert wake.wait_for(lambda: wake.pid_text(lead_world, "lead-1") != "")
    first_pid = wake.pid_text(lead_world, "lead-1")
    second = pool.start(lead_world, "lead-1")
    assert wake.finish(first) == (0, "", "")
    assert (wake.pid_text(lead_world, "lead-1") != first_pid, wake.finish(second)) == (True, (2, "", wake.HEARTBEAT))


def test_a_pid_file_of_a_dead_process_does_not_block_a_new_waiter(lead_world, pool):
    """Checks: S4, a stale pid file (a process that is gone) is overwritten by the new waiter, which then wakes."""
    wake.pid_file(lead_world, "lead-1").parent.mkdir(parents=True, exist_ok=True)
    wake.pid_file(lead_world, "lead-1").write_text("999999999\n", encoding="utf-8")
    proc = pool.start(lead_world, "lead-1")
    assert wake.wait_for(lambda: wake.pid_text(lead_world, "lead-1") not in ("", "999999999"))
    wake.put(lead_world, wake.row())
    assert wake.finish(proc) == (2, "", wake.LINE)


def test_an_unregistered_session_exits_quietly_and_leaves_no_pid_file(lead_world, pool):
    """Catches: S5, a waiter armed for a session that is no lead and holds no card (the owner's tab, a `-p` run)."""
    proc = pool.start(lead_world, "free-1")
    assert (wake.finish(proc), wake.pid_file(lead_world, "free-1").exists()) == ((0, "", ""), False)


def test_a_builder_that_holds_a_card_arms_through_the_card_records(lead_world, pool):
    """Checks: S6, a builder that holds a card (the second lookup) arms and wakes on its lead's order."""
    wake.make_builder(lead_world, "lead-1", "build-1")
    proc = pool.start(lead_world, "build-1")
    assert wake.wait_for(lambda: wake.pid_text(lead_world, "build-1") != "")
    wake.put(lead_world, wake.row("lead-1", "build-1", "take the next step", "order"))
    expected = ("m-20261112000000-aaaaaa order from lead-1: take the next step "
                "(`mkway inbox m-20261112000000-aaaaaa`, then `mkway ack m-20261112000000-aaaaaa`)\n")
    assert wake.finish(proc) == (2, "", expected)


# ---- in this process ---------------------------------------------------------------------------------------------------

def test_the_last_holder_of_a_released_unclosed_card_arms_and_wakes(lead_world):
    """Checks: R1, a builder that released its card and waits for the lead's close or fix message is woken by it."""
    card = wake.make_builder(lead_world, "lead-1", "build-1")
    wake.release(lead_world, "build-1", card)
    wake.put(lead_world, wake.row("lead-1", "build-1", "fix the test", "answer"))
    expected = ("m-20261112000000-aaaaaa answer from lead-1: fix the test "
                "(`mkway inbox m-20261112000000-aaaaaa`, then `mkway ack m-20261112000000-aaaaaa`)\n")
    assert wake.run_here(lead_world, "build-1") == (2, expected)


def test_a_session_that_holds_only_a_closed_card_does_not_arm(lead_world):
    """Catches: R2, a builder whose card is closed still waiting for rows for ever."""
    card = wake.make_builder(lead_world, "lead-1", "build-1")
    register.set_status(lead_world, wake.profile_of(lead_world), card, "closed")
    wake.put(lead_world, wake.row("lead-1", "build-1", "fix the test", "answer"))
    assert (wake.run_here(lead_world, "build-1"), wake.pid_file(lead_world, "build-1").exists()) == ((0, ""), False)


@pytest.mark.parametrize("session", ["../x", "a/b", "a b", ".hidden"])
def test_a_session_id_that_is_no_plain_id_exits_quietly(lead_world, session):
    """Catches: R3, an unsafe session id (a path piece) building a pid file path or an inbox path."""
    assert (wake.run_here(lead_world, session), (state(lead_world) / "wake").exists()) == ((0, ""), False)


@pytest.mark.parametrize("text", ["", "not json", "[]", '{"hook_event_name": "Stop"}', '{"session_id": 5}'])
def test_a_hook_input_with_no_session_id_exits_quietly(lead_world, text):
    """Catches: R4, a hook input that is no JSON object with a session id arming a waiter or crashing."""
    assert wake.run_here(lead_world, "lead-1", stdin=text) == (0, "")


def test_a_row_wakes_a_session_at_most_once(lead_world):
    """Catches: R5, the same unacked row waking the session again at every Stop; the woken id is kept in the state."""
    wake.put(lead_world, wake.row())
    first = wake.run_here(lead_world, "lead-1")
    second = wake.run_here(lead_world, "lead-1")
    assert (first, second, wake.woken_file(lead_world, "lead-1").read_text(encoding="utf-8")) == (
        (2, wake.LINE), (2, wake.HEARTBEAT), "m-20261112000000-aaaaaa\n")


def test_a_row_that_was_unacked_before_the_arm_wakes_at_once(lead_world):
    """Checks: R6, a row already in the inbox wakes the waiter on its first look, with no poll in between."""
    wake.put(lead_world, wake.row())
    clock = wake.Clock()
    assert (wake.run_here(lead_world, "lead-1", clock), clock.ticks) == ((2, wake.LINE), 0)


def test_a_row_that_arrives_later_wakes_at_the_next_poll(lead_world):
    """Checks: R7, a row appended during the second poll wakes the waiter at the third look."""
    clock = wake.Clock({2: lambda: wake.put(lead_world, wake.row())})
    assert (wake.run_here(lead_world, "lead-1", clock), clock.ticks) == ((2, wake.LINE), 2)


def test_a_row_written_by_the_session_itself_does_not_wake_it(lead_world):
    """Catches: R8, a lead woken by a row it wrote."""
    wake.put(lead_world, wake.row("lead-1", "lead-1"))
    assert wake.run_here(lead_world, "lead-1") == (2, wake.HEARTBEAT)


def test_an_acked_row_does_not_wake(lead_world):
    """Catches: R9, a row acknowledged before the arm waking the session."""
    wake.put(lead_world, wake.row())
    leads.ack(wake.shared_of(lead_world), "lead-1", wake.FIRST)
    assert wake.run_here(lead_world, "lead-1") == (2, wake.HEARTBEAT)


def test_a_row_of_another_sessions_inbox_does_not_wake(lead_world):
    """Catches: R10, a row addressed to the other lead waking this one."""
    wake.put(lead_world, wake.row("build-1", "lead-2"))
    assert wake.run_here(lead_world, "lead-1") == (2, wake.HEARTBEAT)


def test_mode_off_exits_quietly_and_leaves_no_pid_file(tmp_path):
    """Catches: R11, `wake.mode: off` that still arms a waiter for a lead with a row waiting."""
    root = wake.waiter_root(tmp_path, mode="off")
    wake.make_lead(root, "lead-1")
    wake.put(root, wake.row())
    assert (wake.run_here(root, "lead-1"), wake.pid_file(root, "lead-1").exists()) == ((0, ""), False)


def test_an_older_waiter_exits_silently_when_the_pid_file_names_another_process(lead_world):
    """Catches: R12, an older waiter that goes on after a newer one took the session."""
    other = wake.pid_file(lead_world, "lead-1")
    clock = wake.Clock({1: lambda: other.write_text("777\n", encoding="utf-8")})
    assert (wake.run_here(lead_world, "lead-1", clock), other.read_text(encoding="utf-8")) == ((0, ""), "777\n")


def test_the_waiter_writes_its_pid_while_it_waits_and_removes_it_at_the_end(lead_world):
    """Checks: R13, the pid file holds the waiter's own pid during the wait and is gone after the heartbeat."""
    seen = []
    clock = wake.Clock({1: lambda: seen.append(wake.pid_text(lead_world, "lead-1"))})
    code = wake.run_here(lead_world, "lead-1", clock)
    assert (code, seen, wake.pid_file(lead_world, "lead-1").exists()) == ((2, wake.HEARTBEAT), ["4242"], False)


def test_the_last_sleep_stops_at_the_deadline(tmp_path):
    """Catches: R14, a poll of 2 s over a deadline of 3 s that sleeps past the deadline (the heartbeat comes at 4 s)."""
    root = wake.waiter_root(tmp_path, poll_seconds=2)
    wake.make_lead(root, "lead-1")
    clock = wake.Clock()
    assert (wake.run_here(root, "lead-1", clock), clock.t) == ((2, wake.HEARTBEAT), 3.0)


def test_the_inbox_is_read_from_the_shared_state_folder_when_it_is_set(tmp_path):
    """Checks: R15, with `state.shared_dir` set the lead, inbox and row are in the shared folder, the pid file in the root's state."""
    shared = tmp_path / "shared"
    root = wake.waiter_root(tmp_path, shared=shared)
    wake.make_lead(root, "lead-1")
    wake.put(root, wake.row())
    assert (wake.run_here(root, "lead-1"), (shared / "inbox" / "lead-1.jsonl").is_file(),
            (state(root) / "inbox").exists()) == ((2, wake.LINE), True, False)


def test_the_woken_ids_of_one_session_are_not_the_ones_of_another(lead_world):
    """Catches: R16, the woken id of one lead hiding the same row id from another lead."""
    wake.put(lead_world, wake.row(to="lead-1"))
    wake.put(lead_world, wake.row(to="lead-2"))
    first = wake.run_here(lead_world, "lead-1")
    second = wake.run_here(lead_world, "lead-2")
    assert (first, second) == ((2, wake.LINE), (2, wake.LINE))


def test_main_reads_the_root_and_the_profile_and_prints_to_stderr(lead_world, capsys):
    """Checks: R17, the command entry point finds the root and the profile itself and writes the line to stderr."""
    wake.put(lead_world, wake.row())
    code = waiter.main(wake.stop_payload("lead-1"), str(lead_world), None, {})
    seen = capsys.readouterr()
    assert (code, seen.out, seen.err) == (2, "", wake.LINE)


def test_main_exits_quietly_when_the_profile_is_invalid(lead_world, capsys):
    """Catches: R18, a profile with an unknown key arming a waiter (every gate fails closed on an invalid profile)."""
    path = lead_world / "mkway" / "profile.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["wake"] = {"mode": "sometimes"}
    path.write_text(json.dumps(data), encoding="utf-8")
    code = waiter.main(wake.stop_payload("lead-1"), str(lead_world), None, {})
    seen = capsys.readouterr()
    assert (code, seen.out, seen.err) == (0, "", "")


def test_main_exits_quietly_when_the_root_cannot_be_found(tmp_path, capsys):
    """Catches: R19, a hook run with no root (vcs none, no `--root`, no project folder) crashing instead of exiting 0."""
    profile = tmp_path / "elsewhere.json"
    profile.write_text('{"vcs": "none"}', encoding="utf-8")
    code = waiter.main(wake.stop_payload("lead-1"), None, str(profile), {})
    seen = capsys.readouterr()
    assert (code, seen.out, seen.err) == (0, "", "")
