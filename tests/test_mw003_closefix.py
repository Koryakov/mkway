"""MW-003 close-fix round: the findings of the blind close check on f763cdb, one test per order item. Synthetic
task roots only."""
import pytest

from _engine import cli, task_root

REASON = "run it in your own terminal, not inside a Claude chat"

# Every command the lock gate refuses as `owner-only-command` at f763cdb, with the default `owner_moves`
# (["open", "closed"]). `upgrade` is not a command of mkway.py (argparse refuses it), so it has no row.
OWNER_ONLY = [
    ("lock", "open", "engine"),
    ("lock", "close", "engine"),
    ("gate", "off", "lock"),
    ("gate", "on", "lock"),
    ("install", "--from", "nowhere"),
    ("card", "resync"),
    ("card", "release", "CARD-001", "--force"),
    ("card", "open", "CARD-001"),
    ("card", "close", "CARD-001"),
    ("card", "set", "CARD-001", "open"),
    ("card", "set", "CARD-001", "closed"),
]


@pytest.mark.parametrize("args", OWNER_ONLY, ids=lambda a: "-".join(a))
def test_owner_only_command_refused_inside_a_session(tmp_path, args):
    """Item 1 (A-M5, R37 (a) H4): the CLI itself refused no owner-only command when `CLAUDECODE` was set, so every
    gap in the shell gate's command reading was a full bypass. Now each one exits 1 with the reason line, before it
    does anything."""
    root = task_root(tmp_path)
    code, out, err = cli(root, *args, env={"CLAUDECODE": "1"})
    assert code == 1, (out, err)
    assert REASON in err
    assert not (root / "mkway" / "locks" / "engine.json").exists()


def test_owner_only_command_refused_with_an_empty_variable(tmp_path):
    """Item 1 (A-M5): the variable counts when present with any value, the empty value included."""
    root = task_root(tmp_path)
    code, out, err = cli(root, "lock", "open", "engine", env={"CLAUDECODE": ""})
    assert code == 1, (out, err)
    assert REASON in err
    assert not (root / "mkway" / "locks" / "engine.json").exists()


def test_owner_only_command_runs_without_the_variable(tmp_path):
    """Item 1 (A-M5): the owner's own terminal has no `CLAUDECODE`; the command runs."""
    root = task_root(tmp_path)
    code, out, err = cli(root, "lock", "open", "engine", env={})
    assert code == 0, (out, err)
    assert (root / "mkway" / "locks" / "engine.json").is_file()


def test_light_mode_card_moves_are_not_refused_by_the_cli(tmp_path):
    """Item 1 (A-M5): the same `owner_moves` rule as the lock gate: in light mode (`owner_moves: []`) a session's
    `card open` and `card close` are not owner-only, so the CLI does not refuse them with the reason line."""
    root = task_root(tmp_path, cards={"owner_moves": []})
    for args in (("card", "open", "CARD-001"), ("card", "close", "CARD-001")):
        code, out, err = cli(root, *args, env={"CLAUDECODE": "1"})
        assert REASON not in err, args


from test_lock import gtask, shell  # noqa: E402,F401  (gtask is a fixture)


def _kind(v):
    return v.reason_id if v.kind == "refuse" else v.kind


def test_glob_below_a_folder_target_refuses(gtask):
    """Item 2 (B-H1, B5 (b)): a glob below a folder target (`mkway/engine/*`) matched neither the target's literal nor
    a parent folder, so it was allowed with no log row: a regression from fix-list item 5. A glob whose literal
    folder lies inside a closed target now refuses `lock-closed-shell`; other globs keep their verdict."""
    for command in ("rm -rf mkway/engine/*", "cp evil.py mkway/engine/gate_lock.p?", "tee mkway/locks/* < x"):
        v = shell(gtask, command)
        assert _kind(v) == "lock-closed-shell", command
    assert _kind(shell(gtask, "rm -rf build/*")) == "allow"


CARRIED_DENY = [
    "bash -c 'git commit -m x'",
    'sh -c "git commit -m x -- mkway/profile.json"',
    "cmd /c git commit -m x",
    'pwsh -Command "git commit -m x"',
    "echo x | xargs git commit -m y",
    "bash -c \"g''it commit -m x\"",
    "eval 'git commit -m x'",
    "python -c \"import subprocess; subprocess.run(['git', 'commit', '-m', 'x'])\"",
    "find . -name x -exec git commit -m y ;",
    "script -q -c 'git commit -m x' /dev/null",
    "perl -e 'system(\"git commit -m x\")'",
    "bash -c '$G commit -m x'",
]
CARRIED_ALLOW = [
    "git diff --name-only | xargs git add",
    "find . -name '*.orig' -exec git rm {} +",
    "bash -c 'git stash && pytest -q && git stash pop'",
]


def test_commit_inside_a_carrier_refuses(gtask):
    """Item 3 (B-H5, R83 fail-closed form): `commit_cmd` read no commit inside another program (`bash -c`, `sh -c`,
    `cmd /c`, `pwsh -Command`, `xargs`, `find -exec`, `eval`, `script -c`, an interpreter's `-c`/`-e`), so a staged
    locked file went in with the commit. A carrier whose argument text, with quotes and backslashes removed, holds a
    `git` token (or a `$`/backtick word in its place) followed by `commit` now refuses `command-unparsed`; the inner
    shell is not modelled."""
    for command in CARRIED_DENY:
        assert _kind(shell(gtask, command)) == "command-unparsed", command
    for command in CARRIED_ALLOW:
        assert shell(gtask, command).kind != "refuse", command


ENGINE_TEXT_PASS = [
    'git commit -m "mkway check prints the error" -- README.md',
    'grep -n "mkway card" README.md',
    'git log --grep "mkway lock"',
    "cat > notes.md <<'EOF'\nrun python mkway/engine/mkway.py card take CARD-001 first\nEOF",
]
ENGINE_TEXT_DENY = [
    "for P in mkway/eng; do echo engine | xargs env -u CLAUDECODE python ${P}ine/mkway.py lock open; done",
    "eval 'python mkway/engine/mkway.py lock open engine'",
    "find . -name x -exec python mkway/engine/mkway.py lock open engine ;",
    "cmd /c python mkway/engine/mkway.py lock open engine",
    "python -c \"import os; os.system('python mkway/engine/mkway.py lock open engine')\"",
    "bash <<'EOF'\npython mkway/engine/mkway.py lock open engine\nEOF",
    'echo "unbalanced; python mkway/engine/mkway.py lock open engine',
]


def test_engine_call_found_by_the_parser(gtask):
    """Item 4 (A-M4, P1): the engine-call detector scanned the whole raw text, quoted messages and heredoc bodies
    included, so a commit message, a grep pattern or a note that names `mkway card` was refused
    `engine-call-not-plain` (word-keyed). When the command parses, its engine calls are now found by the parser; the
    free-text scan runs only when the parse fails and on the argument text of the forms the parser does not go into
    (`xargs`, `find -exec`, `eval`, `cmd /c`, an interpreter's `-c`/`-e`, a shell's heredoc), so those are never less
    caught than at f763cdb."""
    import helpers
    for command in ENGINE_TEXT_PASS:
        assert not helpers.holds_engine_call(command, "bash"), command
        assert _kind(shell(gtask, command)) != "engine-call-not-plain", command
    for command in ENGINE_TEXT_DENY:
        assert helpers.holds_engine_call(command, "bash"), command
        assert _kind(shell(gtask, command)) == "engine-call-not-plain", command


def test_named_target_needs_path_boundaries(tmp_path):
    """Item 5 (B-M2 (a), (b); R84): after the R81 fix, `named_target` still matched a target's full literal as a plain
    substring (a one-segment literal `docs` in «see the docs»; `mkway/state` inside `mkway/statement.md`) and an
    undotted file base name (`run`) after a space or a quote. Now the full literal needs a path boundary on both
    sides, and a one-segment literal or an undotted file base name counts only right after a separator."""
    import json
    import locks
    root = task_root(tmp_path, locks={"targets": [{"name": "docs", "paths": ["docs/**/*.md"]},
                                                  {"name": "tool", "paths": ["scripts/run"]}]})
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))

    def hit(text):
        return locks.named_target(root, profile, text)

    for text in ("python -c \"print('see the docs')\"", "cat mkway/statement.md", "echo run it",
                 "python -c \"print('the run')\""):
        assert hit(text) is None, text
    for text in ("X=a; rm -rf $X/docs", 'cp x "$D/scripts/run"', "rm -rf ./docs", "echo x > mkway/state/a",
                 "X=mkway; rm -rf $X/engine", "echo x > mkway/mkway.lock", "cp a 'mkway/profile.json'"):
        assert hit(text) is not None, text


LOCK_JSON = "'{\"name\":\"engine\",\"state\":\"open\",\"until\":\"2099-01-01T00:00:00\"}'"


def test_powershell_parameter_prefixes(gtask):
    """Item 6 (A-H3): PowerShell takes `-L` for `-LiteralPath`, but the reader returned any name under 3 characters
    unchanged and then dropped its value as an unknown parameter's, so a forged lock file was written. Every unique
    prefix now maps to its parameter, 2 characters included; a parameter the reader does not know (or an ambiguous
    prefix) on a writer cmdlet makes the write `everywhere`."""
    import helpers
    for cmdlet in ("Set-Content", "Add-Content"):
        command = f"{cmdlet} -L mkway/locks/engine.json -Value {LOCK_JSON}"
        assert shell(gtask, command, tool="PowerShell").kind == "refuse", command
    command = f"{LOCK_JSON} | Out-File -L mkway/locks/engine.json"
    assert shell(gtask, command, tool="PowerShell").kind == "refuse", command
    assert helpers.shell_writes("Set-Content -L src/a.txt -Value x", "powershell").paths == ["src/a.txt"]
    for command in ("Set-Content -Zork q src/a.txt -Value x", "Set-Content -P src/a.txt -Value x"):
        assert helpers.shell_writes(command, "powershell").everywhere, command
    assert not helpers.shell_writes("Set-Content -Path src/a.txt -Value x -Encoding utf8 -ea Stop",
                                    "powershell").everywhere


def test_env_chdir_and_the_folder_stack(gtask):
    """Item 7 (A-H2, B-H4): `env -C`/`--chdir` was skipped as a plain option, so the wrapped command's paths were read
    from the wrong folder; `env -S` hid its command; `pushd -n`, `popd -n` and `pushd`/`popd ±N` were read as plain
    folder changes. Now `env -C` is a folder change for the wrapped command, `env -S` is refused, and the stack
    options make the folder unknown (its writes `everywhere`, its commits `commit-folder-unreadable`)."""
    import helpers
    root = gtask.as_posix()
    for command in ("env -C mkway/locks cp /tmp/x engine.json",
                    'env --chdir=mkway/state sh -c "echo x > register.sha"',
                    "cd mkway/locks; pushd -n /tmp; echo x > engine.json",
                    "pushd src; pushd mkway/locks; popd +1; echo x > engine.json",
                    "pushd mkway/locks; pushd /tmp; pushd +1; echo x > engine.json",
                    "env --chdir=mkway cp x profile.json",
                    "env -S 'git commit -m x -- mkway/profile.json'",
                    f"pushd /tmp; pushd {root}/mkway/locks; popd -n; echo x > engine.json"):
        assert shell(gtask, command).kind == "refuse", command
    assert [c.cwd for c in helpers.commit_cmd("env -C mkway/cards git commit -m x -- REGISTER.md")] == ["mkway/cards"]
    assert [c.cwd for c in helpers.commit_cmd("env -C mkway git commit -m x -- profile.json")] == ["mkway"]
    (commit,) = helpers.commit_cmd("pushd -n mkway; git commit -m x -- profile.json")
    assert commit.folder_unreadable


GIT_FORM_DENY = [
    ("git commit --inc -m x -- README.md", "command-unparsed"),
    ("git -c alias.ci=commit ci -m x", "command-unparsed"),
    ("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.ci GIT_CONFIG_VALUE_0=commit git ci -m x", "command-unparsed"),
    ("export GIT_CONFIG_COUNT=1; git status", "command-unparsed"),
    ("git config alias.ci commit; git ci -m x", "command-unparsed"),
    ("git ci -m x", "command-unparsed"),
    ("git commit --pathspec-from-file=list.txt -m x", "pathspec-unparsed"),
    ("git commit --pathspec-from-file list.txt -m x", "pathspec-unparsed"),
]
ENGINE_PREFIX_DENY = [
    "python mkway/engine/mkway.py card new t --prof scratch/evil.json",
    "python mkway/engine/mkway.py card list --prof=x",
    "python mkway/engine/mkway.py check --prof x",
    "python mkway/engine/mkway.py lock list --prof x",
    "python mkway/engine/mkway.py card new t --ro C:/other",
]


def test_commit_forms_and_option_prefixes(gtask):
    """Item 8 (A-M2, A-M1; R83 «refused outright»): `--pathspec-from-file` was consumed and never read; long options
    matched only by exact name, while git takes `--inc` for `--include`; `-c alias.*` and `GIT_CONFIG_*` hid a
    commit; and mkway.py's subparsers took `--prof`/`--ro` for `--profile`/`--root`. Now `--pathspec-from-file`
    refuses `pathspec-unparsed`; a commit long option that is not an exact known name, a `-c alias.` value and a
    `GIT_CONFIG_` assignment refuse `command-unparsed`; every subparser has `allow_abbrev=False`, and the gate refuses
    any `--` prefix of `--profile` or `--root`."""
    import helpers
    for command, want in GIT_FORM_DENY:
        assert _kind(shell(gtask, command)) == want, command
    for command in ("git commit --amend --no-edit", "git status", "git -C src log --oneline",
                    "git commit --untracked-files=no -m x -- a.py"):
        assert helpers.git_form_problem(command) is None, command
    for command in ENGINE_PREFIX_DENY:
        assert _kind(shell(gtask, command)) == "engine-call-not-plain", command
    code, out, err = cli(gtask, "card", "list", "--prof", "x")
    assert code == 2 and "unrecognized" in err, (code, out, err)


def _fake_git(head_exists: bool):
    import subprocess

    def fake(cwd, *args, **kwargs):
        if args[:2] == ("diff", "--name-only") and "HEAD" in args:
            return subprocess.CompletedProcess(args, 128, "", "fatal: a failure")
        if args[:1] == ("rev-parse",):
            return subprocess.CompletedProcess(args, 0 if head_exists else 1, "abc\n" if head_exists else "", "")
        return subprocess.CompletedProcess(args, 0, "", "")
    return fake


def test_all_commit_refuses_when_git_fails(gtask, monkeypatch):
    """Item 9 (A-L2): under `-a`, any non-zero `git diff --name-only HEAD` was taken as «no HEAD», so only the staged
    names were checked and the tracked changes `-a` commits were missed. Now a failure refuses; the one exception is
    when `rev-parse --verify HEAD` shows there is no HEAD, the same as `_expand`."""
    import gate_lock
    monkeypatch.setattr(gate_lock.runner, "git", _fake_git(head_exists=True))
    assert shell(gtask, "git commit -a -m x").kind == "refuse"
    monkeypatch.setattr(gate_lock.runner, "git", _fake_git(head_exists=False))
    assert shell(gtask, "git commit -a -m x").kind != "refuse"


def test_paths_are_recorded_once(tmp_path):
    """Item 10 (A(c), chief point): `card open` on an already open card re-recorded Paths, and in light mode
    (`owner_moves: []`) any session may run it, so a session widened its own scope. Paths are now recorded only at
    the first open from `proposed`; a re-open never re-records them, light mode included."""
    from test_cardmoves import _row, set_paths
    root = task_root(tmp_path, cards={"owner_moves": []})
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    set_paths(root, "CARD-001", "`src/a.py`")
    assert cli(root, "card", "open", "CARD-001", session=True)[0] == 0
    assert _row(root, "CARD-001")["paths"] == "src/a.py"
    set_paths(root, "CARD-001", "`src/`, `other/`")
    assert cli(root, "card", "open", "CARD-001", session=True)[0] == 0
    assert _row(root, "CARD-001")["paths"] == "src/a.py"
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    assert _row(root, "CARD-001")["paths"] == "src/a.py"


FOLDER_DENY = [
    "cd mkway | git commit -m x -- mkway/profile.json",
    "true || cd mkway; git commit -m x -- mkway/profile.json",
    "git -C mkway -C . commit -m x -- profile.json",
    "cd mkway | true; cp x mkway/profile.json",
    "false && cd mkway; git commit -m x -- mkway/profile.json",
    "for x in $(false); do cd mkway; done; git commit -m x -- mkway/profile.json",
    "cd nosuch; echo '{}' > mkway/locks/engine.json",
]


def test_only_plain_top_level_folder_changes_count(gtask):
    """Item 11 (B-H3, R83): folder tracking took every `cd` as run and kept: one in a pipeline, behind `&&`/`||`,
    inside a loop, or to a folder that does not exist; and the last of several `git -C` won. Now a `cd`, `pushd` or
    `popd` changes the folder only as the first command of its and-or list, at top level, not after `&&`/`||`, not
    in a pipeline or the background, not inside a compound, and to a folder that exists; any other makes the folder
    unknown (writes `everywhere`, commits `commit-folder-unreadable`); two or more `-C` make it unknown too."""
    for command in FOLDER_DENY:
        assert shell(gtask, command).kind == "refuse", command
    (gtask / "src").mkdir(exist_ok=True)  # X11 addendum: the held folder lasts only through a pure `&&` chain
    assert shell(gtask, "cd src && true || echo x > mkway/profile.json").kind == "refuse"
    (gtask / "x").mkdir()
    (gtask / "x" / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert shell(gtask, "cd x && git commit -m m -- a.py").kind != "refuse"


BINDING_DENY = [
    "D=a; for D in mkway; do git commit -m x -- $D/profile.json; done",
    "D=a; declare D=mkway; cp x $D/profile.json",
    "D=mkway; (D=a); git commit -m x -- $D/profile.json",
    "D=mkway; false && D=a; git commit -m x -- $D/profile.json",
    "D=a; eval D=mkway; git commit -m x -- $D/profile.json",
    "D=a; mapfile -t D < <(echo mkway); git commit -m x -- $D/profile.json",
    "D=a; unset D; : ${D:=mkway}; git commit -m x -- $D/profile.json",
]


def test_only_plain_top_level_bindings_keep_a_literal(gtask):
    """Item 12 (B-H2, check 2 M3): `expand_vars` learned a name from any simple command made only of assignments and
    kept an earlier literal through other bindings (`for`, `declare`, a subshell, `&&`, `eval`, `mapfile`,
    `${D:=…}`), so the gate checked a stale path. A name now keeps its literal only when every binding of it is a
    plain assignment that runs unconditionally at top level; any other binding makes it unknown; `eval`,
    `source`/`.`, `mapfile`/`readarray`, `select`, `getopts`, `${NAME:=…}` or `${NAME=…}` make every name unknown."""
    import helpers
    for command in BINDING_DENY:
        assert shell(gtask, command).kind == "refuse", command
    assert helpers.expanded_text("D=src; cp x $D/a.py") == "D=src\ncp x src/a.py"


def test_the_refusal_way_out_is_allowed(gtask):
    """Item 13 (A-M3): a staged locked file is refused with «unstage it with `git restore --staged <path>`», but
    that command was itself refused `lock-closed-shell`: `--staged` was ignored and the path read as a write. A
    `git restore --staged` without `--worktree` writes nothing to the working tree, so it is allowed; the refusal's
    own command is checked here."""
    import re
    from test_lock import _git
    pfile = gtask / "mkway" / "profile.json"
    pfile.write_bytes(pfile.read_bytes() + b"\n")
    _git(gtask, "add", "mkway/profile.json")
    message = shell(gtask, "git commit -m x").message
    (way_out,) = re.findall(r"`(git restore --staged [^`]+)`", message)
    assert shell(gtask, way_out).kind != "refuse", way_out
    for command in ("git restore mkway/profile.json", "git restore --staged --worktree mkway/profile.json",
                    "git restore -SW mkway/profile.json"):
        assert shell(gtask, command).kind == "refuse", command


def test_git_bash_folder_is_converted_before_the_join(gtask):
    """Item 14 (B-M1): `join_folder` kept a Git-Bash folder `/c/<root>/src` as an absolute path, and the commit check
    joined it to the root (`C:/c/<root>/src`), so git ran in a folder that does not exist and every pathspec commit
    after such a `cd` was refused. The folder is now converted with the `_GITBASH` rule before it is joined."""
    posix = gtask.as_posix()
    if posix[1:2] != ":":
        pytest.skip("a Git-Bash folder needs a drive-letter root")
    gitbash = "/" + posix[0].lower() + posix[2:]
    (gtask / "src").mkdir(exist_ok=True)
    (gtask / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert shell(gtask, f"cd {gitbash}/src && git commit -m x -- a.py").kind != "refuse"
    pfile = gtask / "mkway" / "profile.json"
    pfile.write_bytes(pfile.read_bytes() + b"\n")
    assert _kind(shell(gtask, f"cd {gitbash}/mkway && git commit -m x -- profile.json")) == "lock-closed-commit"


def test_copy_into_a_folder_checks_the_file_it_writes(gtask):
    """Item 15 (A-L1, A(d)): a copy or move into a folder (`cp a.txt .`, `cp notes.txt mkway/`) was read as a write of
    the folder itself, and a folder that holds a closed target refused it. For `cp`, `mv`, `install` and `ln` a
    folder destination is now checked as `<dest>/<basename(src)>`."""
    for command in ("cp /tmp/a.txt .", "mv build/out.txt .", "cp notes.txt mkway/", "ln -s ../a.txt mkway/"):
        assert shell(gtask, command).kind != "refuse", command
    for command in ("cp a/profile.json mkway/", "cp x mkway/locks/", "mv b/mkway.lock mkway/",
                    "install -m 644 b/profile.json mkway/"):
        assert shell(gtask, command).kind == "refuse", command


def test_check_warns_when_the_git_builtin_list_differs(tmp_path):
    """Item 8 (R90): the built-in list is a static engine key (`lock_gate.git_builtins` in defaults.json, written
    from knowledge and marked «unverified»); `mkway check` compares it with `git --list-cmds=builtins` in the owner's
    terminal and warns on a difference. A fake runner's output that differs from the key gives the warning; the same
    list gives none."""
    import json
    import install
    key = json.loads((install.Path(install.__file__).parent / "defaults.json").read_text(encoding="utf-8"))
    builtins = key["lock_gate"]["git_builtins"]
    assert "commit" in builtins and "ci" not in builtins
    line = install.git_builtins_line(tmp_path, run=lambda: "\n".join(builtins[1:] + ["zz-new"]) + "\n")
    assert line.startswith("git builtins: warning") and builtins[0] in line and "zz-new" in line, line
    same = install.git_builtins_line(tmp_path, run=lambda: "\n".join(builtins) + "\n")
    assert not same.startswith("git builtins: warning"), same
