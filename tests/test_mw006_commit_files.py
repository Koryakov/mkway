"""Commit checks (card MW-006), part 3: the commit gate's rules «right files only» and «own changes only», the files
each commit form takes, staging in the commit's own command, and the fail-closed reads. Synthetic task roots only,
real throwaway git repositories; the gate is called with the dispatcher's own context."""
import json
import subprocess

from _commit_fixture import COMMIT, check, git, make_task, reason, save, stage, touch, work
from _engine import task_root
import register
import runner


def _known(root, *rels):
    """Files the session wrote (recorded) and staged."""
    for rel in rels:
        work(root, rel)
    touch(root, *rels)
    stage(root, *rels)


def test_a_staged_file_outside_the_card_paths_is_refused(tmp_path):
    """E7 (part 3): every staged file must lie inside the open card's Paths; a file outside is refused
    `file-not-in-card`, and the text lists each such file (not the files that are inside), the card, its Paths and the
    ways out. Catches: a commit that takes files the card was never opened for, or a refusal that names no file."""
    root = make_task(tmp_path)
    _known(root, "src/a.py", "lib/a.py", "other/b.py", "docs/c.md")
    v = check(root, COMMIT)
    assert v.kind == "refuse" and v.reason_id == "file-not-in-card"
    assert v.message.split(" are not in")[0] == "docs/c.md, other/b.py"  # the files outside, and only those
    assert "CARD-001" in v.message and "(lib/a.py; src)" in v.message and "git restore --staged" in v.message
    git(root, "restore", "--staged", "--", "other/b.py", "docs/c.md")
    assert reason(check(root, COMMIT)) == "allow"
    many = [f"extra/f{i}.py" for i in range(12)]
    _known(root, *many)
    v = check(root, COMMIT)
    assert v.reason_id == "file-not-in-card" and "and 4 more" in v.message


def test_always_allowed_files_and_empty_paths_pass(tmp_path):
    """E8 (part 3): the card's own folder, the register, the ledger folder and the profile's `paths.exempt` pass
    whatever the Paths say; an empty Paths is no file rule; a session with no open card (none taken, or the card
    is not open) may commit only those. Catches: a commit of the card's own file that its own gate refuses, an
    empty Paths that blocks everything, or a session with no card that commits any file."""
    root = make_task(tmp_path, card_paths="`src/`", paths={"exempt": ["notes/**"]})
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    register.write(root, profile, lambda rows: [dict(r, title="First, renamed") for r in rows])  # a sealed change
    always = ["mkway/cards/CARD-001-first/CARD.md", "mkway/ledger/rows.md", "notes/n.md"]
    for rel in always:
        work(root, rel, "changed\n")
    stage(root, "mkway/cards/REGISTER.md", *always)
    assert reason(check(root, COMMIT)) == "allow"  # never recorded as written: the always-allowed set is exempt
    work(root, "src/a.py")
    stage(root, "src/a.py")
    assert reason(check(root, COMMIT, session="s2")) == "file-not-in-card"  # s2 holds no card
    v = check(root, COMMIT, session="s2")
    assert "src/a.py" in v.message and "no open card" in v.message
    assert "mkway/cards/CARD-001-first/CARD.md" in v.message  # the folder of a card s2 does not hold is not its own
    git(root, "restore", "--staged", "--", "src/a.py", "mkway/cards/CARD-001-first/CARD.md")
    assert reason(check(root, COMMIT, session="s2")) == "allow"  # the register, the ledger and the exempt path pass
    register.set_status(root, profile, "CARD-001", "waiting")
    stage(root, "src/a.py")
    touch(root, "src/a.py")
    v = check(root, COMMIT)
    assert v.reason_id == "file-not-in-card" and "waiting" in v.message  # a card that is not open

    free = make_task(tmp_path, card_paths="", name="free")
    _known(free, "anything/at/all.py")
    assert reason(check(free, COMMIT)) == "allow"


def test_every_commit_form_reads_the_files_it_would_stage(tmp_path):
    """E9 (part 3): `-- <paths>` takes only the named files (another file staged beside them is not in this
    commit); no paths takes the staged files; `-a` takes the tracked changes too; `-i` takes the staged files and the
    named ones; `--amend` takes the index. Each is judged on exactly those files. Catches: a gate that reads only the
    index, or one that refuses a staged file the command would leave out."""
    root = make_task(tmp_path)
    save(root, "other/t.py", "old\n")
    _known(root, "src/a.py", "other/b.py")
    paths_form = "git commit -m 'CARD-001 x' -- "
    assert reason(check(root, paths_form + "src/a.py")) == "allow"
    v = check(root, paths_form + "src/a.py other/b.py")
    assert v.reason_id == "file-not-in-card" and "other/b.py" in v.message and "src/a.py" not in v.message
    assert "`--`" in v.message  # the way out for a named path: leave it out of the paths
    assert check(root, COMMIT).reason_id == "file-not-in-card"  # the index holds other/b.py
    assert check(root, "git commit -i -m 'CARD-001 x' -- src/a.py").reason_id == "file-not-in-card"
    assert check(root, "git commit --amend -m 'CARD-001 x'").reason_id == "file-not-in-card"
    git(root, "restore", "--staged", "--", "other/b.py")
    assert reason(check(root, COMMIT)) == "allow"
    assert reason(check(root, "git commit -i -m 'CARD-001 x' -- src/a.py")) == "allow"
    assert reason(check(root, "git commit --amend -m 'CARD-001 x'")) == "allow"
    work(root, "other/t.py", "new\n")  # a tracked change, not staged
    touch(root, "other/t.py")
    assert reason(check(root, COMMIT)) == "allow"  # not in this commit
    v = check(root, "git commit -a -m 'CARD-001 x'")
    assert v.reason_id == "file-not-in-card" and "other/t.py" in v.message and "-a" in v.message


def test_a_staged_file_the_session_never_touched_is_a_ride_in(tmp_path):
    """E10 (part 3): a staged file the session did not write (no edit-tool row, no shell-write row) is a ride-in:
    `ride-in-file`, naming it, with `git restore --staged <file>`; a file written through an edit tool, a shell
    write, a glob or a deleting command passes; a staged deletion the session did not make is a ride-in too.
    Catches: another session's work swept into this session's commit."""
    root = make_task(tmp_path, card_paths="`src/`")
    save(root, "src/old.py")
    save(root, "src/theirs_old.py")
    work(root, "src/mine.py")
    work(root, "src/other_session.py")
    work(root, "src/glob1.txt")
    work(root, "src/glob2.txt")
    stage(root, "src/mine.py", "src/other_session.py", "src/glob1.txt", "src/glob2.txt")
    git(root, "rm", "-q", "--", "src/old.py", "src/theirs_old.py")
    touch(root, "src/mine.py")
    from _engine import gate_call
    import gate_commit
    gate_call(gate_commit.touch, root, tool="Bash", tool_input={"command": "rm src/old.py"})
    gate_call(gate_commit.touch, root, tool="Bash", tool_input={"command": "touch src/glob*.txt"})
    v = check(root, COMMIT)
    assert v.kind == "refuse" and v.reason_id == "ride-in-file"
    assert "src/other_session.py" in v.message and "src/theirs_old.py" in v.message
    for fine in ("src/mine.py", "src/old.py", "src/glob1.txt", "src/glob2.txt"):
        assert fine not in v.message, fine
    assert "git restore --staged src/other_session.py src/theirs_old.py" in v.message
    git(root, "restore", "--staged", "--", "src/other_session.py", "src/theirs_old.py")
    assert reason(check(root, COMMIT)) == "allow"
    stage(root, "src/other_session.py")
    v = check(root, "git commit -a -m 'CARD-001 x'")
    assert v.reason_id == "ride-in-file" and "-a" in v.message  # under -a the way out is no -a


def test_touch_by_another_session_does_not_count_and_unresolved_does(tmp_path):
    """E11 (part 3): another session's record does not make a file this session's; a shell write this session made
    that the gate could not read counts every file as touched (the gate cannot tell which file it wrote).
    Catches: a record shared across sessions, or an unreadable write that is read as no write."""
    root = make_task(tmp_path, card_paths="`src/`")
    work(root, "src/x.py")
    stage(root, "src/x.py")
    touch(root, "src/x.py", session="s2")
    assert check(root, COMMIT).reason_id == "ride-in-file"
    from _engine import gate_call
    import gate_commit
    gate_call(gate_commit.touch, root, tool="Bash", tool_input={"command": "echo y > $TARGET"})
    assert reason(check(root, COMMIT)) == "allow"
    assert check(root, COMMIT, session="s3").reason_id == "file-not-in-card"  # no card: rule 1 still holds


def test_staging_in_the_same_command_is_refused(tmp_path):
    """E12 (part 3): the hook reads the index before the command runs, so a commit in a command that also stages or
    unstages (`git add`, `git rm`, `git restore`, `git reset`, `git mv`, ...) cannot be checked: refused
    `commit-unreadable`, naming the way out (stage in a call of its own, then commit alone); a read-only git call
    beside the commit is fine. Catches: `git add -f data.csv && git commit`, which passes any check of the index."""
    root = make_task(tmp_path)
    _known(root, "src/a.py")
    for command in ("git add src/b.py && " + COMMIT, "git add -f src/b.py; " + COMMIT,
                    "git rm -q src/a.py && " + COMMIT, "git restore --staged src/a.py && " + COMMIT,
                    "git reset -q && " + COMMIT, "git mv src/a.py src/c.py && " + COMMIT,
                    COMMIT + " && git add -A", "git add . ; " + COMMIT):
        v = check(root, command)
        assert v.kind == "refuse" and v.reason_id == "commit-unreadable", command
        assert "call of its own" in v.message, command
    v = check(root, "git add src/b.py ; " + COMMIT, tool="PowerShell")
    assert v.reason_id == "commit-unreadable"
    for command in ("git status && " + COMMIT, COMMIT + " && git log --oneline -1",
                    "git diff --cached --stat && " + COMMIT + " && git show --stat HEAD"):
        assert reason(check(root, command)) == "allow", command
    assert reason(check(root, COMMIT, tool="PowerShell")) == "allow"


def test_unreadable_commits_fail_closed_and_other_commands_pass(tmp_path, monkeypatch):
    """E13 (part 3): a commit the gate cannot read refuses `commit-unreadable` (a folder from a variable, a carried
    command, an option it does not know, a command that does not parse, a git read that fails or times out) and a
    tampered register refuses `register-tampered`; with `vcs: none`, and for a command that is no commit (a status, a
    log that greps for the word, an echo, a test run), the gate allows. Catches: an integrity gate that allows when
    it cannot see."""
    root = make_task(tmp_path)
    _known(root, "src/a.py")
    for command in ("cd $WHERE && " + COMMIT, "bash -c \"" + COMMIT + "\"", "git commit --inc -m 'CARD-001 x'",
                    "git commit --pathspec-from-file=list.txt -m 'CARD-001 x'", "git commit -m 'CARD-001 x",
                    "git -c alias.ci=commit ci -m x"):
        v = check(root, command)
        assert v.kind == "refuse" and v.reason_id == "commit-unreadable", command
        assert v.message.strip(), command
    for command in ("git status", "git log --grep commit", "echo done", "python -m pytest", "ls -la", ""):
        assert reason(check(root, command)) == "allow", command
    assert reason(check(root, "git commit", tool="Read")) == "allow"  # not a shell tool

    def boom(*_a, **_k):
        raise runner.TimeoutExpired("git", 10)
    monkeypatch.setattr(runner, "git", boom)
    v = check(root, COMMIT)
    assert v.reason_id == "commit-unreadable" and "run it again" in v.message
    monkeypatch.undo()

    def no_repository(*_a, **_k):  # git's own answer in a folder with no repository
        return subprocess.CompletedProcess([], 128, "", "fatal: not a git repository")
    monkeypatch.setattr(runner, "git", no_repository)
    assert check(root, COMMIT).reason_id == "commit-unreadable"
    monkeypatch.undo()
    none = task_root(tmp_path, vcs="none", name="none")
    assert reason(check(none, COMMIT)) == "allow"

    reg = root / "mkway" / "cards" / "REGISTER.md"
    reg.write_bytes(reg.read_bytes() + b"\n")
    v = check(root, COMMIT)
    assert v.reason_id == "register-tampered" and "card resync" in v.message
