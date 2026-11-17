"""The fix-round list of card MW-003 (rulings R37, R43, R44, R45; the list order's item numbers). Synthetic task roots
only."""
import json
import os

import pytest

from test_dispatch import REFUSE, _payload, refusals, run, task  # noqa: F401  (task is a fixture)
from test_lock import _git, _reason, _set_profile, gtask, shell  # noqa: F401  (gtask is a fixture)
from _engine import cli, entry, gate_call, make_profile, task_root, write_profile
import helpers
import logs
import startline


def _broken(root):
    broken = make_profile()
    broken["bundle"]["root"] = "../outside"
    write_profile(root, broken)


def test_invalid_profile_refuses_every_edit_and_shell_call(task):
    """Item 1 (R37 (a) H1, fail closed): with an invalid profile every `edit` and `shell` call is refused
    `profile-invalid` with the validator's message (the broken key), on every call, not once per session; no gate runs
    with defaults. Catches: a typo in the profile that silently drops the task's own lock targets."""
    _broken(task)
    for group, tool, tool_input in (("edit", "Edit", None), ("edit", "Edit", None),
                                    ("shell", "Bash", {"command": "echo x > a.txt"})):
        res = run(task, "PreToolUse", group, [], payload=_payload(tool=tool, tool_input=tool_input))
        out = json.loads(res.stdout)["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny", group
        assert "profile-invalid" in out["permissionDecisionReason"] and "bundle.root" in out["permissionDecisionReason"]
    assert [(r["reason_id"], r["kind"]) for r in refusals(task)] == [("profile-invalid", "refuse")] * 3


def test_invalid_profile_is_a_log_row_in_the_other_groups(task):
    """Item 1 (R37 (a) H1): the non-blocking groups block nothing and write a `log` row (once per session and profile
    content). Catches: a `post` or `prompt` hook that blocks, or stays silent, on a broken profile."""
    _broken(task)
    for event, group in (("PostToolUse", "post"), ("UserPromptSubmit", "prompt")):
        res = run(task, event, group, [], payload=_payload(event))
        assert res.exit_code == 0 and "decision" not in res.stdout, group
    assert [(r["reason_id"], r["kind"]) for r in refusals(task)] == [("profile-invalid", "log")] * 2


def test_start_line_says_edit_and_shell_are_refused(task):
    """Item 1 (R37 (a) H1; startline correction): the start line's `profile-invalid` line says every edit and shell
    call is refused until the owner fixes the profile. Catches: a start line that still promises «nothing is
    blocked»."""
    _broken(task)
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    text = startline.render(task, task / "mkway" / "profile.json", profile, ["bundle.root: leaves the root"], [],
                            {"CLAUDECODE": "1"})
    (line,) = [x for x in text.splitlines() if x.startswith("profile-invalid")]
    assert "every edit and shell call is refused" in line and "never stopped" not in line


BUNDLE_ERROR = "bundle.root: not a relative path inside the repository"


def test_gate_switch_never_writes_a_profile_that_fails_the_schema(task):
    """Item 1 (R64): `mkway gate off|on` checks its result against the schema before `os.replace`; a result with an
    error is refused with the key path and the message, and the profile file is left byte for byte. Catches: an
    engine writer that turns a broken profile into a still-broken one, or hides which key to fix."""
    _broken(task)
    before = (task / "mkway" / "profile.json").read_bytes()
    code, _out, err = cli(task, "gate", "off", "lock")
    assert code != 0 and BUNDLE_ERROR in err
    assert (task / "mkway" / "profile.json").read_bytes() == before


def test_install_checks_the_starter_profile_before_it_is_written(tmp_path, monkeypatch):
    """Item 1 (R64): install validates the starter profile before it replaces the file; a starter with a schema error
    is refused with the key path and the message, and no profile file is written. Catches: install writing a profile
    the dispatcher then refuses on every call."""
    import install
    import core_install  # decision MW-067: plan_profile moved to core_install and reads its own starter_profile
    from test_install import make_source, make_task
    src = make_source(tmp_path, vcs="none")
    root = make_task(tmp_path, vcs="none")
    monkeypatch.setattr(core_install, "starter_profile", lambda vcs: dict(make_profile(), vcs="bogus"))
    with pytest.raises(install.InstallError) as caught:
        install.install(root, src)
    assert "vcs: not one of git, none" in str(caught.value)
    assert not (root / "mkway" / "profile.json").exists()


def test_check_prints_the_profile_error(task):
    """Item 1 (R64; KEYS.md decided line): `mkway check` prints the same schema error the refusal carries (key path
    and message) and is not green. Catches: a check that reports a broken profile as fine."""
    import install
    _broken(task)
    (task / "mkway" / "engine" / "tests").mkdir(parents=True)  # an empty copy: the check's test run ends at once
    env = {k: v for k, v in os.environ.items() if k != "ENGINE_TERMS_FILE"}  # no term scan of the empty copy
    code, lines = install.check(task, env=env)
    assert code != 0
    assert any(line.startswith("profile: invalid") and BUNDLE_ERROR in line for line in lines)


C = "git commit -m 'CARD-001 x' -- "


REG = "mkway/cards/REGISTER.md"


def _root_below_top(tmp_path):
    """A task root one folder below its git top (`<top>/task`), with CARD-001 sealed and committed."""
    top = tmp_path / "top"
    top.mkdir()
    _git(top, "init", "-q")
    root = task_root(top, vcs="git", name="task")
    (root / "mkway" / ".gitignore").write_text("engine/\nlocks/\nstate/\n", encoding="utf-8")
    assert cli(root, "card", "new", "First")[0] == 0
    _git(top, "add", "-A")
    _git(top, "commit", "-q", "-m", "start")
    return root


def test_install_seal_reads_head_from_the_root_folder(tmp_path):
    """Item 3 (R37 (a) M2): install's seal compares the register with `HEAD:./<rel>`, read from the root, so a root
    below its git top is sealed when the register equals HEAD's blob. Catches: `HEAD:<rel>` read from the git top,
    which leaves every such root without a seal."""
    import install
    from test_install import make_source
    src = make_source(tmp_path, vcs="none")
    root = _root_below_top(tmp_path)
    install.install(root, src, vcs="git")
    sha = root / "mkway" / "state" / "register.sha"
    sha.unlink()
    report = install.install(root, src, vcs="git")
    assert "register: sealed" in report and sha.is_file()


def test_everywhere_carries_a_reason():
    """Item 5 (R43 point 1): `Writes.everywhere` carries a reason: `unparsed` (the shell text or the Python body does
    not parse) or `capable` (a risky module, a write call with a computed path, a program with no readable targets).
    Catches: one undifferentiated «everywhere» that the lock gate can only refuse."""
    rows = [('echo "unterminated', "unparsed"), ('python -c "x("', "unparsed"),
            ('python -c "import subprocess"', "capable"), ("find . -name '*.pyc' -delete", "capable"),
            ("ls | xargs -n1 echo", "capable"), ("echo x > src/a.txt", None)]
    for command, want in rows:
        w = helpers.shell_writes(command, "bash")
        assert (w.reason if w.everywhere else None) == want, command


def _kind(v):
    return v.reason_id if v.kind == "refuse" else v.kind


MUST_PASS = [  # real command shapes (synthetic paths) the lock gate must never refuse
    "python -m pytest -q",
    'python -c "import subprocess; subprocess.run([\'python\', \'-m\', \'pytest\'])"',
    "find . -name '*.pyc' -delete",
    "ls src | xargs -n1 echo",
    "git switch -c feature",
    "git stash list",
    "perl -pi -e 's/a/b/' src/a.txt",
    'echo x > "$OUT"',
    "rm -rf build/*",
    'for f in src/*.py; do python -m py_compile "$f"; done',
    "python - <<'EOF'\nimport json\nprint(json.dumps({}))\nEOF",
    'cd src && python -c "import os; os.remove(name)"',
]


def test_must_pass_table_of_real_shapes(gtask):
    """Item 5 (R43 point 1): the must-pass table of real shapes; none is refused. Catches: a literal-reach rule so
    wide that everyday commands block again."""
    for command in MUST_PASS:
        assert shell(gtask, command).kind != "refuse", command


def test_a_log_verdict_writes_a_row_and_shows_nothing(task):
    """Item 5 (R43 (c)): a gate's `log` verdict writes a `log` row and blocks nothing; nothing is shown to the
    session at that call. Catches: a `log` verdict shown as a warn on every unread command."""
    logged = entry("l1", "fixture_gates:always_log", group="shell", reason_ids=["fixture-log"])
    res = run(task, "PreToolUse", "shell", [logged], payload=_payload(tool="Bash", tool_input={"command": "x"}))
    assert res.exit_code == 0 and res.stdout == ""
    assert [(r["reason_id"], r["kind"]) for r in refusals(task)] == [("fixture-log", "log")]


def _unresolved_row(root, session):
    logs.write_refusal(root / "mkway" / "state", logs.row(session=session, event="PreToolUse", tool="Bash",
                                                          gate="lock.shell", reason_id="write-target-unresolved",
                                                          target="x", kind="log"))


def test_unresolved_writes_are_reminded_at_the_next_prompt(task):
    """Item 5 (R43 (c)): at the next prompt the session is reminded how many of its commands had write targets
    that could not be read, once per row; another session's rows are not counted. Catches: a `log` row nobody
    ever sees."""
    for session in ("s1", "s1", "s2"):
        _unresolved_row(task, session)
    prompt = _payload("UserPromptSubmit", tool=None)
    res = run(task, "UserPromptSubmit", "prompt", None, payload=prompt, manifest="real")  # the real `unresolved` gate
    context = json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "write-target-unresolved" in context and "2 of your shell commands" in context
    assert run(task, "UserPromptSubmit", "prompt", None, payload=prompt, manifest="real").stdout == ""


def test_start_line_counts_unresolved_writes(task):
    """Item 5 (R43 (c)): the start line counts the `write-target-unresolved` rows of the log. Catches: the owner
    never learning how often the lock gate could not read a write."""
    for session in ("s1", "s2", "s3"):
        _unresolved_row(task, session)
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    text = startline.render(task, task / "mkway" / "profile.json", profile, [], [], {"CLAUDECODE": "1"})
    (line,) = [x for x in text.splitlines() if x.startswith("write-target-unresolved")]
    assert "3" in line


def test_parse_ok():
    """Item 7 (R43 point 2): `parse_ok(cmd)` says whether the shell text parses. Catches: a helper that reads an
    unbalanced quote as a command."""
    assert helpers.parse_ok("git commit -m x -- a.py") and helpers.parse_ok("Set-Content a.txt x", "powershell")
    assert not helpers.parse_ok('git commit -m "x -- a.py')


def test_unparsed_command_with_a_commit_is_refused(gtask):
    """Item 7 (R43 point 2): a command whose parse fails and that holds a `git` token followed by a `commit` token is
    refused `command-unparsed`; with no such tokens the commit families stay silent (item 5 decides the writes).
    Catches: `commit_cmd` returning [] on a parse error, so the commit gate sees no commit."""
    for command in ('git commit -m "x -- mkway/profile.json', 'echo "a; git -C src commit -m x -- a.py',
                    "cd src && git commit -m 'x"):
        v = shell(gtask, command)
        assert _kind(v) == "command-unparsed" and "commit" in v.message, command
    assert _kind(shell(gtask, 'echo "unterminated')) == "log"
    assert _kind(shell(gtask, 'echo "commit git')) == "log"  # `commit` before `git`: no commit token pair
    assert _kind(shell(gtask, "git commit -m 'CARD-001 x' -- src/a.py")) == "allow"
    _set_profile(gtask, vcs="none")  # no commit families with vcs none
    assert _kind(shell(gtask, 'git commit -m "x -- src/a.py')) == "log"


PREFIX_ROWS = [
    ("timeout 60 rm -rf mkway", "lock-closed-shell"),
    ("timeout -s KILL -k 5 60 rm -rf mkway", "lock-closed-shell"),
    ("timeout --signal=TERM --preserve-status 1m rm -rf mkway", "lock-closed-shell"),
    ("nice -n 5 rm -rf mkway", "lock-closed-shell"),
    ("nice -5 rm -rf mkway", "lock-closed-shell"),
    ("nice --adjustment=3 rm -rf mkway", "lock-closed-shell"),
    ("env -u HOME rm -rf mkway", "lock-closed-shell"),
    ("env -i PATH=/bin timeout 5 nice rm -rf mkway", "lock-closed-shell"),
    ("timeout 1100 git commit -m 'CARD-001 x' -- mkway/profile.json", "lock-closed-commit"),
    ("nice -n 5 env A=1 git commit -m 'CARD-001 x' -- mkway/profile.json", "lock-closed-commit"),
    ("timeout 60 python -m pytest -q", "allow"),
    ("nice -n 5 rm -rf build", "allow"),
]


def test_timeout_nice_env_prefixes_are_read_through(gtask):
    """Item 8 (R44 row 1): `timeout`, `nice` and `env` prefixes, with their options and values, are read through to
    the command they wrap, for writes and for commits. Catches: `timeout 60 rm -rf mkway` read as the program
    `60`, or a commit behind `timeout 1100` that the commit gate never sees."""
    for command, want in PREFIX_ROWS:
        assert _kind(shell(gtask, command)) == want, command
    (commit,) = helpers.commit_cmd("timeout -k 5 1100 git commit -m x -- a.py")
    assert commit.paths == ["a.py"] and commit.message == "x"


def test_commits_follow_folder_changes(gtask):
    """Item 9 (R44 row 2): a commit's paths are read from the folder it runs in, following `cd`, `pushd`/`popd`,
    `Set-Location` and `git -C` with literal targets (one folder helper with batch 3 H5), from the hook input's `cwd`;
    a `cd` to a variable or an unreadable target refuses the commit. Catches: `cd mkway/cards && git commit --
    REGISTER.md` passing the register seal unseen."""
    import gate_lock
    c = " git commit -m 'CARD-001 x' -- "
    reg = gtask / "mkway" / "cards" / "REGISTER.md"
    good = reg.read_bytes()
    reg.write_bytes(good.replace(b"proposed", b"open", 1))
    v = shell(gtask, "cd mkway/cards &&" + c + "REGISTER.md")
    assert _kind(v) == "lock-closed-commit" and "differs from its seal" in v.message
    reg.write_bytes(good)
    for tool, command in (("Bash", "cd mkway &&" + c + "profile.json"),
                          ("Bash", "pushd mkway;" + c + "profile.json; popd"),
                          ("Bash", "git -C mkway commit -m 'CARD-001 x' -- profile.json"),
                          ("PowerShell", "Set-Location mkway;" + c + "profile.json")):
        v = shell(gtask, command, tool=tool)
        assert _kind(v) == "lock-closed-commit" and "mkway/profile.json" in v.message, command
    for command in ("cd $D &&" + c + "a.py", "cd mkway/$X &&" + c + "a.py", "git -C $D commit -m x -- a.py"):
        v = shell(gtask, command)
        assert _kind(v) == "commit-folder-unreadable", command
    (gtask / "src").mkdir()  # the folder must exist: git cannot run in a missing one, and that refuses (item 2)
    (gtask / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert _kind(shell(gtask, "cd src &&" + c + "a.py")) == "allow"
    assert _kind(shell(gtask, "(cd mkway && make);" + c + "src/a.py")) == "allow"  # the subshell's cd ends
    v = gate_call(gate_lock.check, gtask, tool="Bash", tool_input={"command": c.strip() + " profile.json"},
                  cwd=str(gtask / "mkway"))
    assert _kind(v) == "lock-closed-commit"


def test_git_reads_time_out_at_10_seconds_and_refuse(gtask, monkeypatch):
    """Item 11 (R44 row 4): `runner.git`'s default limit is 10 s; a git read that times out inside the lock gate is
    refused `gate-git-timeout`, never passed and never a crash. Catches: a hung git call that outlasts the hook."""
    import inspect
    import subprocess
    import runner
    assert inspect.signature(runner.git).parameters["timeout"].default == 10

    def hung(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)
    monkeypatch.setattr(runner, "git", hung)
    v = shell(gtask, "git commit -m 'CARD-001 x' -- src/a.py")
    assert _kind(v) == "gate-git-timeout" and "10" in v.message


EXPANSION_ROWS = [  # (command, verdict)
    ("D=mkway; rm -rf $D", "lock-closed-shell"),  # (a) after expansion: the folder holds the targets
    ("F=mkway/profile.json; echo x > $F", "lock-closed-shell"),
    ("export B=mkway; echo x > ${B}/profile.json", "lock-closed-shell"),
    ("A=mkway; B=$A/cards; echo x > $B/REGISTER.md", "lock-closed-shell"),
    ('X=mkway; python -c "import subprocess" ${X}/engine', "lock-closed-shell"),  # literal reach after expansion
    ("B=src; echo x > $B/a.txt", "allow"),
    ("P=mkway; git commit -m 'CARD-001 x' -- $P/profile.json", "lock-closed-commit"),
    ("B=src; git commit -m 'CARD-001 x' -- $B/a.py", "allow"),
    ("git commit -m 'CARD-001 x' -- $UNSET/a.py", "pathspec-unparsed"),
    ("B=x git commit -m 'CARD-001 x' -- $B/a.py", "pathspec-unparsed"),  # a prefix assignment is not in scope
]


def test_literal_variables_are_expanded_in_the_same_command(gtask):
    """Item 12 (R44 row 5): a variable assigned a literal earlier in the same command (a plain assignment or
    `export`) is expanded in later words, redirects and folder changes, before the writes, the literal-reach check
    and the commit paths are read; a commit path still unresolved refuses `pathspec-unparsed`. Catches: 34 of 36
    real refusals of `B=<dir>; ... $B/<file>`, and a variable that hides a lock target from the checks."""
    for command, want in EXPANSION_ROWS:
        assert _kind(shell(gtask, command)) == want, command


def test_replay_case_stays_a_pass(gtask):
    """Item 13 (R44 row 5, the replay case): `B=task/x; timeout 1100 git commit -m "<id> y" -- $B/a.py` passes with
    the checked path `task/x/a.py`; the pair `B=$(pwd)` gives `pathspec-unparsed`. Catches: the expansion missing
    behind a `timeout` prefix, or a computed value read as a literal."""
    row = 'B=task/x; timeout 1100 git commit -m "CARD-001 y" -- $B/a.py'
    (commit,) = helpers.commit_cmd(row)
    assert commit.paths == ["task/x/a.py"]
    assert _kind(shell(gtask, row)) == "allow"
    assert _kind(shell(gtask, row.replace("B=task/x", "B=$(pwd)"))) == "pathspec-unparsed"


def test_one_test_cell_form(tmp_path):
    """Item 14 (R45 points 5 and 6): one Test-cell form: a `; ` list of full node ids, or `checked by reading:
    <path>` with a path that exists, valid on any card. A `,` list, a `::name` continuation and a bare `checked by
    reading` are form faults that say how to write the cell. Also the commit row `(cd sub && make); git commit …
    -- a.py` reads `a.py` from the root. Catches: two cell grammars, and a reading claim that names no file."""
    import cardtool
    from test_cardmoves import set_paths, set_tests
    root = task_root(tmp_path, test_roots=["tests"])
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n\n\ndef test_two(x):\n    pass\n",
                                              encoding="utf-8")
    (root / "README.md").write_text("synthetic\n", encoding="utf-8")
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    set_paths(root, "CARD-001", "`src/a.py`")
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    for cells in (["tests/test_a.py::test_one; tests/test_a.py::test_two[a b-1]"],
                  ["checked by reading: README.md"], ["tests/test_a.py::test_one", "`checked by reading: README.md`"]):
        set_tests(root, "CARD-001", cells)
        assert cardtool.close_problem(root, profile, "CARD-001") is None, cells
    for cell, said in (("tests/test_a.py::test_one, tests/test_a.py::test_two", "`; `"),
                       ("tests/test_a.py::test_one; ::test_two", "full node id"),
                       ("checked by reading", "name the file you read"),
                       ("checked by reading: nofile.md", "does not exist")):
        set_tests(root, "CARD-001", [cell])
        problem = cardtool.close_problem(root, profile, "CARD-001")
        assert problem and said in problem, cell
    (commit,) = helpers.commit_cmd("(cd sub && make); git commit -m x -- a.py")
    assert commit.paths == ["a.py"] and commit.cwd is None and not commit.folder_unreadable
