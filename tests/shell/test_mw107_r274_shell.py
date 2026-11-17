"""Card MW-107 (ruling R274 and R274a): the shells of the edit and shell gates judge a write outside the session's root for
every session: another checkout of the same repository is outside whatever the nesting, the reach rule judges real write
positions only, an unreadable write passes for a session and stays refused for a lead (with its way out), an owner's addition
to `paths.outside_writable` counts at the next call, and the start line names the root. Fake home and temp folders only
(USERPROFILE, HOME, TEMP and TMP point at tmp_path); linked checkouts are made by real git in scratch folders. Synthetic names
and sessions only."""
import json
import os
from collections import namedtuple

import pytest

from _engine import gate_call
import _mw017 as lead_helpers
import gate_lead
import gate_outside
import gate_subtask
import helpers
import logs
from test_install import git
from test_startline import _render, task  # noqa: F401  (the start-block fixture, a root with no vcs)

World = namedtuple("World", "root home temp elsewhere")
LEAD, SESSION = "lead-a", "s2"
WAY_OUT = "a file the task needs elsewhere is a folder the owner adds to paths.outside_writable"


def case(id_, *values):
    return pytest.param(*values, id=id_)


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A task root `main` (vcs none) with `lead-a` registered as a lead and `s2` a session that is no lead."""
    home, temp, elsewhere = tmp_path / "home", tmp_path / "temp", tmp_path / "elsewhere"
    for folder in (home, temp, elsewhere):
        folder.mkdir()
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(home))
    for name in ("TEMP", "TMP"):
        monkeypatch.setenv(name, str(temp))
    root = lead_helpers.lead_root(tmp_path, name="main")
    lead_helpers.register_lead(root, LEAD)
    return World(root, home, temp, elsewhere)


def verdict_of(verdict):
    return (verdict.reason_id, verdict.message) if verdict.kind == "refuse" else ("allow", "")


def lead_edit(root, path, **kw):
    return verdict_of(gate_call(gate_lead.edit, root, tool="Write", tool_input={"file_path": str(path), "content": "x"},
                                session=LEAD, **kw))


def session_edit(root, path, **kw):
    return verdict_of(gate_call(gate_subtask.check, root, tool="Write", tool_input={"file_path": str(path), "content": "x"},
                                session=SESSION, **kw))


def outside_edit(root, path, **kw):
    """R274e: a session's edit outside the root is judged by the outside gate (the subtask gate keeps the card rules)."""
    return verdict_of(gate_call(gate_outside.edit, root, tool="Write", tool_input={"file_path": str(path), "content": "x"},
                                session=SESSION, **kw))


def shell(root, command, session=SESSION, **kw):
    """The shell steps in manifest order: a lead is judged by the lead gate, a session by the outside gate (R274e)."""
    gate = gate_lead.shell if session == LEAD else gate_outside.shell
    return verdict_of(gate_call(gate, root, tool="Bash", tool_input={"command": command}, session=session, **kw))


def real(path):
    return os.path.realpath(path).replace("\\", "/")


def linked(root, name="nested-wt"):
    """The root made a git repository with one commit, and a linked checkout of it below the root."""
    git(root, "init", "-q")
    (root / ".gitkeep").write_text("x", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    git(root, "worktree", "add", "-q", str(root / name), "-b", "wt-" + name)
    return root / name


# ---- another checkout of the same repository is outside ----------------------------------------------------------------

@pytest.mark.real_shared_state
def test_a_write_into_a_linked_checkout_below_the_root_is_refused_for_a_lead_and_a_session(world):
    """Catches: the incident class, a session at the main checkout that writes into a linked checkout below its own root (the folder nesting hides it from the root rule)."""
    nested = linked(world.root)
    target = nested / "src" / "a.py"
    got = (lead_edit(world.root, target), outside_edit(world.root, target))
    assert [reason for reason, _ in got] == ["write-outside-root", "write-outside-root"]
    assert all(f"write the file inside {real(world.root)};" in message and WAY_OUT in message for _, message in got)


@pytest.mark.real_shared_state
def test_a_plain_folder_below_the_root_is_not_a_checkout(world):
    """Checks: the nearest allow of the linked-checkout refusal, a folder below the root that no checkout owns is judged by the card and lead rules, not by the outside rule."""
    nested = linked(world.root)
    target = world.root / "plain" / "a.py"
    place = real(nested).casefold() if os.name == "nt" else real(nested)
    assert (helpers.checkouts_below(world.root), lead_edit(world.root, target)[0], session_edit(world.root, target)[0]) == (
        ((place,), ""), "lead-no-edit", "no-open-card")  # the list names the one linked checkout and not the plain folder


@pytest.mark.real_shared_state
def test_the_main_checkout_seen_from_a_linked_checkout_is_outside(world, tmp_path):
    """Catches: a session in a linked checkout that writes a file of the main checkout by its absolute path (the wrong-worktree class)."""
    nested = linked(world.root)
    inner = lead_helpers.lead_root(nested.parent, name=nested.name)  # the install root of the linked checkout
    lead_helpers.register_lead(inner, LEAD)
    got = (lead_edit(inner, world.root / "src" / "a.py")[0], outside_edit(inner, world.root / "src" / "a.py")[0],
           lead_edit(inner, inner / "src" / "a.py")[0])
    assert got == ("write-outside-root", "write-outside-root", "lead-no-edit")


@pytest.mark.real_shared_state
def test_an_unreadable_list_of_checkouts_never_passes_silently(world):
    """Catches: a hook that cannot read the linked-checkout list and lets the write through, or that fails the call, or that says nothing (R274 design note)."""
    nested = linked(world.root)
    pointer = world.root / ".git" / "worktrees" / nested.name / "gitdir"
    pointer.unlink()
    pointer.mkdir()  # a folder where the file should be: reading it fails
    target = nested / "src" / "a.py"
    got = lead_edit(world.root, target)[0]
    state = world.root / "mkway" / "state" / logs.REFUSALS
    rows = [json.loads(line) for line in state.read_text(encoding="utf-8").splitlines() if line.strip()]
    noted = [r for r in rows if r.get("reason_id") == "write-target-unresolved" and r.get("kind") == "log"
             and "worktree" in str(r.get("note"))]
    assert (got, len(noted) >= 1) == ("lead-no-edit", True)  # judged by the root rule: inside the root, and not the lead's


def test_a_root_with_no_checkouts_reads_no_list(world):
    """Checks: a root with no vcs (the install root) has no linked checkouts: a path below it is judged by the root rule alone and nothing is logged."""
    got = lead_edit(world.root, world.root / "plain" / "a.py")[0]
    assert (helpers.checkouts_below(world.root), got, (world.root / "mkway" / "state" / logs.REFUSALS).exists()) == (
        ((), ""), "lead-no-edit", False)


# ---- the reach rule: real write positions only ---------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    case("a-quoted-redirect-sign", 'echo "a > {elsewhere}/x.txt"'),
    case("a-heredoc-body", "cat <<'EOF'\nline > {elsewhere}/x.txt\nEOF"),
    case("a-path-in-a-message", 'git commit -m "see {elsewhere}/x.txt"'),
    case("redirect-to-dev-null", "echo x >/dev/null"),
    case("redirect-to-nul", "echo x > NUL"),
    case("stderr-to-stdout", "ls 2>&1"),
])
def test_a_shape_that_names_no_outside_write_target_passes(world, command):
    """Checks: R274a 8.1, a quoted `>`, a heredoc body, a path inside a message string, `>/dev/null`, `NUL` and `2>&1` are no write position: they pass for a session."""
    assert shell(world.root, command.format(elsewhere=world.elsewhere.as_posix()))[0] == "allow"


def test_a_named_outside_write_target_is_refused_and_an_unreadable_one_passes_for_a_session(world):
    """Catches: R274 5.5, a named outside write target that passes, or an unreadable one that blocks a session that is no lead."""
    named = shell(world.root, f"echo x > {world.elsewhere.as_posix()}/a.txt")[0]
    unreadable = shell(world.root, "echo x > $TARGET/a.txt")[0]
    assert (named, unreadable) == ("write-outside-root", "allow")


def log_rows(world, reason):
    path = world.root / "mkway" / "state" / logs.REFUSALS
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []
    return [r for r in rows if r.get("reason_id") == reason]


def test_an_unreadable_write_that_passes_for_a_session_leaves_one_calls_log_row(world):
    """Catches: R274a 8.2, a pass of an unreadable write target that the scorecard cannot count: the row `write-target-unread`, kind log, verdict allow, naming the session and the command."""
    command = "echo x > $TARGET/a.txt"
    assert shell(world.root, command)[0] == "allow"
    (row,) = log_rows(world, "write-target-unread")
    assert (row["kind"], row["verdict"], row["session"], row["target"]) == ("log", "allow", SESSION, command)


@pytest.mark.parametrize("command, expected", [
    case("a-readable-write-inside", "echo x > src/a.py", "allow"),
    case("a-readable-write-outside-is-refused", "echo x > {elsewhere}/a.txt", "write-outside-root"),
    case("a-read", "cat {elsewhere}/a.txt", "allow"),
    case("dev-null", "echo x >/dev/null", "allow"),
    case("stderr-to-stdout", "ls 2>&1", "allow"),
])
def test_a_command_with_a_readable_target_leaves_no_unread_row(world, command, expected):
    """Checks: R274a 8.2, the row is for the pass of a target the reader could not read, never for a readable write or a read; the verdict of each is the one the case names (R274e 12)."""
    got = shell(world.root, command.format(elsewhere=world.elsewhere.as_posix()))[0]
    assert (got, log_rows(world, "write-target-unread")) == (expected, [])


def test_a_lead_unreadable_write_is_refused_and_leaves_no_unread_row(world):
    """Checks: the row records a pass; a lead's unreadable write is refused (`lead-no-edit`), so it is not a pass."""
    assert shell(world.root, "echo x > $TARGET/a.txt", session=LEAD)[0] == "lead-no-edit"
    assert log_rows(world, "write-target-unread") == []


def test_the_old_key_is_no_profile_error_and_counts_as_an_alias_until_the_upgrade_renames_it(world):
    """Catches: R274b 1, a profile that still holds `leads.outside_writable` that is refused at hook time, or whose folders stop counting before the upgrade renames the key; the folders of `paths.outside_writable` come first and a folder is listed once."""
    import profiles
    base = {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
            "python": {"command": "python"}}
    old = {**base, "leads": {"outside_writable": ["/abs/old/**", "/abs/both/**", "relative/**"]}}
    both = {**old, "paths": {"outside_writable": ["/abs/both/**", "/abs/new/**"]}}
    defaults = ["<home>/.claude/projects/*/memory/**", "<home>/.claude/plans/**", "<temp>/claude/**"]
    odd = {**base, "leads": {"outside_writable": 7}}
    assert (profiles.validate(old), profiles.validate(both), profiles.validate(odd)) == ([], [], [])
    assert profiles.outside_writable(old) == defaults + ["/abs/old/**", "/abs/both/**"]
    assert profiles.outside_writable(both) == defaults + ["/abs/both/**", "/abs/new/**", "/abs/old/**"]
    assert profiles.outside_writable(odd) == defaults


def test_a_folder_of_the_old_key_still_opens_for_a_session_until_the_rename(world):
    """Catches: R274b 1, nothing gets narrower before the rename: a folder the owner listed under the old key is still writable by a session."""
    target = world.elsewhere / "data" / "a.csv"
    before = (outside_edit(world.root, target)[0], shell(world.root, f"echo x > {target.as_posix()}")[0])
    file = world.root / "mkway" / "profile.json"
    profile = json.loads(file.read_text(encoding="utf-8"))
    profile["leads"] = {**profile.get("leads", {}), "outside_writable": [world.elsewhere.as_posix() + "/data/**"]}
    file.write_text(json.dumps(profile), encoding="utf-8")
    after = (outside_edit(world.root, target)[0], shell(world.root, f"echo x > {target.as_posix()}")[0])
    assert (before, after) == (("write-outside-root", "write-outside-root"), ("allow", "allow"))  # the old key alone opens it


def test_the_lead_keeps_its_stricter_rule_for_an_unreadable_write(world):
    """Catches: a lead that writes through a path the gate cannot read (R274 5.5: the lead keeps its stricter rule, never weaker)."""
    assert shell(world.root, "echo x > $TARGET/a.txt", session=LEAD)[0] == "lead-no-edit"


def test_the_lead_unreadable_write_names_a_way_out_that_works(world):
    """Catches: R274a 8.7, the lead's stricter rule refuses with no way out: the same write with a plain path, or the edit tool, is allowed."""
    reason, message = shell(world.root, "echo x > $TARGET/q_ask.md", session=LEAD)
    plain = shell(world.root, "echo x > mkway/asks/q_ask.md", session=LEAD)[0]
    by_tool = lead_edit(world.root, world.root / "mkway" / "asks" / "q_ask.md")[0]
    assert (reason, "plain path" in message and "edit tool" in message, plain, by_tool) == (
        "lead-no-edit", True, "allow", "allow")


# ---- an owner's addition counts at the next call ---------------------------------------------------------------------------

def test_an_owner_addition_to_the_list_takes_effect_at_the_next_call(world):
    """Catches: R274a 8.8, a profile addition that waits for a restart: the profile is read at each call."""
    target = world.elsewhere / "data" / "a.csv"
    before = outside_edit(world.root, target)[0]
    file = world.root / "mkway" / "profile.json"
    profile = json.loads(file.read_text(encoding="utf-8"))
    profile["paths"] = {**profile.get("paths", {}), "outside_writable": [world.elsewhere.as_posix() + "/data/**"]}
    file.write_text(json.dumps(profile), encoding="utf-8")
    after = (outside_edit(world.root, target)[0], shell(world.root, f"echo x > {target.as_posix()}")[0])
    assert (before, after) == ("write-outside-root", ("allow", "allow"))


# ---- the start line names the root ---------------------------------------------------------------------------------------------

def test_the_start_line_names_the_root_of_a_root_with_no_vcs(task):  # noqa: F811
    """Catches: R274 5.8 and R274a 8.11, a start block with no root sentence, or one that names another folder than the install root of a folder with no vcs."""
    lines = _render(task).splitlines()
    assert lines[1] == f"root: {real(task)}; every path you write starts here"
