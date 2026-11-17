"""Card MW-110: the env-id check of the session family as table tests on Facts -> Verdict (`core_session.decide_session_env`)
and the proof of a sender (`core_session.decide_sender`, rulings R279 and R279c). No disk, no git: each row builds a facts
record and reads the verdict, under the guard that fails on any file, process or clock access. One test id is one case. The
expected values are written from the card rows, never computed by the code under test. Synthetic values only."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_session as core
from _no_io import no_io

CORE = Path(__file__).resolve().parents[2] / "engine" / "core_session.py"
NAME = "SYNTH_SESSION_VAR"  # the variable name is a fact: the decision never holds the real one
LAUNCHER = "LAUNCHER-LINE"
IN_WINDOW, AFTER_WINDOW, UNTIL = "2026-12-01", "2027-01-01", "2026-12-15"
BAD = "next week"  # a watch date that cannot be read


def facts(**kw):
    base = dict(session_id="s-1", env_name=NAME, env_id="s-1", command="python mkway/engine/mkway.py send --to x",
                day=IN_WINDOW, watch_until=UNTIL, launcher=LAUNCHER)
    base.update(kw)
    return core.SessionEnvFacts(**base)


def case(id_, *values):
    return pytest.param(*values, id=id_)


@pytest.mark.parametrize("given, kind, reason", [
    case("env-equals-hook-id-allows", facts(), "allow", None),
    case("env-differs-refuses", facts(env_id="s-2"), "refuse", "session-id-mismatch"),
    case("unset-in-window-warns", facts(env_id=None), "allow-with-line", "session-id-unset"),
    case("empty-in-window-warns", facts(env_id=""), "allow-with-line", "session-id-unset"),
    case("unset-on-the-last-day-warns", facts(env_id=None, day=UNTIL), "allow-with-line", "session-id-unset"),
    case("unset-after-window-refuses", facts(env_id=None, day=AFTER_WINDOW), "refuse", "session-id-mismatch"),
    case("empty-after-window-refuses", facts(env_id="", day=AFTER_WINDOW), "refuse", "session-id-mismatch"),
    case("unset-with-no-date-warns-whatever-the-day", facts(env_id=None, watch_until="", day=AFTER_WINDOW),
         "allow-with-line", "session-id-unset"),
    case("empty-with-no-date-warns", facts(env_id="", watch_until=""), "allow-with-line", "session-id-unset"),
    case("env-differs-with-no-date-still-refuses", facts(env_id="s-2", watch_until=""), "refuse", "session-id-mismatch"),
    case("env-equals-after-window-allows", facts(day=AFTER_WINDOW), "allow", None),
    case("hook-gives-no-id-allows", facts(session_id=None, env_id="s-9"), "allow", None),
    case("hook-gives-a-blank-id-allows", facts(session_id="  ", env_id="s-9"), "allow", None),
    case("no-command-env-equals-allows", facts(command=None), "allow", None),
])
def test_the_session_env_verdict(given, kind, reason):
    """Catches: a shell call whose environment id is not the hook's id passing, an unset variable refused inside the watch
    window or passing after it, or an equal id refused."""
    verdict = no_io_run(core.decide_session_env, given)
    assert (verdict.kind, verdict.reason) == (kind, reason)


def no_io_run(function, *args):
    with no_io():
        return function(*args)


@pytest.mark.parametrize("command", [
    case("bash-prefix", f"{NAME}=other python mkway/engine/mkway.py send --to x"),
    case("bash-export", f"export {NAME}=other; python mkway/engine/mkway.py send --to x"),
    case("bash-env-program", f"env {NAME}=other python mkway/engine/mkway.py send --to x"),
    case("powershell-env", f"$env:{NAME} = 'other'; python mkway/engine/mkway.py send --to x"),
    case("powershell-env-no-spaces", f"$env:{NAME}='other'"),
    case("cmd-set", f"set {NAME}=other && python mkway/engine/mkway.py send --to x"),
    case("python-environ", f"python -c \"import os; os.environ['{NAME}'] = 'other'\""),
    case("dot-net-set", f"[Environment]::SetEnvironmentVariable('{NAME}', 'other')"),
    case("setx", f"setx {NAME} other"),
    case("assignment-after-a-pipe", f"echo a | {NAME}=other cat"),
])
def test_an_inline_assignment_of_the_variable_is_refused(command):
    """Catches: a session that gives itself another identity by assigning the variable in the command text, in any shell form."""
    verdict = no_io_run(core.decide_session_env, facts(command=command))
    assert (verdict.kind, verdict.reason) == ("refuse", "session-id-mismatch")


@pytest.mark.parametrize("command", [
    case("bash-echo", f"echo ${NAME}"),
    case("bash-echo-braces", f"echo ${{{NAME}}}"),
    case("powershell-read", f"Write-Output $env:{NAME}"),
    case("a-test-for-equality", f"[ \"${NAME}\" == \"x\" ] && echo same"),
    case("another-variable-with-the-name-as-prefix", f"{NAME}_OTHER=1 python a.py"),
    case("another-variable-with-the-name-as-suffix", f"PRE_{NAME}=1 python a.py"),
    case("the-name-in-a-comment-word", f"git log --grep {NAME}"),
])
def test_a_command_that_only_reads_the_variable_passes(command):
    """Catches: the refusal widened to every mention of the variable, so a session that reads its own id is blocked."""
    verdict = no_io_run(core.decide_session_env, facts(command=command))
    assert verdict.kind == "allow"


@pytest.mark.parametrize("given, fragments", [
    case("mismatch-names-both-ids", facts(env_id="s-2"), ("s-2", "s-1", NAME)),
    case("mismatch-names-the-launcher-line", facts(env_id="s-2"), (LAUNCHER,)),
    case("unset-after-window-names-the-launcher-line", facts(env_id=None, day=AFTER_WINDOW), (LAUNCHER, NAME)),
    case("inline-assignment-names-the-launcher-line", facts(command=f"{NAME}=x ls"), (LAUNCHER, NAME)),
    case("unset-warn-names-the-launcher-line-and-the-date", facts(env_id=None), (LAUNCHER, UNTIL, NAME)),
])
def test_the_session_env_text_names_the_way_out(given, fragments):
    """Catches: a refusal or a warn that does not tell the session which line starts it with the variable set."""
    text = no_io_run(core.decide_session_env, given).text
    assert [f for f in fragments if f not in text] == []


@pytest.mark.parametrize("given, kind, reason", [
    case("unreadable-date-and-unset-refuses", facts(env_id=None, watch_until="", watch_bad=BAD), "refuse", "session-id-mismatch"),
    case("unreadable-date-and-empty-refuses", facts(env_id="", watch_until="", watch_bad=BAD), "refuse", "session-id-mismatch"),
    case("unreadable-date-and-equal-allows", facts(watch_until="", watch_bad=BAD), "allow", None),
    case("unreadable-date-and-differing-refuses", facts(env_id="s-2", watch_until="", watch_bad=BAD), "refuse",
         "session-id-mismatch"),
])
def test_an_unreadable_watch_date_counts_as_passed_at_the_hook(given, kind, reason):
    """Catches: R279c Q2 at the hook: an unset variable allowed with a warn for ever because the date cannot be read."""
    verdict = no_io_run(core.decide_session_env, given)
    assert (verdict.kind, verdict.reason) == (kind, reason)


def test_the_hook_text_for_an_unreadable_date_names_the_value_and_that_it_counts_as_passed():
    """Checks: the refusal says which value cannot be read, that it counts as passed, and the launcher line."""
    text = no_io_run(core.decide_session_env, facts(env_id=None, watch_until="", watch_bad=BAD)).text
    assert [f for f in (BAD, "counts as passed", LAUNCHER, "messaging.session_id_watch_until") if f not in text] == []


def test_the_decision_holds_no_literal_of_the_variable_name():
    """Catches: the variable name written as a literal inside the decision, so the name cannot be changed in one place."""
    source = CORE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    (function,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "decide_session_env"]
    literals = [n.value for n in ast.walk(function) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert [s for s in literals if "SESSION_ID" in s.upper() or "MKWAY" in s.upper()] == []


def test_the_name_is_one_module_constant_the_shell_passes_in():
    """Checks: the one place that names the variable is a module constant of the core, which the shell passes as a fact."""
    assert core.SESSION_ENV == "MKWAY_SESSION_ID"


PERMIT_SECONDS = 120


def sender(**kw):
    base = dict(env_name=NAME, env_id="s-1", own_permit="s-1", latest_permit=None, day=IN_WINDOW, watch_until=UNTIL,
                watch_bad="", launcher=LAUNCHER, permit_seconds=PERMIT_SECONDS)
    base.update(kw)
    return core.SenderFacts(**base)


@pytest.mark.parametrize("given, session, reason, warns", [
    # the variable is set: its own permit is the proof (R279c: the CLI opens only its own file)
    case("own-permit-equals-env-is-the-proof", sender(), "s-1", None, False),
    case("own-permit-is-the-proof-after-the-date", sender(day=AFTER_WINDOW), "s-1", None, False),
    case("own-permit-is-the-proof-with-an-unreadable-date", sender(watch_until="", watch_bad=BAD), "s-1", None, False),
    case("own-permit-of-another-id-is-a-mismatch", sender(own_permit="s-2"), None, "session-id-mismatch", False),
    case("own-permit-of-another-id-after-the-date", sender(own_permit="s-2", day=AFTER_WINDOW), None,
         "session-id-mismatch", False),
    case("env-alone-before-the-date-counts-with-a-warn", sender(own_permit=None), "s-1", None, True),
    case("env-alone-on-the-last-day-counts-with-a-warn", sender(own_permit=None, day=UNTIL), "s-1", None, True),
    case("env-alone-with-no-date-counts-with-a-warn", sender(own_permit=None, watch_until="", day=AFTER_WINDOW), "s-1", None,
         True),
    case("env-alone-after-the-date-is-unverified", sender(own_permit=None, day=AFTER_WINDOW), None, "session-id-unverified",
         False),
    case("env-alone-with-an-unreadable-date-is-unverified", sender(own_permit=None, watch_until="", watch_bad=BAD), None,
         "session-id-unverified", False),
    case("another-sessions-latest-permit-never-proves-a-variable", sender(own_permit=None, latest_permit="s-9"), "s-1", None,
         True),
    # no variable: before the date the most recent permit may be taken, with a warn naming the limit
    case("no-env-before-the-date-takes-the-latest-permit-with-a-warn",
         sender(env_id=None, own_permit=None, latest_permit="s-9"), "s-9", None, True),
    case("empty-env-before-the-date-takes-the-latest-permit", sender(env_id="", own_permit=None, latest_permit="s-9"), "s-9",
         None, True),
    case("no-env-and-no-permit-is-no-session", sender(env_id=None, own_permit=None), None, "message-no-session", False),
    case("no-env-after-the-date-is-unverified-even-with-a-permit",
         sender(env_id=None, own_permit=None, latest_permit="s-9", day=AFTER_WINDOW), None, "session-id-unverified", False),
    case("no-env-no-permit-after-the-date-is-unverified", sender(env_id=None, own_permit=None, day=AFTER_WINDOW), None,
         "session-id-unverified", False),
    case("no-env-with-an-unreadable-date-is-unverified",
         sender(env_id=None, own_permit=None, latest_permit="s-9", watch_until="", watch_bad=BAD), None,
         "session-id-unverified", False),
])
def test_the_sender_verdict(given, session, reason, warns):
    """Catches: the variable taken as the proof of a session by itself (R279, R279c): a session's own permit (the file named by
    its variable) is the proof; the variable alone counts only before `watch_until` (with a warn row); with no variable the
    most recent permit counts only before it; after it, or when the date cannot be read, the refusal is `session-id-unverified`."""
    verdict = no_io_run(core.decide_sender, given)
    assert (verdict.session, verdict.reason, verdict.warn) == (session, reason, warns)


@pytest.mark.parametrize("given, fragments", [
    case("mismatch-names-both-ids-and-the-launcher", sender(own_permit="s-2"), ("s-1", "s-2", NAME, LAUNCHER)),
    case("unverified-names-the-launcher-and-the-hooks", sender(own_permit=None, day=AFTER_WINDOW),
         (LAUNCHER, NAME, UNTIL, "hooks")),
    case("unverified-with-no-variable-names-the-variable-and-the-launcher",
         sender(env_id=None, own_permit=None, day=AFTER_WINDOW), (LAUNCHER, NAME, UNTIL, "hooks", "not set")),
    case("unverified-for-an-unreadable-date-names-the-value-and-that-it-counts-as-passed",
         sender(own_permit=None, watch_until="", watch_bad=BAD),
         (BAD, "counts as passed", LAUNCHER, "messaging.session_id_watch_until")),
    case("no-session-names-the-launcher-and-the-limit", sender(env_id=None, own_permit=None),
         (LAUNCHER, NAME, str(PERMIT_SECONDS), "alone, in its plain form")),
])
def test_the_sender_refusal_names_the_way_out(given, fragments):
    """Catches: a refusal of the send tool that does not name the launcher line, that of `session-id-unverified` that does not
    say the way out is a session with the hooks, or one for an unreadable date that does not name the value."""
    text = no_io_run(core.decide_sender, given).text
    assert [f for f in fragments if f not in text] == []


def test_a_warn_for_the_latest_permit_names_the_limit_and_the_date():
    """Catches: the most recent permit taken in silence: the warn says two sessions at once can take each other's permit
    and that the end date ends it."""
    verdict = no_io_run(core.decide_sender, sender(env_id=None, own_permit=None, latest_permit="s-9"))
    assert [f for f in ("most recent permit", "two sessions", UNTIL, NAME, LAUNCHER) if f not in verdict.note] == []


@pytest.mark.parametrize("day, until, bad, passed", [
    case("before", IN_WINDOW, UNTIL, "", False),
    case("last-day", UNTIL, UNTIL, "", False),
    case("after", AFTER_WINDOW, UNTIL, "", True),
    case("no-date", AFTER_WINDOW, "", "", False),
    case("unreadable-counts-as-passed", IN_WINDOW, "", BAD, True),
    case("unreadable-wins-over-a-future-date", IN_WINDOW, UNTIL, BAD, True),
])
def test_the_watch_period_is_passed_when_the_date_is_past_or_cannot_be_read(day, until, bad, passed):
    """Catches: R279c Q2: an unreadable `watch_until` read as no expiry (a trial that never ends); it counts as passed."""
    assert no_io_run(core.watch_passed, day, until, bad) is passed


def test_the_sender_decision_holds_no_literal_of_the_variable_name_or_a_date():
    """Catches: the name or an end date written as a literal inside the sender decision."""
    tree = ast.parse(CORE.read_text(encoding="utf-8"))
    (function,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "decide_sender"]
    literals = [n.value for n in ast.walk(function) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert [s for s in literals if "SESSION_ID" in s.upper() or "MKWAY" in s.upper()] == []
    assert [s for s in literals if len(s) == 10 and s[:4].isdigit() and s[4] == "-"] == []


def test_the_core_holds_no_date_of_its_own():
    """Catches: a hard-coded end date for the transition (a switch of the launcher that comes later would then refuse
    every session): the date is a fact from the profile, empty by default."""
    tree = ast.parse(CORE.read_text(encoding="utf-8"))
    dates = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and len(n.value) == 10 and n.value[:4].isdigit() and n.value[4] == "-"]
    assert dates == []
