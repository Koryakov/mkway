"""Card MW-063: `core_lock.decide(facts) -> Verdict` as table tests. No disk, no git, no clock: each case builds a `Facts`
record and reads the verdict; every call runs under a guard that fails on any file, process or clock access. One test
id is one case; each refusal reason has a deny case and the nearest allow case. Expected values come from the rules of
the lock gate (the card rows), never from the code. Synthetic values only."""
import builtins
import contextlib
import io
import os
import pathlib
import subprocess
import time

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_lock as core
from _no_io import no_io

REGISTER = "mkway/cards/REGISTER.md"
COMMIT = "git commit -m 'CARD-001 x' -- "


def T(name, *entries, built_in=False, **kw):
    return core.Target(name, entries, built_in, **kw)


BUILT_IN = (T("engine", "mkway/engine/", built_in=True), T("lock", "mkway/mkway.lock", built_in=True),
            T("profile", "mkway/profile.json", built_in=True),
            T("hooks", ".claude/settings.json", ".claude/settings.local.json", built_in=True),
            T("locks", "mkway/locks/", built_in=True), T("gitignore", "mkway/.gitignore", built_in=True),
            T("gitattributes", "mkway/.gitattributes", built_in=True), T("register", REGISTER, built_in=True),
            T("state", "mkway/state/", built_in=True))
DOCS, SEEDS = T("docs", "docs/**/*.md"), T("seeds", "*.seed")
RULES = T("rules", "rules/**", "conf/x.json")
HOLD = T("hold", "**", open_by_default=True)


class Reads(dict):
    """The facts a case gives. A disk fact not named in `hits` is "no file" (None): the folders of these cases are empty."""

    def __init__(self, base, hits=None):
        super().__init__(base)
        self.hits = hits or {}

    def __contains__(self, key):
        return key[0] == "disk" or dict.__contains__(self, key)

    def __getitem__(self, key):
        return self.hits.get(key) if key[0] == "disk" else dict.__getitem__(self, key)


QUIET = {("engine_call",): None, ("calls",): (), ("parse_ok",): True, ("names_commit",): False, ("carrier",): None,
         ("form",): None, ("env",): None, ("cdpath",): False, ("writes",): core.WriteFacts(), ("expanded_text",): "",
         ("commits",): (), ("unknown_shape",): ""}


def edit(rel, *, targets=BUILT_IN, hits=None):
    return core.Facts(tool_name="Edit", targets=targets, session_id="s1", edit_rels=(rel,), reads=Reads({}, hits))


def shell(command="", *, targets=BUILT_IN, git=False, hits=None, tool="Bash", reads=None, **kw):
    kw.setdefault("session_id", "s1")
    return core.Facts(tool_name=tool, command=command, targets=targets, vcs_git=git, register_rel=REGISTER,
                      owner_terminal="OWNER-TERMINAL", owner_fix="OWNER-FIX", stale_hours=2,
                      reads=Reads({**QUIET, **(reads or {})}, hits), **kw)


def w(*texts, reason=None):
    """Writes the reader found: each path is read as itself."""
    return core.WriteFacts(reason, tuple((t, t) for t in texts))


def call(*args, held=None, mine=None, stale=None, lead=False, register=None, **kw):
    reads = {("calls",): (args,), ("holders",): held or {}, ("mine",): mine, ("stale",): stale or {}, ("lead",): lead,
             ("register",): register or core.RegisterFacts()}
    return shell(reads=reads, **kw)


def rows(**by_id):
    return core.RegisterFacts(rows={k: v if isinstance(v, core.Row) else core.Row(v) for k, v in by_id.items()})


def run(f):
    with no_io():
        return core.decide(f)


def outcome(f):
    """The reason of a refusal, else the kind (`allow`, `log`)."""
    v = run(f)
    return v.reason if v.kind == core.REFUSE else v.kind


def text_of(f):
    return run(f).text


@pytest.fixture(autouse=True, scope="module")
def _warm_imports():
    """The first call imports lazily; that stays out of the guard."""
    core.decide(edit("src/a.py"))


# ==== the edit tool ============================================================================================================

BUILT_IN_PATHS = [
    pytest.param("mkway/engine/dispatch.py", "lock-closed-edit", id="engine-copy"),
    pytest.param("mkway/mkway.lock", "lock-closed-edit", id="mkway-lock"),
    pytest.param("mkway/profile.json", "lock-closed-edit", id="profile"),
    pytest.param(".claude/settings.json", "lock-closed-edit", id="hook-entries-committed"),
    pytest.param(".claude/settings.local.json", "lock-closed-edit", id="hook-entries-local"),
    pytest.param("mkway/.gitignore", "lock-closed-edit", id="bundle-gitignore"),
    pytest.param("mkway/.gitattributes", "lock-closed-edit", id="bundle-gitattributes"),
    pytest.param(REGISTER, "lock-closed-edit", id="register"),
    pytest.param("mkway/state/records.jsonl", "lock-closed-edit", id="state-records"),
    pytest.param("mkway/state/register.sha", "lock-closed-edit", id="state-seal"),
    pytest.param("mkway/locks/x.json", "lock-file-by-session", id="lock-file"),
]


@pytest.mark.parametrize("rel, reason", BUILT_IN_PATHS)
def test_an_edit_inside_a_closed_built_in_target_is_refused(rel, reason):
    """Catches: a built-in target missing from the list, so a session can edit the engine, the profile, the hooks, a lock file, the register or the state."""
    assert outcome(edit(rel)) == reason


@pytest.mark.parametrize("rel", [
    pytest.param("src/a.py", id="source-file"),
    pytest.param("mkway/cards/CARD-001-first/CARD.md", id="card-file-beside-the-register"),
    pytest.param("mkway/locksmith.txt", id="name-that-only-starts-like-the-locks-folder"),
    pytest.param("mkway/profile.json.bak", id="name-that-only-starts-like-the-profile"),
])
def test_an_edit_outside_every_target_is_allowed(rel):
    """Checks: a source file, a card file and names that only start like a built-in folder are not targets."""
    assert outcome(edit(rel)) == "allow"


@pytest.mark.parametrize("closed, want", [
    pytest.param(True, "lock-closed-edit", id="lock-closed"),
    pytest.param(False, "allow", id="lock-open"),
])
def test_a_profile_target_refuses_only_while_its_lock_is_closed(closed, want):
    """Catches: a profile target that stays closed after the owner opened it, or one that is open without the owner."""
    assert outcome(edit("rules/a.md", targets=BUILT_IN + (T("rules", "rules/**", closed=closed),))) == want


@pytest.mark.parametrize("rel", [
    pytest.param("other/rules/a.md", id="same-name-below-another-folder"),
    pytest.param("x.json", id="base-name-of-a-listed-file"),
])
def test_a_profile_target_matches_its_path_and_never_a_base_name(rel):
    """Checks: a profile target matches its own path, never a file with the same base name."""
    assert outcome(edit(rel, targets=BUILT_IN + (RULES,))) == "allow"


@pytest.mark.parametrize("rel, part", [
    pytest.param("rules/a.md", "rules/a.md", id="quotes-the-path"),
    pytest.param("rules/a.md", "'rules'", id="quotes-the-lock-name"),
])
def test_a_refusal_quotes_the_path_and_the_lock_name(rel, part):
    """Catches: a refusal that does not say which lock or which path."""
    assert part in text_of(edit(rel, targets=BUILT_IN + (RULES,)))


@pytest.mark.parametrize("rel, targets, part", [
    pytest.param(REGISTER, BUILT_IN, "only the engine's own commands write it", id="never-open-target"),
    pytest.param("mkway/engine/x.py", BUILT_IN, "lock open engine", id="built-in-the-owner-may-open"),
    pytest.param("rules/a.md", BUILT_IN + (RULES,), "ask the owner to open it", id="profile-target"),
    pytest.param("src/a.py", BUILT_IN + (HOLD,), "hold by the owner", id="owner-hold"),
])
def test_the_refusal_names_the_way_out_for_the_kind_of_target(rel, targets, part):
    """Catches: one way out named for every target, so the owner is told to open what is never open."""
    assert part in text_of(edit(rel, targets=targets))


# ==== a write that holds a closed target ========================================================================================

HOLDERS = BUILT_IN + (DOCS, SEEDS)


@pytest.mark.parametrize("path, hits", [
    pytest.param("mkway", None, id="folder-of-the-engine-and-the-register"),
    pytest.param(".", None, id="the-root"),
    pytest.param("mkway/cards", None, id="folder-of-the-register"),
    pytest.param("docs", None, id="literal-folder-of-a-glob-target"),
    pytest.param("data", {("disk", "data", "*.seed"): "data/x.seed"}, id="folder-holding-a-file-a-glob-matches"),
])
def test_a_write_to_a_folder_that_holds_a_closed_target_is_refused(path, hits):
    """Catches: `rm -rf mkway` or `mv mkway old` passing because the folder itself is inside no target."""
    assert outcome(shell(reads={("writes",): w(path)}, targets=HOLDERS, hits=hits)) == "lock-closed-shell"


@pytest.mark.parametrize("path", [
    pytest.param("mkway/cards/CARD-001-first", id="card-folder-below-the-register-folder"),
    pytest.param("other", id="folder-with-no-matching-file"),
    pytest.param("src", id="source-folder"),
])
def test_a_write_to_a_folder_that_holds_no_closed_target_is_allowed(path):
    """Checks: a folder with no closed target under it, or holding no matching file, is allowed."""
    assert outcome(shell(reads={("writes",): w(path)}, targets=HOLDERS)) == "allow"


@pytest.mark.parametrize("path, part", [
    pytest.param("docs", "'docs'", id="names-the-lock-of-the-glob-folder"),
    pytest.param("data", "data/x.seed", id="names-the-file-that-shows-it"),
])
def test_the_refusal_for_a_holding_folder_says_what_it_holds(path, part):
    """Catches: a refusal for a holding folder that does not name the lock or the file that holds it."""
    hits = {("disk", "data", "*.seed"): "data/x.seed"}
    assert part in text_of(shell(reads={("writes",): w(path)}, targets=HOLDERS, hits=hits))


# ==== writes by a shell command =================================================================================================

@pytest.mark.parametrize("path, reason", [
    pytest.param("mkway/profile.json", "lock-closed-shell", id="redirect-to-the-profile"),
    pytest.param(REGISTER, "lock-closed-shell", id="sed-in-place-on-the-register"),
    pytest.param("mkway/state/records.jsonl", "lock-closed-shell", id="forged-search-record"),
    pytest.param("mkway/locks/engine.json", "lock-file-by-session", id="forged-lock-file"),
    pytest.param("mkway/mkway.lock", "lock-closed-shell", id="lock-text-of-the-engine"),
])
def test_a_shell_write_inside_a_closed_target_is_refused(path, reason):
    """Catches: a forged lock file, record or register written through a shell redirect, `tee`, `cp` or `sed -i`."""
    assert outcome(shell(reads={("writes",): w(path)})) == reason


@pytest.mark.parametrize("path", [
    pytest.param("src/a.txt", id="source-file"),
    pytest.param("build/out.txt", id="build-output"),
])
def test_a_shell_write_outside_every_target_is_allowed(path):
    """Checks: a shell write to a source or build file is allowed."""
    assert outcome(shell(reads={("writes",): w(path)})) == "allow"


@pytest.mark.parametrize("glob", [
    pytest.param("mkway/engine/*", id="star-below-a-folder-target"),
    pytest.param("mkway/engine/gate_lock.p?", id="question-mark-below-a-folder-target"),
    pytest.param("mkway/locks/*", id="star-below-the-locks-folder"),
    pytest.param("mkway/*", id="star-over-the-bundle-folder"),
    pytest.param("mkway/engin?/gate_lock.py", id="wildcard-in-a-folder-segment"),
    pytest.param("mkway/engine*", id="star-right-after-the-folder-name"),
    pytest.param("mkway/l?cks/engine.json", id="wildcard-in-the-locks-segment"),
])
def test_a_glob_that_reaches_a_closed_target_is_refused(glob):
    """Catches: `rm -rf mkway/engine/*` or `cp x mkway/engin?/y` passing because the glob names no target literally."""
    assert outcome(shell(reads={("writes",): w(glob)})) == "lock-closed-shell"


@pytest.mark.parametrize("glob", [
    pytest.param("build/*", id="star-below-a-plain-folder"),
    pytest.param("src/*.py", id="star-below-the-source-folder"),
])
def test_a_glob_that_reaches_no_closed_target_is_allowed(glob):
    """Checks: a glob that reaches no closed target is allowed."""
    assert outcome(shell(reads={("writes",): w(glob)})) == "allow"


COMMAND_NAMING_THE_PROFILE = "python -c \"import subprocess; subprocess.run([1, 'mkway/profile.json'])\""


@pytest.mark.parametrize("command, reason, expanded, part", [
    pytest.param(COMMAND_NAMING_THE_PROFILE, "capable", "", "capable", id="capable-writer-naming-the-profile"),
    pytest.param("echo \"x > mkway/mkway.lock", "unparsed", "", "unparsed", id="unparsed-text-naming-the-lock"),
    pytest.param("X=mkway; rm -rf $X/engine", "capable", "X=mkway\nrm -rf mkway/engine", "engine",
                 id="variable-then-the-engine-folder"),
    pytest.param("cat list.txt | xargs -I{} cp {} .claude/settings.local.json", "capable", "", "settings.local.json",
                 id="xargs-copy-onto-the-local-hook-entries"),
])
def test_a_command_that_writes_anywhere_and_names_a_closed_target_is_refused(command, reason, expanded, part):
    """Catches: a command whose write targets cannot be read passing although its text names a closed target."""
    f = shell(command, reads={("writes",): w(reason=reason), ("expanded_text",): expanded})
    assert (outcome(f), part in text_of(f)) == ("lock-closed-shell", True)


@pytest.mark.parametrize("command, reason", [
    pytest.param("python -c \"import subprocess; subprocess.run([1])\"", "capable", id="capable-writer-naming-nothing"),
    pytest.param("echo \"unterminated", "unparsed", id="unparsed-text-naming-nothing"),
    pytest.param("git switch main", "capable", id="branch-switch-that-rewrites-the-tree"),
])
def test_a_command_that_writes_anywhere_and_names_no_target_is_only_logged(command, reason):
    """Catches: about one false block in ten real commands, every unreadable write refused."""
    assert outcome(shell(command, reads={("writes",): w(reason=reason)})) == "log"


def test_a_variable_path_is_a_write_anywhere_and_is_logged():
    """Checks: a write to a variable path is logged, not refused, when it names no closed target."""
    assert outcome(shell("echo x > \"$OUT\"", reads={("writes",): core.WriteFacts(None, (("\"$OUT\"", None),))})) == "log"


def test_a_command_that_writes_nothing_unreadable_is_allowed():
    """Checks: a command that writes nothing unreadable is allowed."""
    assert outcome(shell("python -m pytest -q")) == "allow"


# ==== the text of a command names a closed target ===============================================================================

NAMES = BUILT_IN + (DOCS, T("tool", "scripts/run"))


@pytest.mark.parametrize("text", [
    pytest.param("python -c \"print('see the docs')\"", id="word-docs-in-a-sentence"),
    pytest.param("cat mkway/statement.md", id="name-that-continues-after-the-literal"),
    pytest.param("echo run it", id="undotted-file-base-name-after-a-space"),
    pytest.param("python -c \"print('the run')\"", id="undotted-file-base-name-after-a-quote"),
    pytest.param("python -c 'import subprocess; print(\"locks\")'", id="folder-name-as-a-quoted-word"),
    pytest.param("python - <<'EOF'\nimport subprocess\n# R09: only the State differs\nEOF", id="folder-name-in-a-heredoc-sentence"),
    pytest.param("python - <<'EOF'\nimport subprocess\nengine = 1\nEOF", id="folder-name-as-a-variable-in-a-heredoc"),
    pytest.param("cat .gitignore | xargs -n1 echo", id="the-roots-own-gitignore-is-not-the-bundles"),
])
def test_a_plain_word_names_no_closed_target(text):
    """Catches: a word-keyed refusal, the defect that refused 909 of 943 real commands."""
    assert core.named_target(NAMES, text) is None


@pytest.mark.parametrize("text", [
    pytest.param("X=a; rm -rf $X/docs", id="folder-after-a-variable"),
    pytest.param("cp x \"$D/scripts/run\"", id="file-after-a-slash-in-quotes"),
    pytest.param("rm -rf ./docs", id="folder-after-dot-slash"),
    pytest.param("echo x > mkway/state/a", id="state-folder-with-its-path"),
    pytest.param("X=mkway; rm -rf $X/engine", id="engine-folder-after-a-variable"),
    pytest.param("echo x > mkway/mkway.lock", id="the-lock-text-file"),
    pytest.param("cp a 'mkway/profile.json'", id="the-profile-in-quotes"),
    pytest.param("echo x > ${X}/state/x", id="state-folder-after-a-braced-variable"),
    pytest.param("cat list.txt | xargs -I{} cp {} mkway/.gitignore", id="the-bundle-gitignore-by-its-full-path"),
    pytest.param("cd $D && echo x > mkway.lock", id="a-dotted-file-name-after-a-space"),
])
def test_a_path_in_a_path_position_names_a_closed_target(text):
    """Catches: a closed target named in a path position that the name check misses."""
    assert core.named_target(NAMES, text) is not None


# ==== the engine's own commands: owner-only =====================================================================================

OWNER_ONLY = [
    pytest.param(("lock", "open", "rules"), id="lock-open"),
    pytest.param(("lock", "close", "rules"), id="lock-close"),
    pytest.param(("gate", "off", "lock"), id="gate-off"),
    pytest.param(("gate", "on", "lock"), id="gate-on"),
    pytest.param(("gate", "watch", "lock"), id="gate-watch"),
    pytest.param(("install", "--from", "x"), id="install"),
    pytest.param(("upgrade",), id="upgrade"),
    pytest.param(("hold",), id="hold"),
    pytest.param(("go",), id="go"),
    pytest.param(("delivered",), id="delivered"),
    pytest.param(("card", "open", "CARD-001"), id="card-open"),
    pytest.param(("card", "close", "CARD-001"), id="card-close"),
    pytest.param(("card", "resync"), id="card-resync"),
    pytest.param(("card", "set", "CARD-001", "closed"), id="card-set-closed"),
    pytest.param(("card", "set", "CARD-001", "open"), id="card-set-open-by-a-non-holder"),
    pytest.param(("card", "release", "CARD-001", "--force"), id="release-force-last"),
    pytest.param(("card", "release", "--force", "CARD-001"), id="release-force-first"),
    pytest.param(("card", "release", "CARD-001", "--force=yes"), id="release-force-with-a-value"),
    pytest.param(("lead", "add", "s9"), id="lead-add"),
    pytest.param(("lead", "remove", "s9"), id="lead-remove"),
    pytest.param(("give", "CARD-001", "s9"), id="give-by-a-session-that-is-no-lead"),
]


@pytest.mark.parametrize("args", OWNER_ONLY)
def test_a_session_call_of_an_owner_command_is_refused(args):
    """Catches: an owner move (lock, gate, install, card open or close, force release) a session can run."""
    assert outcome(call(*args)) == "owner-only-command"


@pytest.mark.parametrize("args", [
    pytest.param(("lock", "list"), id="lock-list"),
    pytest.param(("card", "list"), id="card-list"),
    pytest.param(("card", "new", "Second"), id="card-new-by-a-non-lead"),
    pytest.param(("card", "set", "CARD-001", "proposed"), id="card-set-a-status-outside-the-owner-moves"),
    pytest.param(("search", "words"), id="search"),
    pytest.param(("check",), id="check"),
    pytest.param(("card", "release", "CARD-002"), id="release-of-a-card-no-one-holds"),
])
def test_a_session_call_of_another_engine_command_is_allowed(args):
    """Checks: the other engine commands a session may run are allowed."""
    assert outcome(call(*args)) == "allow"


def test_a_command_with_no_engine_call_is_allowed():
    """Checks: a command with no engine call is allowed."""
    assert outcome(shell("git status")) == "allow"


def test_an_owner_refusal_names_the_owners_terminal():
    """Catches: an owner refusal that does not name the owner's terminal."""
    assert "terminal" in text_of(call("card", "close", "CARD-001"))


@pytest.mark.parametrize("args", [
    pytest.param(("card", "open", "CARD-001"), id="card-open"),
    pytest.param(("card", "close", "CARD-001"), id="card-close"),
    pytest.param(("card", "set", "CARD-001", "open"), id="card-set-open"),
])
def test_light_mode_lets_a_session_make_the_card_moves(args):
    """Catches: a light mode (`cards.owner_moves: []`) that still refuses the card moves."""
    assert outcome(call(*args, owner_moves=())) == "allow"


@pytest.mark.parametrize("args", [
    pytest.param(("lock", "open", "rules"), id="lock-open"),
    pytest.param(("gate", "off", "lock"), id="gate-off"),
    pytest.param(("install", "--from", "x"), id="install"),
    pytest.param(("card", "resync"), id="card-resync"),
    pytest.param(("card", "release", "CARD-001", "--force"), id="force-release"),
])
def test_light_mode_keeps_the_owners_other_commands(args):
    """Catches: a light mode that opens every owner command."""
    assert outcome(call(*args, owner_moves=())) == "owner-only-command"


@pytest.mark.parametrize("holder, status, session, want", [
    pytest.param("s1", "waiting", "s1", "allow", id="holder-from-waiting"),
    pytest.param("s1", "waiting-owner", "s1", "owner-only-command", id="holder-from-waiting-owner"),
    pytest.param("s2", "waiting", "s1", "owner-only-command", id="another-session-holds"),
    pytest.param(None, "waiting", "s1", "owner-only-command", id="no-holder-record"),
    pytest.param("s1", "open", "s1", "owner-only-command", id="holder-but-already-open"),
])
def test_the_holder_reopens_its_pause_only_from_waiting(holder, status, session, want):
    """Catches: a reopen open to any session, or one that passes from `waiting-owner`."""
    held = {"CARD-001": holder} if holder else {}
    f = call("card", "set", "CARD-001", "open", held=held, register=rows(**{"CARD-001": status}), session_id=session)
    assert outcome(f) == want


# ==== pausing, taking and releasing a card ======================================================================================

@pytest.mark.parametrize("held, want", [
    pytest.param({"CARD-001": "s1"}, "allow", id="the-session-holds-it"),
    pytest.param({"CARD-001": "s2"}, "card-not-yours", id="another-session-holds-it"),
    pytest.param({}, "card-not-yours", id="no-one-holds-it"),
])
def test_a_session_pauses_only_the_card_it_holds(held, want):
    """Catches: a session that pauses another session's card, which its holder then cannot reopen."""
    assert outcome(call("card", "set", "CARD-001", "waiting", held=held)) == want


MINE = rows(**{"CARD-001": "open"})
CLOSED_MINE = rows(**{"CARD-001": "closed"})


@pytest.mark.parametrize("mine, register, want", [
    pytest.param("CARD-001", MINE, "session-has-card", id="holds-an-open-card"),
    pytest.param("CARD-001", rows(**{"CARD-001": "waiting"}), "session-has-card", id="holds-a-waiting-card"),
    pytest.param("CARD-001", CLOSED_MINE, "allow", id="holds-a-closed-card"),
    pytest.param(None, MINE, "allow", id="holds-no-card"),
])
def test_a_session_takes_a_second_card_only_when_its_first_is_closed(mine, register, want):
    """Catches: a second card per session."""
    assert outcome(call("card", "take", "CARD-002", mine=mine, register=register)) == want


def test_a_session_may_take_the_card_it_already_holds():
    """Checks: a session may take the card it already holds."""
    assert outcome(call("card", "take", "CARD-001", mine="CARD-001", register=MINE)) == "allow"


@pytest.mark.parametrize("held, stale, want", [
    pytest.param({"CARD-002": "s2"}, {}, "card-not-yours", id="another-session-holds-it"),
    pytest.param({"CARD-002": "s2"}, {"CARD-002": "s2"}, "allow", id="its-holder-is-stale"),
    pytest.param({}, {}, "allow", id="no-one-holds-it"),
    pytest.param({"CARD-002": "s1"}, {}, "allow", id="the-session-holds-it-itself"),
])
def test_a_card_another_session_holds_cannot_be_taken_unless_its_holder_is_stale(held, stale, want):
    """Catches: a take that overrides a live holder, or a holder gone for good that blocks the card."""
    assert outcome(call("card", "take", "CARD-002", held=held, stale=stale, register=rows(**{"CARD-002": "open"}))) == want


@pytest.mark.parametrize("other_status, stale, want", [
    pytest.param("open", {}, "take-root-busy", id="another-session-builds-in-this-root"),
    pytest.param("waiting", {}, "allow", id="the-other-card-is-paused"),
    pytest.param("closed", {}, "allow", id="the-other-card-is-closed"),
    pytest.param("open", {"CARD-009": "s9"}, "allow", id="the-other-holder-is-stale"),
])
def test_one_builder_per_task_root(other_status, stale, want):
    """Catches: two sessions building in one worktree and one index."""
    f = call("card", "take", "CARD-002", held={"CARD-009": "s9"}, stale=stale,
             register=rows(**{"CARD-009": other_status, "CARD-002": "open"}))
    assert outcome(f) == want


@pytest.mark.parametrize("ordered_by, want", [
    pytest.param("s1", "allow", id="ordered-by-this-session"),
    pytest.param("s7", "card-not-yours", id="ordered-by-another-session"),
    pytest.param("owner", "card-not-yours", id="ordered-by-the-owner"),
])
def test_a_session_releases_another_sessions_card_only_when_it_ordered_it(ordered_by, want):
    """Catches: a release of someone else's card by a session that did not order it."""
    f = call("card", "release", "CARD-001", held={"CARD-001": "s2"},
             register=rows(**{"CARD-001": core.Row("open", ordered_by)}))
    assert outcome(f) == want


def test_the_release_refusal_names_the_owners_force():
    """Catches: a release refusal that does not name the owner's --force."""
    f = call("card", "release", "CARD-001", held={"CARD-001": "s2"}, register=rows(**{"CARD-001": "open"}))
    assert "--force" in text_of(f)


def test_a_session_releases_its_own_card():
    """Checks: a session releases the card it holds."""
    assert outcome(call("card", "release", "CARD-001", held={"CARD-001": "s1"})) == "allow"


# ==== the orderer's close and open (cards.approver: orderer) ====================================================================

@pytest.mark.parametrize("problem, want", [
    pytest.param(None, "allow", id="the-orderer-closes"),
    pytest.param(("close-not-orderer", "ordered by the owner"), "close-not-orderer", id="ordered-by-the-owner"),
    pytest.param(("close-by-holder", "held by this session"), "close-by-holder", id="the-holder-is-the-orderer"),
])
def test_a_session_closes_a_card_only_as_its_orderer(problem, want):
    """Catches: a session that approves its own work, or closes a card it did not order."""
    f = call("card", "close", "CARD-001", orderer=True, register=rows(**{"CARD-001": core.Row("open", "s1", problem)}))
    assert outcome(f) == want


@pytest.mark.parametrize("args, register, want", [
    pytest.param(("card", "close", "CARD-404"), rows(**{"CARD-001": "open"}), "allow", id="no-such-card"),
    pytest.param(("card", "close"), rows(**{"CARD-001": "open"}), "allow", id="no-card-id"),
    pytest.param(("card", "close", "CARD-001"), core.RegisterFacts(problem=("register-tampered", "the seal fails")),
                 "register-tampered", id="the-seal-fails"),
])
def test_the_orderer_close_leaves_the_cli_what_is_not_its_to_decide(args, register, want):
    """Catches: a close of a card with a tampered register passing the gate."""
    assert outcome(call(*args, orderer=True, register=register)) == want


def test_a_close_by_the_orderer_leaves_the_one_use_close_permit():
    """Checks: a close by the orderer leaves the one-use close permit."""
    v = run(call("card", "close", "CARD-001", orderer=True, register=rows(**{"CARD-001": core.Row("open", "s1")})))
    assert [(p.kind, p.card) for p in v.permits] == [("close", "CARD-001")]


def test_a_close_permit_that_cannot_be_written_refuses_with_the_owners_terminal():
    """Catches: a close permit that cannot be written, with no owner's terminal named as the way out."""
    v = run(call("card", "close", "CARD-001", orderer=True, register=rows(**{"CARD-001": core.Row("open", "s1")})))
    assert (v.permits[0].on_fail.reason, "OWNER-TERMINAL" in v.permits[0].on_fail.text) == ("close-not-orderer", True)


@pytest.mark.parametrize("lead, problem, want", [
    pytest.param(True, None, "allow", id="a-lead-opens-the-card-it-ordered"),
    pytest.param(True, ("owner-only-command", "only a registered lead opens a card it ordered"), "owner-only-command",
                 id="a-lead-opens-a-card-another-ordered"),
    pytest.param(False, None, "owner-only-command", id="a-session-that-is-no-lead"),
])
def test_a_lead_opens_a_proposed_card_it_ordered_and_nothing_else(lead, problem, want):
    """Catches: a session that opens a card the owner ordered."""
    f = call("card", "open", "CARD-001", orderer=True, lead=lead,
             register=rows(**{"CARD-001": core.Row("proposed", "s1", None, problem)}))
    assert outcome(f) == want


def test_a_lead_open_leaves_the_one_use_open_permit():
    """Checks: a lead's open leaves the one-use open permit."""
    v = run(call("card", "open", "CARD-001", orderer=True, lead=True,
                 register=rows(**{"CARD-001": core.Row("proposed", "s1")})))
    assert [(p.kind, p.card) for p in v.permits] == [("open", "CARD-001")]


def test_a_release_by_the_orderer_leaves_the_one_use_release_permit():
    """Checks: a release by the orderer leaves the one-use release permit."""
    v = run(call("card", "release", "CARD-001", held={"CARD-001": "s2"},
                 register=rows(**{"CARD-001": core.Row("open", "s1")})))
    assert [(p.kind, p.card) for p in v.permits] == [("release", "CARD-001")]


@pytest.mark.parametrize("args, lead, want", [
    pytest.param(("give", "CARD-001", "s9"), True, [("by", None)], id="a-lead-hands-a-card-off"),
    pytest.param(("built", "CARD-001"), False, [("by", None)], id="built-names-the-session"),
    pytest.param(("lead", "register"), False, [("by", None)], id="lead-register-names-the-session"),
    pytest.param(("ack", "x"), False, [("by", None)], id="ack-names-the-session"),
    pytest.param(("card", "new", "T"), True, [("by", None)], id="a-lead-new-card-gets-its-order"),
    pytest.param(("card", "new", "T"), False, [], id="a-non-lead-new-card-leaves-nothing"),
])
def test_the_commands_that_name_the_session_leave_the_one_use_permit(args, lead, want):
    """Checks: the commands that name the session leave the one-use permit, and a non-lead's new card leaves none."""
    assert [(p.kind, p.card) for p in run(call(*args, lead=lead)).permits] == want


def test_a_take_that_frees_a_stale_holder_leaves_the_one_use_permit():
    """Checks: a take that frees a stale holder leaves the one-use permit."""
    f = call("card", "take", "CARD-002", held={"CARD-002": "s2"}, stale={"CARD-002": "s2"},
             register=rows(**{"CARD-002": "open"}))
    assert [(p.kind, p.card) for p in run(f).permits] == [("by", None)]


# ==== --quote-file ==============================================================================================================

QUOTE = {("quote_folders",): ("mkway/asks", "mkway/ledger")}


@pytest.mark.parametrize("rel, want", [
    pytest.param("mkway/asks/q.txt", "allow", id="inside-the-asks-folder"),
    pytest.param("mkway/ledger/q.txt", "allow", id="inside-the-ledger-folder"),
    pytest.param("elsewhere/q.txt", "quote-file-outside", id="outside-both-folders"),
    pytest.param("mkway/asks/../../q.txt", "quote-file-outside", id="climbs-out-of-the-asks-folder"),
    pytest.param(None, "quote-file-outside", id="outside-the-root"),
])
def test_a_quote_file_must_lie_in_the_quote_folders(rel, want):
    """Catches: a `--quote-file` that makes the engine read any file of the machine."""
    f = shell(reads={("calls",): (("ledger", "add", "--quote-file", "q.txt"),), ("quote_rel", "q.txt"): rel, **QUOTE})
    assert outcome(f) == want


# ==== reading the command: the exact form, the unparsed, the carried ===========================================================

def test_an_engine_call_that_is_not_the_plain_form_is_refused():
    """Catches: a chained or wrapped engine call that slips an owner command past the call rules."""
    f = shell(reads={("engine_call",): "it follows another command"})
    assert (outcome(f), "it follows another command" in text_of(f)) == ("engine-call-not-plain", True)


def test_a_plain_engine_call_is_not_refused_for_its_form():
    """Checks: a plain engine call is not refused for its form."""
    assert outcome(shell(reads={("engine_call",): None})) == "allow"


@pytest.mark.parametrize("reads", [
    pytest.param({("parse_ok",): False, ("names_commit",): True}, id="text-does-not-parse-and-names-a-commit"),
    pytest.param({("carrier",): "bash -c"}, id="a-carrier-may-run-a-commit"),
    pytest.param({("env",): "the `env` option -C is not read"}, id="env-option-not-read"),
    pytest.param({("cdpath",): True}, id="cd-under-cdpath"),
    pytest.param({("unknown_shape",): "a heredoc", ("names_commit",): True}, id="unknown-shape-names-a-commit"),
    pytest.param({("form",): ("command-unparsed", "an alias")}, id="a-git-form-the-reader-cannot-check"),
])
def test_a_command_whose_commit_or_folder_cannot_be_read_is_refused(reads):
    """Catches: an unreadable commit or folder passing, so a locked file goes in with it (an integrity gate fails closed)."""
    assert outcome(shell(git=True, reads=reads)) == "command-unparsed"


@pytest.mark.parametrize("reads", [
    pytest.param({("parse_ok",): False, ("names_commit",): False}, id="text-does-not-parse-and-names-no-commit"),
    pytest.param({("unknown_shape",): "a heredoc", ("names_commit",): False}, id="unknown-shape-names-no-commit"),
    pytest.param({("cdpath",): False, ("env",): None}, id="nothing-unreadable"),
])
def test_a_command_with_nothing_unreadable_about_a_commit_is_not_refused_as_unparsed(reads):
    """Checks: a command with nothing unreadable about a commit is not refused as unparsed."""
    assert outcome(shell(git=True, reads={("commits",): (), **reads})) == "allow"


def test_a_carried_commit_is_not_checked_without_git():
    """Checks: a carried commit is not checked without git."""
    assert outcome(shell(git=False, reads={("carrier",): "bash -c"})) == "allow"


# ==== commits ===================================================================================================================

def one(commit, reads=None):
    """A git commit with these facts."""
    return shell(git=True, reads={("commits",): (commit,), **(reads or {})})


def cmt(*paths, rels=None, **kw):
    return core.CommitFacts(paths=paths, rels=paths if rels is None else rels, **kw)


def names(*paths, problem=None):
    return core.Names(paths, problem)


PROFILE, SRC = "mkway/profile.json", "src/a.py"
SEAL = core.Seal("register.sha", True, "abc", "abc")


@pytest.mark.parametrize("spec, taken, want", [
    pytest.param("mkway", (PROFILE,), "lock-closed-commit", id="folder-takes-a-changed-profile"),
    pytest.param(".", (PROFILE,), "lock-closed-commit", id="dot-takes-a-changed-profile"),
    pytest.param("mkway/*.json", (PROFILE,), "lock-closed-commit", id="glob-takes-a-changed-profile"),
    pytest.param(PROFILE, (PROFILE,), "lock-closed-commit", id="the-profile-named"),
    pytest.param("mkway", (), "allow", id="folder-with-no-changed-tracked-file"),
    pytest.param("src", (SRC,), "allow", id="source-folder"),
    pytest.param(SRC, (SRC,), "allow", id="source-file"),
])
def test_a_commit_pathspec_is_judged_by_the_files_it_takes(spec, taken, want):
    """Catches: `git commit -- mkway` committing a changed profile because the folder name is no target."""
    assert outcome(one(cmt(spec), {("expanded", 0): names(*taken)})) == want


def test_a_pathspec_refusal_names_the_file_it_takes():
    """Catches: a pathspec refusal that does not name the file it takes."""
    f = one(cmt("mkway"), {("expanded", 0): names(PROFILE)})
    assert PROFILE in text_of(f)


@pytest.mark.parametrize("problem, want", [
    pytest.param("git exit 128", "lock-closed-commit", id="git-cannot-expand-it"),
    pytest.param(None, "allow", id="git-expands-it"),
])
def test_a_pathspec_git_cannot_expand_is_refused_never_passed(problem, want):
    """Catches: a failed expansion read as «no files», so the commit passes unchecked."""
    assert outcome(one(cmt(SRC), {("expanded", 0): names(SRC, problem=problem)})) == want


@pytest.mark.parametrize("taken, want", [
    pytest.param((PROFILE,), "lock-closed-commit", id="a-locked-file-is-staged"),
    pytest.param((SRC,), "allow", id="only-a-source-file-is-staged"),
    pytest.param((), "allow", id="nothing-is-staged"),
])
def test_a_commit_with_no_pathspec_takes_the_staged_files(taken, want):
    """Catches: `git add mkway/profile.json` then `git commit -m x` passing the gate."""
    assert outcome(one(cmt(), {("index", 0, False): names(*taken)})) == want


def test_the_staged_refusal_names_the_session_s_own_way_out():
    """Catches: a staged refusal that gives no way out for the session."""
    f = one(cmt(), {("index", 0, False): names(PROFILE)})
    assert ("git restore --staged mkway/profile.json" in text_of(f), "owner" in text_of(f)) == (True, False)


@pytest.mark.parametrize("taken, want", [
    pytest.param((PROFILE,), "lock-closed-commit", id="a-locked-file-has-a-tracked-change"),
    pytest.param((SRC,), "allow", id="only-a-source-file-changed"),
])
def test_a_commit_with_dash_a_takes_the_tracked_changes_too(taken, want):
    """Catches: `git commit -a` committing a changed locked file the session never staged."""
    assert outcome(one(cmt(all=True), {("index", 0, True): names(*taken)})) == want


def test_the_dash_a_refusal_names_the_option_and_the_way_out():
    """Catches: a -a refusal that does not name the option and the way out."""
    f = one(cmt(all=True), {("index", 0, True): names(PROFILE)})
    assert "commit without -a and name your own paths after `--`" in text_of(f)


@pytest.mark.parametrize("taken, want", [
    pytest.param((PROFILE,), "lock-closed-commit", id="amend-with-a-staged-locked-file"),
    pytest.param((), "allow", id="amend-with-nothing-staged"),
])
def test_an_amend_with_a_pathspec_still_takes_the_staged_files(taken, want):
    """Catches: `git commit --amend -- src/a.py` carrying a staged locked file in behind a named path."""
    f = one(cmt(SRC, amend=True), {("expanded", 0): names(SRC), ("index", 0, False): names(*taken)})
    assert outcome(f) == want


@pytest.mark.parametrize("read, want", [
    pytest.param(names(PROFILE, problem="git exit 128"), "lock-closed-commit", id="staged-names-cannot-be-read"),
    pytest.param(names(SRC), "allow", id="staged-names-are-read"),
])
def test_staged_names_with_include_that_cannot_be_read_refuse(read, want):
    """Catches: a failed read of the staged names passing as an empty list."""
    assert outcome(one(cmt(SRC, include=True), {("expanded", 0): names(SRC), ("staged", 0): read})) == want


@pytest.mark.parametrize("read, want", [
    pytest.param(names(problem="git exit 128"), "lock-closed-commit", id="index-names-cannot-be-read"),
    pytest.param(names(), "allow", id="index-names-are-read"),
])
def test_index_names_that_cannot_be_read_refuse(read, want):
    """Catches: a failed `git diff` under `-a` read as «nothing changed»."""
    assert outcome(one(cmt(all=True), {("index", 0, True): read})) == want


@pytest.mark.parametrize("seal, want", [
    pytest.param(SEAL, "allow", id="work-tree-register-equals-its-seal"),
    pytest.param(core.Seal("register.sha", True, "abc", "def"), "lock-closed-commit", id="work-tree-register-differs"),
    pytest.param(core.Seal("register.sha", True, "abc", None), "lock-closed-commit", id="register-file-is-missing"),
    pytest.param(core.Seal("register.sha", False), "lock-closed-commit", id="seal-file-is-missing"),
])
def test_the_register_commits_only_when_its_sha256_equals_its_seal(seal, want):
    """Catches: a register commit that skips the seal, so a forged register goes in."""
    f = one(cmt(REGISTER), {("expanded", 0): names(REGISTER), ("seal",): seal})
    assert outcome(f) == want


@pytest.mark.parametrize("seal, part", [
    pytest.param(core.Seal("register.sha", False), "register.sha is missing", id="names-the-missing-seal"),
    pytest.param(core.Seal("register.sha", True, "abc", "def"), "differs from its seal", id="says-it-differs"),
])
def test_the_register_refusal_says_why_and_gives_the_owner_fix(seal, part):
    """Catches: a register refusal that does not say why or give the owner's fix."""
    f = one(cmt(REGISTER), {("expanded", 0): names(REGISTER), ("seal",): seal})
    assert (part in text_of(f), "OWNER-FIX" in text_of(f)) == (True, True)


@pytest.mark.parametrize("blob, want", [
    pytest.param(core.Blob("abc"), "allow", id="staged-register-equals-its-seal"),
    pytest.param(core.Blob("zzz"), "lock-closed-commit", id="staged-register-is-a-forgery"),
    pytest.param(core.Blob(None, 128), "lock-closed-commit", id="staged-register-cannot-be-read"),
])
def test_with_include_the_staged_register_must_equal_its_seal_too(blob, want):
    """Catches: a staged forgery behind a restored working tree, or a failed read that passes."""
    f = one(cmt(REGISTER, include=True), {("expanded", 0): names(REGISTER), ("staged", 0): names(REGISTER),
                                              ("seal",): SEAL, ("blob", REGISTER): blob})
    assert outcome(f) == want


def test_without_include_a_staged_forgery_is_not_read():
    """Checks: without include, a staged forgery is not read and the commit is allowed."""
    f = one(cmt(REGISTER), {("expanded", 0): names(REGISTER), ("seal",): SEAL})
    assert outcome(f) == "allow"


@pytest.mark.parametrize("key, commit", [
    pytest.param(("expanded", 0), cmt(SRC), id="pathspec-expansion"),
    pytest.param(("staged", 0), cmt(SRC, include=True), id="staged-names"),
    pytest.param(("index", 0, False), cmt(), id="index-names"),
])
def test_a_git_read_that_times_out_refuses(key, commit):
    """Catches: a hung git read that passes the commit or crashes the gate."""
    reads = {("expanded", 0): names(SRC), ("staged", 0): names(SRC), key: core.Timeout(10)}
    f = one(commit, reads)
    assert (outcome(f), "10 s" in text_of(f)) == ("gate-git-timeout", True)


def test_a_staged_blob_read_that_times_out_refuses():
    """Catches: a staged blob read that times out and passes instead of refusing."""
    f = one(cmt(REGISTER, include=True), {("expanded", 0): names(REGISTER), ("staged", 0): names(REGISTER),
                                              ("seal",): SEAL, ("blob", REGISTER): core.Timeout(10)})
    assert outcome(f) == "gate-git-timeout"


@pytest.mark.parametrize("commit, want", [
    pytest.param(cmt(SRC, folder_unreadable=True), "commit-folder-unreadable", id="folder-from-a-variable"),
    pytest.param(cmt(SRC), "allow", id="folder-is-read"),
])
def test_a_commit_run_in_a_folder_the_gate_cannot_read_is_refused(commit, want):
    """Catches: `cd $WHERE && git commit -- a.py` checked against the wrong folder."""
    assert outcome(one(commit, {("expanded", 0): names(SRC)})) == want


@pytest.mark.parametrize("path, want", [
    pytest.param("$D/a.py", "pathspec-unparsed", id="a-variable-left-in-the-path"),
    pytest.param("`pwd`/a.py", "pathspec-unparsed", id="a-substitution-left-in-the-path"),
    pytest.param(":(glob)src/**", "allow", id="pathspec-magic-is-no-variable"),
    pytest.param("src/a.py", "allow", id="a-literal-path"),
])
def test_a_commit_path_still_holding_a_variable_is_refused(path, want):
    """Catches: a commit path built from a variable the gate cannot read, naming a locked file at run time."""
    assert outcome(one(cmt(path), {("expanded", 0): names(SRC)})) == want


def test_without_git_no_commit_is_checked():
    """Checks: without git no commit is checked."""
    assert outcome(shell(git=False, reads={("commits",): (cmt(PROFILE),)})) == "allow"


# ==== forged writes: the decision for the facts the reader gives ================================================================

@pytest.mark.parametrize("facts, want", [
    pytest.param(edit("mkway/locks/x.json"), "lock-file-by-session", id="edit-of-a-lock-file"),
    pytest.param(shell(reads={("writes",): w("mkway/locks/x.json")}), "lock-file-by-session", id="redirect-into-the-locks-folder"),
    pytest.param(shell(reads={("engine_call",): "a command is chained in front of it"}), "engine-call-not-plain",
                 id="chained-lock-open"),
    pytest.param(call("card", "set", "CARD-001", "open", held={"CARD-001": "s1"},
                      register=rows(**{"CARD-001": "waiting-owner"})), "owner-only-command",
                 id="reopen-from-waiting-owner"),
    pytest.param(call("card", "set", "CARD-001", "closed"), "owner-only-command", id="set-closed-by-a-session"),
    pytest.param(shell("python -c \"import runpy; runpy.run_path('mkway/engine/mkway.py')\"",
                       reads={("writes",): w(reason="capable")}), "lock-closed-shell", id="runpy-of-the-engine-script"),
])
def test_a_forged_write_to_a_lock_file_the_engine_or_the_register_is_refused(facts, want):
    """Catches: a forge shape (an edit, a redirect, a chained engine call, a reopen, a runpy) that slips past."""
    assert outcome(facts) == want


# ==== the interface: a fact that is not there is asked for by name ==============================================================

@pytest.mark.parametrize("facts, key", [
    pytest.param(core.Facts(tool_name="Bash"), ("engine_call",), id="a-shell-command-needs-its-engine-call-first"),
    pytest.param(core.Facts(tool_name="Edit", targets=(DOCS,), edit_rels=("other",)),
                 ("disk", "other", "docs/**/*.md"), id="a-glob-target-needs-the-files-on-disk"),
    pytest.param(shell(reads={("calls",): (("card", "take", "CARD-002"),)}), ("holders",),
                 id="a-take-needs-who-holds-what"),
    pytest.param(shell(reads={("calls",): (("give", "C", "s9"),)}), ("lead",), id="a-give-needs-to-know-whether-it-is-a-lead"),
])
def test_a_missing_fact_is_asked_for_by_its_key(facts, key):
    """Catches: a core that guesses a fact it was not given instead of asking the shell to read it."""
    v = core.decide(facts)
    assert (v.kind, v.need) == (core.NEED, key)


def test_a_decision_that_does_not_reach_a_fact_never_asks_for_it():
    """Checks: a decision that does not reach a fact never asks for it."""
    assert core.decide(core.Facts(tool_name="Edit", targets=BUILT_IN, edit_rels=("mkway/profile.json",))).kind == core.REFUSE


@pytest.mark.parametrize("make", [
    pytest.param(lambda: core.Verdict("deny", "r", "t"), id="unknown-kind"),
    pytest.param(lambda: core.refuse("", "no reason"), id="refusal-without-a-reason"),
    pytest.param(lambda: core.refuse("r", ""), id="refusal-without-a-text"),
    pytest.param(lambda: core.Verdict(core.NEED), id="need-without-a-key"),
])
def test_a_verdict_that_is_malformed_is_not_built(make):
    """Catches: a refusal that reaches the dispatcher with no reason id or no message."""
    with pytest.raises(ValueError):
        make()


@pytest.mark.parametrize("facts", [
    pytest.param(edit(REGISTER), id="edit"),
    pytest.param(shell(reads={("writes",): w(REGISTER)}), id="shell-write"),
    pytest.param(call("lock", "open", "x"), id="owner-command"),
    pytest.param(call("card", "take", "CARD-002", held={"CARD-002": "s2"}, register=rows(**{"CARD-002": "open"})),
                 id="held-card"),
    pytest.param(one(cmt(PROFILE), {("expanded", 0): names(PROFILE)}), id="commit"),
    pytest.param(one(cmt(SRC), {("expanded", 0): core.Timeout(5)}), id="git-timeout"),
])
def test_every_refusal_names_a_reason_the_core_declares(facts):
    """Catches: a refusal whose reason id the manifest of the lock gate does not declare."""
    assert run(facts).reason in core.REASONS


def test_the_guard_of_this_file_fails_on_disk_access():
    """Catches: a guard that cannot fail, so a core that read a file would pass every case here."""
    with no_io(), pytest.raises(AssertionError):
        open(os.devnull)
