"""The owner hold (card MW-010, part 1): a profile lock target that is open by default and closes with a marker.
Synthetic task roots only; no task data."""
import json
import subprocess

import pytest

from _engine import cli, gate_call, task_root
import gate_lock
import schema_check

GIT_ID = ["-c", "user.name=mkway-test", "-c", "user.email=mkway-test"]
HOLD = {"name": "hold", "paths": ["**"], "open_by_default": True}
WORD = "hold by the owner; wait for the owner's word"


def _git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


def _profile(targets):
    return {"vcs": "none", "bundle": {"root": "mkway"}, "gates": {}, "state": {"dir": "mkway/state"},
            "python": {"command": "python"}, "locks": {"targets": targets}}


def _edit(root, path):
    return gate_call(gate_lock.check, root, tool="Edit", tool_input={"file_path": path}, session="s1")


def _shell(root, command):
    return gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session="s1")


def _reason(v):
    return v.reason_id if v.kind == "refuse" else "allow"


@pytest.fixture
def held(tmp_path):
    root = task_root(tmp_path, vcs="git", name="held", locks={"targets": [HOLD]})
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    assert cli(root, "card", "new", "First")[0] == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "start")
    return root


def test_schema_accepts_open_by_default_on_a_profile_target():
    """E1 (part 1): `open_by_default: true` on a profile lock target is valid; a value that is not a boolean is not.
    Catches: a schema that still refuses the key, or one that takes any value."""
    assert schema_check.check(_profile([HOLD])) == []
    assert schema_check.check(_profile([{"name": "hold", "paths": ["**"], "open_by_default": "yes"}])) != []


def test_schema_refuses_open_by_default_on_a_built_in_name():
    """E2 (part 1): the flag on a built-in target name is refused by the schema check, with a text naming the target
    and the flag; the same target without the flag is not this check's business. Catches: a built-in target that a
    profile could open by default."""
    from locks import built_in
    names = [t.name for t in built_in(".", {"bundle": {"root": "mkway"}})]
    assert len(names) >= 9
    for name in names:
        errors = schema_check.check(_profile([{"name": name, "paths": ["x"], "open_by_default": True}]))
        assert any(name in e and "open_by_default" in e and "built-in" in e for e in errors), (name, errors)
    assert schema_check.check(_profile([{"name": "engine", "paths": ["x"]}])) == []


def test_no_marker_lets_one_edit_and_one_commit_pass(held):
    """E3 (part 1): an open-by-default target with no marker file is open to the edit gate and to the shell gate,
    commit included. Catches: a target that is closed until the owner opens it, as every other target is."""
    assert _reason(_edit(held, "src/a.py")) == "allow"
    assert _reason(_shell(held, "git commit -m 'CARD-001 x' -- src/a.py")) == "allow"


def test_a_marker_refuses_the_edit_and_the_commit_until_the_owner_opens(held):
    """E4 (part 1): `lock close hold` writes the marker and both gates refuse with the lock text plus the hold text;
    `--minutes` is ignored; `lock open hold` removes the marker and both pass again; a session cannot run either
    command. Catches: a gate that reads no marker, a marker that expires, or a hold a session can lift."""
    code, _, _ = cli(held, "lock", "close", "hold", "--minutes", "5")
    assert code == 0
    marker = held / "mkway" / "locks" / "hold.json"
    assert marker.is_file()
    edit = _edit(held, "src/a.py")
    commit = _shell(held, "git commit -m 'CARD-001 x' -- src/a.py")
    assert (_reason(edit), _reason(commit)) == ("lock-closed-edit", "lock-closed-commit")
    for verdict in (edit, commit):
        assert "'hold'" in verdict.message and WORD in verdict.message
    assert _reason(_shell(held, "python mkway/engine/mkway.py lock open hold")) == "owner-only-command"
    assert cli(held, "lock", "open", "hold", "--minutes", "5")[0] == 0
    assert not marker.exists()
    assert cli(held, "lock", "open", "hold")[0] == 0  # no marker left: still fine
    assert _reason(_edit(held, "src/a.py")) == "allow"
    assert _reason(_shell(held, "git commit -m 'CARD-001 x' -- src/a.py")) == "allow"


def test_hold_and_go_do_what_lock_close_and_open_do(held, tmp_path):
    """E7 (part 3, R123): `mkway hold` writes the marker `lock close hold` writes and `mkway go` removes it; the gates
    then refuse and pass as for the long forms; a profile with no `hold` target gets a refusal that names the target
    and the profile line, and writes no marker. Catches: a short form that does something else, or one that fails
    silently on a profile without the target."""
    marker = held / "mkway" / "locks" / "hold.json"
    code, out, _ = cli(held, "hold")
    assert code == 0 and marker.is_file() and "hold" in out
    assert _reason(_edit(held, "src/a.py")) == "lock-closed-edit"
    code, out, _ = cli(held, "go")
    assert code == 0 and not marker.exists()
    assert _reason(_edit(held, "src/a.py")) == "allow"
    bare = task_root(tmp_path, vcs="git", name="bare", locks={"targets": []})
    for word in ("hold", "go"):
        code, out, err = cli(bare, word)
        text = out + err
        assert code != 0 and "no hold target" in text and "locks.targets" in text and "open_by_default" in text, text
    assert not (bare / "mkway" / "locks" / "hold.json").exists()


def test_hold_and_go_are_refused_inside_a_session(held):
    """E8 (part 3, R123): inside a session `mkway hold` and `mkway go` are owner-only, as the long forms are: the CLI
    refuses with `owner-only-command` and writes nothing, and the lock gate refuses the shell call. Catches: a short
    form a session can use to lift or set the hold."""
    marker = held / "mkway" / "locks" / "hold.json"
    for word in ("hold", "go"):
        code, out, err = cli(held, word, session=True)
        assert code != 0 and "owner-only-command" in err, (word, err)
        assert not marker.exists()
        assert _reason(_shell(held, f"python mkway/engine/mkway.py {word}")) == "owner-only-command"
    cli(held, "hold")
    assert cli(held, "go", session=True)[0] != 0 and marker.is_file()


def test_lock_list_and_the_start_line_show_both_states(held):
    """E5 (part 1): `lock list` shows `hold: open (default)` with no marker and `hold: closed by the owner` with one;
    the start block's locks line counts the marker file. Catches: a list that shows nothing for a target that is open
    by default, or a start block that does not count the marker."""
    import startline
    profile_file = held / "mkway" / "profile.json"
    profile = json.loads(profile_file.read_text(encoding="utf-8"))
    assert "hold: open (default)" in cli(held, "lock", "list")[1]
    assert "locks: 0 files" in startline.render(held, profile_file, profile, [], [], {}, session="s1")
    cli(held, "lock", "close", "hold")
    out = cli(held, "lock", "list")[1]
    assert "hold: closed by the owner" in out and "open (default)" not in out
    assert "locks: 1 files" in startline.render(held, profile_file, profile, [], [], {}, session="s1")
