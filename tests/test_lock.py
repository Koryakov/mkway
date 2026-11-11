"""The lock gate, the owner-only commands and the register seal (card MW-003, deliverable 3; spec section 1,
L1-L8; R18, R19a, R19c). Synthetic task roots only; gates are called with the dispatcher's own context."""
import datetime
import json
import os
import subprocess
import threading
import time

import pytest

from _engine import cli, gate_call, jsonl, task_root
import gate_lock
import records
import register

GIT_ID = ["-c", "user.name=mkway-test", "-c", "user.email=mkway-test"]


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _set_profile(root, **over):
    p = _profile(root)
    p.update(over)
    (root / "mkway" / "profile.json").write_text(json.dumps(p, indent=2), encoding="utf-8")


def edit(root, path, session="s1", tool="Edit"):
    return gate_call(gate_lock.check, root, tool=tool, tool_input={"file_path": path}, session=session)


def shell(root, command, session="s1", tool="Bash"):
    return gate_call(gate_lock.check, root, tool=tool, tool_input={"command": command}, session=session)


def _reason(v):
    return v.reason_id if v.kind == "refuse" else "allow"


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path)
    assert cli(root, "card", "new", "First")[0] == 0  # the owner's terminal: CARD-001, proposed, sealed
    return root


def test_built_in_targets_refuse_edit_tool_writes(task):
    """E8: the built-in targets are closed to edit-tool writes and the profile cannot remove them: the engine copy,
    `mkway.lock`, the profile, the owned hook entries, `locks/` (never open), the bundle `.gitignore` and
    `.gitattributes`, the register and `<state.dir>/`. A path outside them is allowed.
    Catches: a target list that misses one of them, or a profile that empties the list."""
    _set_profile(task, locks={"targets": []})
    rows = [
        ("mkway/engine/engine/dispatch.py", "lock-closed-edit"),
        ("mkway/mkway.lock", "lock-closed-edit"),
        ("mkway/profile.json", "lock-closed-edit"),
        (".claude/settings.json", "lock-closed-edit"),  # MW-027: the committed hook entries
        (".claude/settings.local.json", "lock-closed-edit"),
        ("mkway/.gitignore", "lock-closed-edit"),
        ("mkway/.gitattributes", "lock-closed-edit"),
        ("mkway/cards/REGISTER.md", "lock-closed-edit"),
        ("mkway/state/records.jsonl", "lock-closed-edit"),
        ("mkway/state/register.sha", "lock-closed-edit"),
        ("mkway/locks/x.json", "lock-file-by-session"),
        (str(task / "mkway" / "profile.json"), "lock-closed-edit"),
        ("src/a.py", "allow"),
        ("mkway/cards/CARD-001-first/CARD.md", "allow"),
    ]
    for path, want in rows:
        assert _reason(edit(task, path, tool="Write")) == want, path


def test_forge_shapes_are_refused(task):
    """E9: at least 10 forge shapes are refused: an Edit of a lock file, a redirect, `tee`, `cp`, `python -c`, a
    chained `lock open`, a session's `card set <id> open` and `card set <id> closed`, a reopen from
    `waiting-owner`, PowerShell writes, a forged search record. Catches: any one shape that slips past."""
    register.set_status(task, _profile(task), "CARD-001", "waiting-owner")
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    rows = [
        ("edit", "mkway/locks/x.json", "lock-file-by-session"),
        ("bash", "echo '{}' > mkway/locks/x.json", "lock-file-by-session"),
        ("bash", "echo x | tee mkway/locks/x.json", "lock-file-by-session"),
        ("bash", "cp a.json mkway/locks/x.json", "lock-file-by-session"),
        ("bash", "python -c \"open('mkway/locks/x.json','w').write('{}')\"", "lock-file-by-session"),
        # changed by MW-003 batch 3 (H4, R54): a chained or wrapped engine call is refused by the exact-form rule first
        ("bash", "git status && python mkway/engine/mkway.py lock open rules", "engine-call-not-plain"),
        ("bash", "python mkway/engine/mkway.py card set CARD-001 open", "owner-only-command"),
        ("bash", "python mkway/engine/mkway.py card set CARD-001 closed", "owner-only-command"),
        ("bash", "echo '{\"kind\": \"search\"}' >> mkway/state/records.jsonl", "lock-closed-shell"),
        ("bash", "sed -i 's/proposed/open/' mkway/cards/REGISTER.md", "lock-closed-shell"),
        ("bash", "python -c \"import runpy; runpy.run_path('mkway/engine/mkway.py')\"", "lock-closed-shell"),
        # changed by MW-003 list item 5 (R43: the forge shapes name a lock file and stay refused; an unparsed command
        # that names none is logged, not refused)
        ("bash", 'echo "unbalanced > mkway/mkway.lock', "lock-closed-shell"),
        ("ps", "Set-Content mkway\\cards\\REGISTER.md x", "lock-closed-shell"),
        ("ps", "& python .\\mkway\\engine\\mkway.py lock open rules", "engine-call-not-plain"),
    ]
    for kind, text, want in rows:
        if kind == "edit":
            got = edit(task, text)
        else:
            got = shell(task, text, tool="PowerShell" if kind == "ps" else "Bash")
        assert _reason(got) == want, text


def test_owner_only_commands_in_any_spelling(task):
    """E10: a session's call of `lock open`, `lock close`, `gate off`, `install`, `upgrade`, `card open`,
    `card close`, `card resync`, `card set` to a status in `cards.owner_moves`, and `card release` with `--force`
    in any position or form is refused (`owner-only-command`); its message names the owner's terminal. Other card
    commands pass the gate. Catches: an owner move that a session can run by a new spelling."""
    p = "python mkway/engine/mkway.py"
    refused = [
        f"{p} lock open rules", f"{p} lock close rules", f"{p} gate off lock", f"{p} install --from x",
        f"{p} upgrade", f"{p} card open CARD-001", f"{p} card close CARD-001", f"{p} card resync",
        f"{p} card set CARD-001 closed", f"{p} card release CARD-001 --force", f"{p} card release --force CARD-001",
        f"{p} card release CARD-001 --force=yes", f"py -3 mkway/engine/mkway.py card open CARD-001",
        f"cd mkway/engine && python mkway.py card close CARD-001",
    ]
    for cmd in refused:
        v = shell(task, cmd)
        assert _reason(v) == "owner-only-command", cmd
        assert "terminal" in v.message
    # changed by the MW-003 close check (M2): a session pauses only the card it holds, so s1 holds CARD-001 here
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    allowed = [f"{p} card list", f"{p} card new Second", f"{p} card take CARD-001",
               f"{p} card set CARD-001 waiting", f"{p} search words", f"{p} check", "git status",
               "python -m pytest -q"]
    for cmd in allowed:
        assert _reason(shell(task, cmd)) == "allow", cmd


def test_light_mode_lets_card_moves_through(task):
    """E10: with `cards.owner_moves: []` (the light mode) `card open`, `card close` and `card set` pass the gate;
    `lock open`, `gate off`, `install`, `card resync` and `card release --force` stay the owner's.
    Catches: a light mode that opens every owner command."""
    _set_profile(task, cards={"owner_moves": []})
    p = "python mkway/engine/mkway.py"
    for cmd in (f"{p} card open CARD-001", f"{p} card close CARD-001", f"{p} card set CARD-001 open"):
        assert _reason(shell(task, cmd)) == "allow", cmd
    for cmd in (f"{p} lock open rules", f"{p} gate off lock", f"{p} install --from x", f"{p} card resync",
                f"{p} card release CARD-001 --force"):
        assert _reason(shell(task, cmd)) == "owner-only-command", cmd


def test_holder_reopens_only_from_waiting(task):
    """E11 (R19c): the holding session's `card set <id> open` passes only when the sealed register says `waiting`;
    another session, a session with no take record, and a reopen from `waiting-owner` are refused
    (`owner-only-command`). Catches: a reopen open to any session, or one that reads the status from the card."""
    p = "python mkway/engine/mkway.py card set CARD-001 open"
    state = task / "mkway" / "state"
    register.set_status(task, _profile(task), "CARD-001", "waiting")
    assert _reason(shell(task, p, session="s1")) == "owner-only-command"  # no holder record: fail closed
    records.append(state, "s1", "take", "CARD-001")
    assert _reason(shell(task, p, session="s1")) == "allow"
    assert _reason(shell(task, p, session="s2")) == "owner-only-command"
    register.set_status(task, _profile(task), "CARD-001", "waiting-owner")
    assert _reason(shell(task, p, session="s1")) == "owner-only-command"


def test_one_card_per_session_and_release(task):
    """E12 (R15 A2; v3.1): `card take` is refused while this session holds a card that is not closed
    (`session-has-card`); a card another session holds cannot be taken or released (`card-not-yours`), and the
    message names the owner's `card release <id> --force`; a release of a card no one holds passes the gate.
    Catches: a second card per session, or a release of someone else's card."""
    assert cli(task, "card", "new", "Second")[0] == 0
    state = task / "mkway" / "state"
    p = "python mkway/engine/mkway.py card"
    records.append(state, "s1", "take", "CARD-001")
    assert _reason(shell(task, f"{p} take CARD-002", session="s1")) == "session-has-card"
    v = shell(task, f"{p} release CARD-001", session="s2")
    assert _reason(v) == "card-not-yours" and "--force" in v.message
    assert _reason(shell(task, f"{p} take CARD-001", session="s2")) == "card-not-yours"
    assert _reason(shell(task, f"{p} release CARD-002", session="s2")) == "allow"
    register.set_status(task, _profile(task), "CARD-001", "closed")
    assert _reason(shell(task, f"{p} take CARD-002", session="s1")) == "allow"
    records.append(state, None, "release", "CARD-001", by="owner")
    assert _reason(shell(task, f"{p} take CARD-001", session="s2")) == "allow"


def test_profile_targets_open_and_expire(task):
    """E13: a profile target (`locks.targets[]`, a name and paths or globs) is closed unless its lock file is open
    and not expired; the owner's `mkway lock open <name>` opens it; every refusal quotes the path and the lock
    name; a target in a user home folder is off. Catches: a lock that never expires, a match by base name, or a
    refusal that does not say which lock."""
    _set_profile(task, locks={"targets": [{"name": "rules", "paths": ["rules/**", "conf/x.json"]},
                                          {"name": "home", "paths": ["~/.secret"]}]})
    v = edit(task, "rules/a.md")
    assert _reason(v) == "lock-closed-edit" and "rules/a.md" in v.message and "rules" in v.message
    assert _reason(edit(task, "other/rules/a.md")) == "allow"
    assert _reason(edit(task, "x.json")) == "allow"
    assert _reason(shell(task, "echo 1 > conf/x.json")) == "lock-closed-shell"
    code, out, err = cli(task, "lock", "open", "rules", "--minutes", "5")
    assert code == 0, err
    marker = task / "mkway" / "state" / "locks" / "rules.json"  # changed by MW-022 (E1): the shared folder
    lock = json.loads(marker.read_text(encoding="utf-8"))
    assert lock["name"] == "rules" and lock["state"] == "open" and lock["until"] and lock["opened_at"]
    assert _reason(edit(task, "rules/a.md")) == "allow"
    lock["until"] = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
    marker.write_text(json.dumps(lock), encoding="utf-8")
    assert _reason(edit(task, "rules/a.md")) == "lock-closed-edit"
    assert cli(task, "lock", "open", "locks")[0] != 0  # `locks/` is never open
    assert cli(task, "lock", "open", "nosuch")[0] != 0


def test_register_seal_refuses_a_tampered_register(task):
    """E14 (R19a): every engine write of the register first checks its sha256 against `<state.dir>/register.sha`;
    on a difference it refuses (`register-tampered`) and changes nothing; the lock gate's register read refuses
    too. `card resync` (the owner's) prints the diff against `register.last` and rewrites the seal. The register
    is written with `\\n` line ends. Catches: a seal that is not checked before a write, or a resync that skips
    the diff."""
    reg = task / "mkway" / "cards" / "REGISTER.md"
    assert b"\r\n" not in reg.read_bytes()
    reg.write_bytes(reg.read_bytes().replace(b"proposed", b"open"))
    before = reg.read_bytes()
    code, out, err = cli(task, "card", "new", "Second")
    assert code != 0 and "register-tampered" in (out + err)
    assert reg.read_bytes() == before
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    assert _reason(shell(task, "python mkway/engine/mkway.py card set CARD-001 open")) == "register-tampered"
    code, out, err = cli(task, "card", "resync")
    assert code == 0, err
    assert "-| CARD-001" in out and "+| CARD-001" in out
    assert cli(task, "card", "new", "Second")[0] == 0


def test_one_writer_at_a_time(task):
    """E15 (R19c): two writers each add one row; both rows are present. A writer whose lock was taken over refuses
    (`register-busy`) and changes nothing. A lock older than 30 s is stale and is taken over.
    Catches: a second writer that drops the first one's row under a seal that still matches."""
    import cardtool
    errors = []
    profile = _profile(task)

    def add(title):
        try:
            cardtool.new_card(task, profile, title)
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=add, args=(t,)) for t in ("Alpha", "Beta")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    text = (task / "mkway" / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert "Alpha" in text and "Beta" in text
    profile = _profile(task)
    lock = task / "mkway" / "state" / "register.lock"

    def steal():
        lock.write_text("someone-else", encoding="utf-8")

    reg = task / "mkway" / "cards" / "REGISTER.md"
    before = reg.read_bytes()
    with pytest.raises(register.RegisterError) as info:
        register.write(task, profile, lambda rows: rows, _before_replace=steal)
    assert info.value.reason == "register-busy"
    assert reg.read_bytes() == before
    lock.write_text("stale", encoding="utf-8")
    old = time.time() - 60
    os.utime(lock, (old, old))
    register.set_status(task, profile, "CARD-001", "open")
    assert "| open |" in reg.read_text(encoding="utf-8")


def _git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


@pytest.fixture
def gtask(tmp_path):
    root = task_root(tmp_path, vcs="git", name="gtask")
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    _git(root, "init", "-q")
    assert cli(root, "card", "new", "First")[0] == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "start")
    return root


def test_commit_of_closed_targets_and_the_register(gtask):
    """E16 (R19a): a commit that touches a closed target is refused (`lock-closed-commit`); a commit that holds the
    register passes only when the working-tree register's sha256 equals `register.sha`; with `-i` the staged
    register counts too; a missing `register.sha` refuses. Catches: a register commit that skips the seal, or a
    staged forgery behind a restored working tree."""
    reg = "mkway/cards/REGISTER.md"
    c = "git commit -m 'CARD-001 x' -- "
    assert _reason(shell(gtask, c + "mkway/profile.json")) == "lock-closed-commit"
    assert _reason(shell(gtask, c + "src/a.py")) == "allow"
    assert cli(gtask, "card", "new", "Second")[0] == 0
    assert _reason(shell(gtask, c + reg)) == "allow"
    path = gtask / reg
    good = path.read_bytes()
    path.write_bytes(good.replace(b"proposed", b"open", 1))
    _git(gtask, "add", reg)
    path.write_bytes(good)
    assert _reason(shell(gtask, c + reg)) == "allow"
    assert _reason(shell(gtask, "git commit -i -m 'CARD-001 x' -- " + reg)) == "lock-closed-commit"
    _git(gtask, "reset", "-q", "--", reg)
    (gtask / "mkway" / "state" / "register.sha").unlink()
    assert _reason(shell(gtask, c + reg)) == "lock-closed-commit"


def test_lock_gate_runs_in_both_groups(task):
    """E17 (decision 1): the lock gate has two manifest entries, `edit` and `shell`, on one function; the
    dispatcher refuses through either and writes one row each. Catches: a gate wired into one group only."""
    import dispatch
    entries = [e for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e.get("gate") == "lock"]
    assert sorted((e["group"], e["function"]) for e in entries) == [("edit", "gate_lock:check"),
                                                                     ("shell", "gate_lock:check")]
    env = {"CLAUDE_PROJECT_DIR": str(task)}
    for group, tool, tin in (("edit", "Edit", {"file_path": "mkway/profile.json"}),
                             ("shell", "Bash", {"command": "echo x > mkway/profile.json"})):
        payload = {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tin}
        res = dispatch.run("PreToolUse", group, json.dumps(payload), env=env)
        assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny", group
    rows = jsonl(task / "mkway" / "state" / "refusals.jsonl")
    assert [(r["gate"], r["reason_id"]) for r in rows] == [("lock.edit", "lock-closed-edit"),
                                                           ("lock.shell", "lock-closed-shell")]


def test_start_line_lists_open_locks(task):
    """E18: the start line lists the open locks and their end times (lock_notice joins the start line).
    Catches: a start line that counts lock files only."""
    import startline
    _set_profile(task, locks={"targets": [{"name": "rules", "paths": ["rules/**"]}]})
    cli(task, "lock", "open", "rules", "--minutes", "5")
    profile = _profile(task)
    text = startline.render(task, task / "mkway" / "profile.json", profile, [], [], {}, session="s1")
    (line,) = [x for x in text.splitlines() if x.startswith("locks:")]
    lock = json.loads((task / "mkway" / "state" / "locks" / "rules.json").read_text(encoding="utf-8"))  # MW-022 (E1)
    assert "rules open until " + lock["until"] in line
