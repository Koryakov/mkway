"""Card MW-110 (fix of the pre-merge readers): the commit path with the launcher variable unset. A commit that names its card
passes the whole shell group; the only thing the session reads is the one `session-id-unset` warn, said once per session.
Kept in this card's own file: the helper of `test_commit_wiring.py` passes the variable of a launched session (decision
MW110-D2) and says nothing about a session that has none. Synthetic task root, a real throwaway git repository."""
from _commit_fixture import make_task, stage, work
from _mw110 import context_of, denied, hook_shell

TESTS_OFF = {"commit_tests": {"on": False}}  # the test gate runs after `commit_files` in the same group
COMMIT = "git commit -m 'CARD-001 add the thing'"


def _task(tmp_path):
    root = make_task(tmp_path, card_paths="", gates=TESTS_OFF)
    work(root, "src/a.py")
    stage(root, "src/a.py")
    return root


def test_a_commit_with_the_variable_unset_is_allowed_with_one_session_id_unset_warn(tmp_path):
    """Checks: a session with no launcher variable commits with the card id in its message: the call is not denied and the
    hook adds exactly one warn `session-id-unset`, which names the launcher line."""
    root = _task(tmp_path)
    out = hook_shell(root, COMMIT, "s1", {})
    said = context_of(out)
    assert (out.exit_code, denied(out)) == (0, None)
    assert said.count("session-id-unset") == 1
    assert "--session-id" in said


def test_the_warn_is_said_once_the_second_commit_call_of_the_session_is_silent(tmp_path):
    """Catches: the transition warn repeated on every commit of a session: the second shell call passes in silence."""
    root = _task(tmp_path)
    first = hook_shell(root, COMMIT, "s1", {})
    second = hook_shell(root, COMMIT, "s1", {})
    assert "session-id-unset" in context_of(first)
    assert (second.exit_code, second.stdout) == (0, "")


def test_a_commit_that_names_no_card_is_still_refused_by_the_commit_gate_with_the_variable_unset(tmp_path):
    """Catches: the warn of the session-id gate hiding the refusal of the commit gate: the deny carries the commit reason."""
    root = _task(tmp_path)
    reason = denied(hook_shell(root, "git commit -m 'add the thing'", "s1", {}))
    assert reason is not None
    assert reason.startswith("[mkway commit_files commit-message-card] ")
