"""Card MW-078, rows R20 to R26: the failure edges of the inbox waiter, found by the coverage check after the green
commit (their red proof is the coverage report in the card Log: each case runs lines no earlier row ran). The waiter runs
in this process with a clock that never waits. Synthetic roots and session ids only."""
import io
import sys
from pathlib import Path

import pytest

import _wake_world as wake
from _engine import cli
import waiter


@pytest.fixture
def lead_world(tmp_path):
    root = wake.waiter_root(tmp_path)
    wake.make_lead(root, "lead-1")
    return root


def test_a_builder_that_holds_a_card_is_woken_in_process(lead_world):
    """Checks: R20, the card-holder lookup (`role_of`) arms a builder and its lead's order wakes it."""
    wake.make_builder(lead_world, "lead-1", "build-1")
    wake.put(lead_world, wake.row("lead-1", "build-1", "take the next step", "order"))
    code, err = wake.run_here(lead_world, "build-1")
    assert (code, err.startswith("m-20261112000000-aaaaaa order from lead-1: take the next step ")) == (2, True)


def test_a_pid_file_that_vanishes_ends_the_waiter_quietly(lead_world):
    """Catches: R21, a waiter that goes on, or crashes, when its pid file is gone (a cleaned state folder)."""
    clock = wake.Clock({1: lambda: wake.pid_file(lead_world, "lead-1").unlink()})
    assert wake.run_here(lead_world, "lead-1", clock) == (0, "")


def test_a_pid_file_that_cannot_be_removed_does_not_change_the_exit_code(lead_world, monkeypatch):
    """Catches: R22, a failed clean-up in `finally` turning the heartbeat (exit 2) into a crash that loses the wake."""
    def refuse(self, *args, **kwargs):
        raise PermissionError("synthetic")
    monkeypatch.setattr(Path, "unlink", refuse)
    assert wake.run_here(lead_world, "lead-1") == (2, wake.HEARTBEAT)


def test_a_failing_role_lookup_reads_as_no_role_and_exits_quietly(lead_world, monkeypatch):
    """Catches: R23, a role lookup that raises (an unreadable register) crashing the waiter or arming it by mistake."""
    def broken(*args, **kwargs):
        raise OSError("synthetic")
    wake.make_builder(lead_world, "lead-1", "build-1")
    monkeypatch.setattr(waiter.messages, "role_of", broken)
    assert (wake.run_here(lead_world, "build-1"), wake.pid_file(lead_world, "build-1").exists()) == ((0, ""), False)


def test_an_unreadable_profile_argument_gives_no_vcs_hint_and_exit_0(lead_world, tmp_path, capsys):
    """Catches: R24, a `--profile` that names a missing file crashing the hint, or the waiter arming on no profile."""
    code = waiter.main(wake.stop_payload("lead-1"), str(lead_world), str(tmp_path / "missing.json"), {})
    seen = capsys.readouterr()
    assert (code, seen.out, seen.err) == (0, "", "")


def test_the_command_line_entry_runs_the_waiter_before_dispatch(lead_world, monkeypatch):
    """Checks: R25, `mkway hook-wait` reads the Stop payload from stdin and returns the waiter's exit code and line."""
    wake.put(lead_world, wake.row())
    monkeypatch.setattr(sys, "stdin", io.StringIO(wake.stop_payload("lead-1")))
    assert cli(lead_world, "hook-wait") == (2, "", wake.LINE)


def test_a_crash_of_the_waiter_is_exit_0_at_the_command_line(lead_world, monkeypatch):
    """Catches: R26, a crash of the waiter failing the Stop (any exception must read as exit 0)."""
    def broken(*args, **kwargs):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(waiter, "main", broken)
    monkeypatch.setattr(sys, "stdin", io.StringIO(wake.stop_payload("lead-1")))
    assert cli(lead_world, "hook-wait") == (0, "", "")
