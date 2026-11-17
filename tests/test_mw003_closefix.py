"""MW-003 close-fix round: the findings of the blind close check on f763cdb, one test per order item. Synthetic
task roots only."""
import os

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
    """Catches: an owner-only command that runs inside a session, where each one must exit 1 with the reason line before it does anything (Item 1, A-M5, R37 (a) H4)."""
    # the CLI itself refused no owner-only command when CLAUDECODE was set, so every gap in the shell gate's command reading was a full bypass
    root = task_root(tmp_path)
    code, out, err = cli(root, *args, env={"CLAUDECODE": "1"})
    assert code == 1, (out, err)
    assert REASON in err
    assert not (root / "mkway" / "locks" / "engine.json").exists()


def test_owner_only_command_refused_with_an_empty_variable(tmp_path):
    """Catches: an owner-only command that runs when the session variable is present with the empty value (Item 1, A-M5)."""
    # the variable counts when present with any value, the empty value included
    root = task_root(tmp_path)
    code, out, err = cli(root, "lock", "open", "engine", env={"CLAUDECODE": ""})
    assert code == 1, (out, err)
    assert REASON in err
    assert not (root / "mkway" / "locks" / "engine.json").exists()


def test_owner_only_command_runs_without_the_variable(tmp_path):
    """Checks: the owner's own terminal has no session variable, so the owner-only command runs (Item 1, A-M5)."""
    root = task_root(tmp_path)
    code, out, err = cli(root, "lock", "open", "engine", env={})
    assert code == 0, (out, err)
    assert (root / "mkway" / "state" / "locks" / "engine.json").is_file()  # changed by MW-022 (E1): the shared folder


@pytest.mark.parametrize("args", [pytest.param(("card", "open", "CARD-001"), id="card-open"),
                                  pytest.param(("card", "close", "CARD-001"), id="card-close")])
def test_light_mode_card_moves_are_not_refused_by_the_cli(tmp_path, args):
    """Checks: in light mode a session's card open and card close are not owner-only, so the CLI does not refuse them with the reason line (Item 1, A-M5)."""
    # the same owner_moves rule as the lock gate; light mode is owner_moves []
    root = task_root(tmp_path, cards={"owner_moves": []})
    code, out, err = cli(root, *args, env={"CLAUDECODE": "1"})
    assert REASON not in err, args


from test_lock import gtask, shell  # noqa: E402,F401  (gtask is a fixture)


def _kind(v):
    return v.reason_id if v.kind == "refuse" else v.kind


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
    """Catches: a commit hidden inside another program that goes through instead of refusing command-unparsed, while plain carriers of other git commands stay allowed (Item 3, B-H5, R83 fail-closed form)."""
    # commit_cmd read no commit inside bash -c, sh -c, cmd /c, pwsh -Command, xargs, find -exec, eval, script -c or an interpreter's -c/-e, so a staged locked file went in with the commit;
    # a carrier whose argument text, with quotes and backslashes removed, holds a git token (or a $ or backtick word in its place) followed by commit refuses; the inner shell is not modelled
    assert [c for c in CARRIED_DENY if _kind(shell(gtask, c)) != "command-unparsed"] == []
    assert [c for c in CARRIED_ALLOW if shell(gtask, c).kind == "refuse"] == []


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
    """Catches: an engine call hidden in a form the parser does not go into that is not refused engine-call-not-plain, or a quoted message, pattern or note that names mkway wrongly refused (Item 4, A-M4, P1)."""
    # the detector scanned the whole raw text, quoted messages and heredoc bodies included; when the command parses, its engine calls are found by the parser; the free-text scan runs only when the parse
    # fails and on the argument text of the forms the parser does not go into (xargs, find -exec, eval, cmd /c, an interpreter's -c/-e, a shell's heredoc), so those are never less caught than at f763cdb
    import helpers
    assert [c for c in ENGINE_TEXT_PASS if helpers.holds_engine_call(c, "bash")] == []
    assert [c for c in ENGINE_TEXT_PASS if _kind(shell(gtask, c)) == "engine-call-not-plain"] == []
    assert [c for c in ENGINE_TEXT_DENY if not helpers.holds_engine_call(c, "bash")] == []
    assert [c for c in ENGINE_TEXT_DENY if _kind(shell(gtask, c)) != "engine-call-not-plain"] == []


LOCK_JSON = "'{\"name\":\"engine\",\"state\":\"open\",\"until\":\"2099-01-01T00:00:00\"}'"


def test_powershell_parameter_prefixes(gtask):
    """Catches: a PowerShell parameter prefix of two characters that the reader drops, so a forged lock file is written (Item 6, A-H3)."""
    # PowerShell takes -L for -LiteralPath, but the reader returned any name under 3 characters unchanged and then dropped its value as an unknown parameter's;
    # every unique prefix now maps to its parameter, 2 characters included; a parameter the reader does not know (or an ambiguous prefix) on a writer cmdlet makes the write everywhere
    import helpers
    command = f"Set-Content -L mkway/locks/engine.json -Value {LOCK_JSON}"
    assert shell(gtask, command, tool="PowerShell").kind == "refuse", command
    command = f"Add-Content -L mkway/locks/engine.json -Value {LOCK_JSON}"
    assert shell(gtask, command, tool="PowerShell").kind == "refuse", command
    command = f"{LOCK_JSON} | Out-File -L mkway/locks/engine.json"
    assert shell(gtask, command, tool="PowerShell").kind == "refuse", command
    assert helpers.shell_writes("Set-Content -L src/a.txt -Value x", "powershell").paths == ["src/a.txt"]
    assert helpers.shell_writes("Set-Content -Zork q src/a.txt -Value x", "powershell").everywhere
    assert helpers.shell_writes("Set-Content -P src/a.txt -Value x", "powershell").everywhere
    assert not helpers.shell_writes("Set-Content -Path src/a.txt -Value x -Encoding utf8 -ea Stop",
                                    "powershell").everywhere


def test_env_chdir_and_the_folder_stack(gtask):
    """Catches: a write or commit through env -C, env -S or the folder stack options that is read from the wrong folder and goes through (Item 7, A-H2, B-H4)."""
    # env -C/--chdir was skipped as a plain option; env -S hid its command; pushd -n, popd -n and pushd/popd ±N were read as plain folder changes;
    # now env -C is a folder change for the wrapped command, env -S is refused, and the stack options make the folder unknown (its writes everywhere, its commits commit-folder-unreadable)
    import helpers
    root = gtask.as_posix()
    commands = ["env -C mkway/locks cp /tmp/x engine.json",
                'env --chdir=mkway/state sh -c "echo x > register.sha"',
                "cd mkway/locks; pushd -n /tmp; echo x > engine.json",
                "pushd src; pushd mkway/locks; popd +1; echo x > engine.json",
                "pushd mkway/locks; pushd /tmp; pushd +1; echo x > engine.json",
                "env --chdir=mkway cp x profile.json",
                "env -S 'git commit -m x -- mkway/profile.json'",
                f"pushd /tmp; pushd {root}/mkway/locks; popd -n; echo x > engine.json"]
    assert [c for c in commands if shell(gtask, c).kind != "refuse"] == []
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
    """Catches: a commit hidden by a pathspec file, an abbreviated long option, a git alias or a GIT_CONFIG assignment, or an abbreviated mkway option, that is not refused (Item 8, A-M2, A-M1, R83 refused outright)."""
    # --pathspec-from-file was consumed and never read; long options matched only by exact name, while git takes --inc for --include; -c alias.* and GIT_CONFIG_* hid a commit; mkway.py's subparsers took --prof/--ro for --profile/--root;
    # now --pathspec-from-file refuses pathspec-unparsed; a commit long option that is not an exact known name, a -c alias. value and a GIT_CONFIG_ assignment refuse command-unparsed;
    # every subparser has allow_abbrev=False, and the gate refuses any -- prefix of --profile or --root
    import helpers
    allowed = ["git commit --amend --no-edit", "git status", "git -C src log --oneline", "git commit --untracked-files=no -m x -- a.py"]
    assert [c for c, want in GIT_FORM_DENY if _kind(shell(gtask, c)) != want] == []
    assert [c for c in allowed if helpers.git_form_problem(c) is not None] == []
    assert [c for c in ENGINE_PREFIX_DENY if _kind(shell(gtask, c)) != "engine-call-not-plain"] == []
    code, out, err = cli(gtask, "card", "list", "--prof", "x")
    assert code == 2, (code, out, err)
    assert "unrecognized" in err, (code, out, err)


def _fake_git(head_exists: bool):
    import subprocess

    def fake(cwd, *args, **kwargs):
        if args[:2] == ("diff", "--name-only") and "HEAD" in args:
            return subprocess.CompletedProcess(args, 128, "", "fatal: a failure")
        if args[:1] == ("rev-parse",):
            return subprocess.CompletedProcess(args, 0 if head_exists else 1, "abc\n" if head_exists else "", "")
        return subprocess.CompletedProcess(args, 0, "", "")
    return fake


def test_paths_are_recorded_once(tmp_path):
    """Checks: Paths are recorded only at the first open from proposed, and a re-open never re-records them, light mode included (Item 10, A(c), chief point)."""
    # card open on an already open card re-recorded Paths, and in light mode (owner_moves []) any session may run it, so a session widened its own scope
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
    """Catches: a folder change that is not a plain top level cd, a cd in a pipeline, behind and-or, inside a loop or to a missing folder, or several git -C, taken as run and kept so a write or commit goes through (Item 11, B-H3, R83)."""
    # a cd, pushd or popd changes the folder only as the first command of its and-or list, at top level, not after &&/||, not in a pipeline or the background, not inside a compound, and to a folder that exists;
    # any other makes the folder unknown (writes everywhere, commits commit-folder-unreadable); two or more -C make it unknown too
    assert [c for c in FOLDER_DENY if shell(gtask, c).kind != "refuse"] == []
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
    """Catches: a variable that keeps an earlier literal through a loop, declare, subshell, and-or, eval, mapfile or default binding, so the gate checks a stale path (Item 12, B-H2, check 2 M3)."""
    # expand_vars learned a name from any simple command made only of assignments; a name now keeps its literal only when every binding of it is a plain assignment that runs unconditionally at top level;
    # any other binding makes it unknown; eval, source, mapfile/readarray, select, getopts, ${NAME:=...} or ${NAME=...} make every name unknown
    import helpers
    assert [c for c in BINDING_DENY if shell(gtask, c).kind != "refuse"] == []
    assert helpers.expanded_text("D=src; cp x $D/a.py") == "D=src\ncp x src/a.py"


def test_the_refusal_way_out_is_allowed(gtask):
    """Checks: the way out a refusal names, git restore staged without worktree, is allowed, while a restore that writes the working tree stays refused (Item 13, A-M3)."""
    # a staged locked file is refused with «unstage it with git restore --staged <path>», but that command was itself refused lock-closed-shell: --staged was ignored and the path read as a write
    import re
    from test_lock import _git
    pfile = gtask / "mkway" / "profile.json"
    pfile.write_bytes(pfile.read_bytes() + b"\n")
    _git(gtask, "add", "mkway/profile.json")
    message = shell(gtask, "git commit -m x").message
    (way_out,) = re.findall(r"`(git restore --staged [^`]+)`", message)
    assert shell(gtask, way_out).kind != "refuse", way_out
    writing = ["git restore mkway/profile.json", "git restore --staged --worktree mkway/profile.json",
               "git restore -SW mkway/profile.json"]
    assert [c for c in writing if shell(gtask, c).kind != "refuse"] == []


@pytest.mark.skipif(os.name != "nt", reason="a Git-Bash folder needs a drive-letter root")
def test_git_bash_folder_is_converted_before_the_join(gtask):
    """Checks: a Git-Bash folder is converted with the GITBASH rule before it is joined, so a pathspec commit after such a cd is not refused for a folder that does not exist (Item 14, B-M1)."""
    # join_folder kept a Git-Bash folder /c/<root>/src as an absolute path, and the commit check joined it to the root (C:/c/<root>/src), so git ran in a folder that does not exist
    posix = gtask.as_posix()
    gitbash = "/" + posix[0].lower() + posix[2:]
    (gtask / "src").mkdir(exist_ok=True)
    (gtask / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert shell(gtask, f"cd {gitbash}/src && git commit -m x -- a.py").kind != "refuse"
    pfile = gtask / "mkway" / "profile.json"
    pfile.write_bytes(pfile.read_bytes() + b"\n")
    assert _kind(shell(gtask, f"cd {gitbash}/mkway && git commit -m x -- profile.json")) == "lock-closed-commit"


def test_copy_into_a_folder_checks_the_file_it_writes(gtask):
    """Catches: a copy or move into a closed folder of a file that is a closed target that goes through, or one into an open folder wrongly refused as a write of the folder itself (Item 15, A-L1, A(d))."""
    # a copy or move into a folder was read as a write of the folder itself, and a folder that holds a closed target refused it; for cp, mv, install and ln a folder destination is checked as <dest>/<basename(src)>
    open_folder = ["cp /tmp/a.txt .", "mv build/out.txt .", "cp notes.txt mkway/", "ln -s ../a.txt mkway/"]
    closed_target = ["cp a/profile.json mkway/", "cp x mkway/locks/", "mv b/mkway.lock mkway/", "install -m 644 b/profile.json mkway/"]
    assert [c for c in open_folder if shell(gtask, c).kind == "refuse"] == []
    assert [c for c in closed_target if shell(gtask, c).kind != "refuse"] == []


def test_check_warns_when_the_git_builtin_list_differs(tmp_path):
    """Checks: mkway check warns when git's builtin list differs from the static engine key, and gives no warning for the same list (Item 8, R90)."""
    # the built-in list is the static engine key lock_gate.git_builtins in defaults.json, written from knowledge and marked «unverified»; check compares it with git --list-cmds=builtins in the owner's terminal;
    # a fake runner's output that differs from the key gives the warning, the same list gives none
    import json
    import install
    key = json.loads((install.Path(install.__file__).parent / "defaults.json").read_text(encoding="utf-8"))
    builtins = key["lock_gate"]["git_builtins"]
    assert "commit" in builtins
    assert "ci" not in builtins
    line = install.git_builtins_line(tmp_path, run=lambda: "\n".join(builtins[1:] + ["zz-new"]) + "\n")
    assert line.startswith("git builtins: warning"), line
    assert builtins[0] in line, line
    assert "zz-new" in line, line
    same = install.git_builtins_line(tmp_path, run=lambda: "\n".join(builtins) + "\n")
    assert not same.startswith("git builtins: warning"), same
