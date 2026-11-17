"""Card MW-107 (rulings R274, R274a and R274e): the shell of the outside gate (`gate_outside`, the entries `outside.edit` and
`outside.shell`, class integrity). The near miss of each pass shape, a delete program that hides nothing, the unread row of a
`writes anywhere` shape, `NUL` as a case that can fail, and the base a relative path is read from (the edit tool and the shell
both join it to the cwd). Fake home and temp folders only; synthetic names and sessions only."""
import json
from collections import namedtuple

import pytest

import _mw017 as lead_helpers
from _engine import gate_call
import gate_lead
import gate_outside
import logs

World = namedtuple("World", "root home temp elsewhere")
LEAD, SESSION = "lead-a", "s2"


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


def outside_edit(root, path, **kw):
    return verdict_of(gate_call(gate_outside.edit, root, tool="Write", tool_input={"file_path": str(path), "content": "x"},
                                session=SESSION, **kw))


def shell(root, command, session=SESSION, **kw):
    """The shell steps in manifest order: a lead is judged by the lead gate, a session by the outside gate (R274e)."""
    gate = gate_lead.shell if session == LEAD else gate_outside.shell
    return verdict_of(gate_call(gate, root, tool="Bash", tool_input={"command": command}, session=session, **kw))


def log_rows(world, reason):
    path = world.root / "mkway" / "state" / logs.REFUSALS
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []
    return [r for r in rows if r.get("reason_id") == reason]


NEAR_MISSES = [
    case("a-quoted-redirect-sign-then-a-real-one", 'echo "a > b" > {e}/x.txt'),
    case("a-heredoc-with-a-real-redirect", "cat <<EOF > {e}/x.txt\nline\nEOF"),
    case("a-path-in-a-message-then-a-real-one", 'echo "see {e}/y.txt" > {e}/x.txt'),
    case("dev-null-then-a-real-one", "echo x 2>/dev/null > {e}/x.txt"),
    case("nul-then-a-real-one", "echo x > NUL; echo y > {e}/x.txt"),
    case("2-and-1-then-a-real-one", "echo x 2>&1 > {e}/x.txt"),
]


@pytest.mark.parametrize("command", NEAR_MISSES)
@pytest.mark.parametrize("session", [SESSION, LEAD])
def test_a_near_miss_of_each_pass_shape_is_refused_for_a_session_and_a_lead(world, session, command):
    """Catches: R274a 8.1 (W75), a command that holds one of the six pass shapes and also a real write position outside the root, which passes because of the shape."""
    assert shell(world.root, command.format(e=world.elsewhere.as_posix()), session=session)[0] == "write-outside-root"


def test_nul_is_a_pass_shape_that_can_fail(world):
    """Catches: R274e (6), `> NUL` read as a file: with the shell started outside the root, a plain relative target cannot be placed (one unread row) and `NUL` must leave no row and no refusal."""
    nul = shell(world.root, "echo x > NUL", cwd=str(world.elsewhere))[0]
    rows_after_nul = len(log_rows(world, "write-target-unread"))
    plain = shell(world.root, "echo x > a.txt", cwd=str(world.elsewhere))[0]
    assert (nul, rows_after_nul, plain, len(log_rows(world, "write-target-unread"))) == ("allow", 0, "allow", 1)


def test_a_delete_program_does_not_hide_a_write_outside_the_root(world):
    """Catches: R274e (3), a command that names a delete program anywhere and is then left unjudged: only the delete program's own target is the delete gate's."""
    e = world.elsewhere.as_posix()
    got = (shell(world.root, f"rm a.txt; echo x > {e}/conftest.py")[0], shell(world.root, f"echo rm > {e}/x.txt")[0],
           shell(world.root, f"rm a.txt && echo x > {e}/y.txt && rm b.txt")[0])
    assert got == ("write-outside-root",) * 3


def test_the_delete_programs_own_target_is_left_to_the_delete_gate_and_an_inside_write_passes(world):
    """Checks: the other half of R274e (3), `rm` of an outside file alone and a delete followed by a write inside the root are no outside refusal."""
    e = world.elsewhere.as_posix()
    got = (shell(world.root, f"rm {e}/x.txt")[0], shell(world.root, f"rm {e}/x.txt; rm -f {e}/y.txt")[0],
           shell(world.root, "rm a.txt && echo y > src/a.py")[0])
    assert got == ("allow",) * 3


def test_a_redirect_on_a_delete_command_is_still_judged(world):
    """Catches: R274e (3), a redirect on the delete program's own line (`rm a.txt > outside`), which passes because the line names a delete program."""
    assert shell(world.root, f"rm a.txt > {world.elsewhere.as_posix()}/log.txt")[0] == "write-outside-root"


@pytest.mark.parametrize("command", [
    case("eval-of-a-variable", 'eval "$CMD"'),
    case("an-unreadable-target", "echo x > $TARGET/a.txt"),
])
def test_a_writes_anywhere_shape_of_a_session_passes_with_one_unread_row(world, command):
    """Catches: R274e (4), R274a 8.2, a shape that may write anywhere (a program with no readable target, a computed path) that passes a session with no calls-log row: the scorecard must count the pass."""
    got = shell(world.root, command)[0]
    (row,) = log_rows(world, "write-target-unread")
    assert (got, row["kind"], row["verdict"], row["target"]) == ("allow", "log", "allow", command)


@pytest.mark.parametrize("command", [
    case("a-delete-line-with-an-exec", "find . -name x -delete -exec touch {} +"),
    case("a-delete-line-with-an-fprint", "find . -name x -delete -fprint out.txt"),
    case("an-fprint-alone", "find . -fprint out.txt"),
])
def test_a_find_that_may_write_anywhere_leaves_the_unread_row_even_on_a_delete_line(world, command):
    """Catches: R274e (4), round-2 reader item 2, the delete line of a `find` that also runs `-exec` or writes with `-fprint`: the delete targets are the delete gate's, but the program that may write anywhere still passes a session only with its row."""
    got = shell(world.root, command)[0]
    assert (got, len(log_rows(world, "write-target-unread"))) == ("allow", 1)


@pytest.mark.parametrize("command", [
    case("a-find-delete-alone", "find . -name x -delete"),
    case("a-remove-alone", "rm a.txt"),
])
def test_a_delete_alone_leaves_no_unread_row(world, command):
    """Checks: the pair of the test above: a delete and nothing else that may write is the delete gate's business, no row of the outside gate."""
    assert (shell(world.root, command)[0], log_rows(world, "write-target-unread")) == ("allow", [])


def test_a_lead_is_refused_for_a_writes_anywhere_shape_and_leaves_no_unread_row(world):
    """Checks: the unread row records a pass; the lead gate refuses the same shape (`lead-no-edit`), so no row is written for the lead."""
    assert (shell(world.root, 'eval "$CMD"', session=LEAD)[0], log_rows(world, "write-target-unread")) == ("lead-no-edit", [])


# ---- the base of a relative path: the edit tool and the shell both join it to the cwd (R274e 11) -------------------------

def relative_edit(world, path, cwd):
    return verdict_of(gate_call(gate_outside.edit, world.root, tool="Write", tool_input={"file_path": path, "content": "x"},
                                session=SESSION, cwd=str(cwd)))


def relative_redirect(world, path, cwd):
    return shell(world.root, f"echo x > {path}", cwd=str(cwd))


@pytest.mark.parametrize("path, cwd_parts, expected", [
    case("up-from-a-folder-lands-inside", "../notes/a.md", ("src",), "allow"),
    case("up-two-levels-lands-outside", "../../notes/a.md", ("src",), "write-outside-root"),
    case("a-plain-name-in-the-root", "a.md", (), "allow"),
])
def test_a_relative_path_is_joined_to_the_cwd_by_the_edit_tool_and_by_the_shell(world, path, cwd_parts, expected):
    """Catches: R274e (11), two bases for one relative path: the edit tool reading it from the root while the shell reads it from the cwd (or the reverse); both give the same verdict."""
    cwd = world.root.joinpath(*cwd_parts)
    assert (relative_edit(world, path, cwd)[0], relative_redirect(world, path, cwd)[0]) == (expected, expected)


def test_a_relative_edit_path_with_the_cwd_outside_the_root_is_outside(world):
    """Catches: R274e (11), a relative edit path of a session whose cwd lies outside its root, read from the root and let through."""
    assert relative_edit(world, "a.md", world.elsewhere)[0] == "write-outside-root"


def test_a_session_edit_inside_the_root_passes_the_outside_gate(world):
    """Checks: the nearest allow of the gate: a file inside the root is no business of the outside gate (the card rules are the subtask gate's)."""
    assert outside_edit(world.root, world.root / "src" / "a.py")[0] == "allow"


def test_the_lead_edit_of_a_relative_order_path_is_read_from_the_cwd(world):
    """Catches: R274e (11), the lead's edit of a relative path read from the root instead of the cwd: a lead started in its card folder writes `ORDER.md` there."""
    folder = world.root / "mkway" / "asks"
    folder.mkdir(parents=True, exist_ok=True)
    got = verdict_of(gate_call(gate_lead.edit, world.root, tool="Write",
                               tool_input={"file_path": "q_ask.md", "content": "x"}, session=LEAD, cwd=str(folder)))
    assert got[0] == "allow"
    assert lead_edit(world.root, world.root / "mkway" / "asks" / "q_ask.md")[0] == "allow"


# ---- one base for every gate of the edit group (round-2 reader item 1) -------------------------------------------------

def test_the_lock_gate_reads_a_relative_edit_path_from_the_same_cwd_as_the_outside_gate(world):
    """Catches: round-2 reader item 1, the cwd base split: the outside and subtask gates join a relative edit path to the hook cwd while the lock gate read it from the root, so a write from a locked folder named `x.txt` was checked as `x.txt` and let through."""
    import gate_lock
    locked = world.root / "mkway" / "engine"
    locked.mkdir(parents=True, exist_ok=True)
    absolute = verdict_of(gate_call(gate_lock.check, world.root, tool="Write",
                                    tool_input={"file_path": str(locked / "x.txt"), "content": "x"}, session=SESSION))
    relative = verdict_of(gate_call(gate_lock.check, world.root, tool="Write",
                                    tool_input={"file_path": "x.txt", "content": "x"}, session=SESSION, cwd=str(locked)))
    assert (absolute[0], relative[0]) == ("lock-closed-edit", "lock-closed-edit")


def test_the_lock_gate_allows_the_same_relative_name_from_the_root(world):
    """Checks: the near miss of the test above: the same relative name with the cwd at the root is no lock target."""
    import gate_lock
    got = verdict_of(gate_call(gate_lock.check, world.root, tool="Write",
                               tool_input={"file_path": "x.txt", "content": "x"}, session=SESSION, cwd=str(world.root)))
    assert got[0] == "allow"
