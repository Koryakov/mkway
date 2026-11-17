"""The lock gate, the owner-only commands and the register seal (card MW-003, deliverable 3; spec section 1,
L1-L8; R18, R19a, R19c). Synthetic task roots only; gates are called with the dispatcher's own context.
The lock DECISION cases moved to `tests/core/test_lock_decide.py` and `tests/shell/test_lock_facts.py` (MW-063; see
`cards/MW-063-lock-core/case_map.md`); what stays here is the register seal, the one-writer case, the start line, and
the helpers other modules import."""
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
