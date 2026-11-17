"""MW-003 remainder: the re-check findings on the close-fix round, the rulings on them and close-fix items 17 and 19,
one or more tests per order item. Each deny row is the replayed finding input; `L` is a lock file and `J` a lock text
in state open. Synthetic task roots only."""
from test_lock import _git, gtask, shell  # noqa: F401  (gtask is a fixture)

L = "mkway/locks/engine.json"
J = "'{\"name\":\"engine\",\"state\":\"open\"}'"


def _kind(v):
    return v.reason_id if v.kind == "refuse" else v.kind


def _stage_profile(root):
    """The findings' precondition: a changed locked file is staged (`git add` of it is allowed)."""
    path = root / "mkway" / "profile.json"
    path.write_bytes(path.read_bytes() + b"\n")
    _git(root, "add", "mkway/profile.json")


# ---- item 1: commit visibility (H8, O6) -----------------------------------------------------------------------------

UNREAD_COMMITS = [
    ("H8e", "stdbuf -oL git commit -m x"),
    ("H8f", "winpty git commit -m x"),
    ("H8i", "function f { git commit -m x; }; f"),
    ("H8j", "read G <<< git; $G commit -m x"),
    ("one read, one not", "git commit -m ok -- a.py; stdbuf -oL git commit -m x"),
    ("quoted subcommand", 'stdbuf -oL git "commit" -m x'),
    ("single-quoted subcommand", "winpty git 'commit' -m x"),
    ("in a substitution", 'X="$(stdbuf -oL git commit -m x)"'),
    ("$ word, quoted", 'read G <<< git; $G "commit" -m x'),
    ("backtick word", "`which git` commit -m x"),
]
COMMIT_PASS = [
    "git config --get commit.gpgsign",
    "git log --grep commit",
    "git help commit",
    'git commit -m "fix the commit check" -- README.md',
    "git diff --name-only | xargs git add",
    "bash -c 'digit commit -m x'",
    "bash -c 'git log --grep commit'",
]


def test_a_commit_the_reader_does_not_read_refuses(gtask):
    """Item 1, R95 (2a) (H8e, H8f, H8i, H8j): `commit_cmd` reads a commit only when `git` is the program; a `git`
    word behind another program (`stdbuf`, `winpty`), inside a `function` body or a `$` word in the git position
    took a staged locked file into the commit unchecked. Now a simple command whose words (quotes removed) hold a
    `git` word, or a `$`/backtick word, whose subcommand after git's global options is `commit`, and whose commit
    `commit_cmd` did not read, refuses `command-unparsed`. `commit` after another subcommand, `commit.gpgsign` and
    `digit` are not it (R95a, O6)."""
    _stage_profile(gtask)
    for cid, command in UNREAD_COMMITS:
        assert _kind(shell(gtask, command)) == "command-unparsed", (cid, command)
    for command in COMMIT_PASS:
        assert shell(gtask, command).kind != "refuse", command


def test_xargs_git_and_a_shell_fed_by_stdin_are_carriers(gtask):
    """Item 1 (H8a, H8b): `xargs git` with its subcommand coming from stdin, and a shell fed by a heredoc or a pipe,
    ran a commit whose words the gate never saw. `xargs git` with no subcommand in its own arguments refuses; a
    shell fed by a heredoc or stdin is a carrier, and its text naming a commit refuses `command-unparsed`."""
    _stage_profile(gtask)
    for command in ("echo commit -m x | xargs git",                     # H8a
                    "bash <<'EOF'\ngit commit -m x\nEOF",              # H8b
                    "echo 'git commit -m x' | bash",
                    "printf 'git commit -m x' | sh -s"):
        assert _kind(shell(gtask, command)) == "command-unparsed", command
    for command in ("cat steps.sh | bash", "bash <<'EOF'\necho done\nEOF"):
        assert shell(gtask, command).kind != "refuse", command


def test_interpreter_flags_are_read_as_clusters_and_attached_forms(gtask):
    """Item 1 (H8c, H8d): an interpreter's code was found only after an exact `-c` or `-e` word, so `-c"…"` (the
    code attached) and `-Ic` (a cluster) ran a commit unseen. Clusters and attached forms are now read."""
    _stage_profile(gtask)
    for command in ("python -c\"import subprocess;subprocess.run(['git','commit','-m','x'])\"",   # H8c
                    "python -Ic \"import subprocess;subprocess.run(['git','commit','-m','x'])\""):  # H8d
        assert _kind(shell(gtask, command)) == "command-unparsed", command


def test_verify_first_perl_and_node_code_flags(gtask):
    """Item 1, verify first: `perl -E`, `perl -we`, `node -p` and `node --eval` carry code the same way."""
    _stage_profile(gtask)
    for command in ("perl -E 'system(\"git commit -m x\")'",
                    "perl -we 'system(\"git commit -m x\")'",
                    "node -p \"require('child_process').execSync('git commit -m x')\"",
                    "node --eval \"require('child_process').execSync('git commit -m x')\""):
        assert _kind(shell(gtask, command)) == "command-unparsed", command


def test_verify_first_an_interpreter_fed_by_stdin_with_a_process_start(gtask):
    """Item 1, verify first (R98): an interpreter fed by a heredoc or stdin is a carrier only when its body also
    holds a process-start call; a script that only edits text naming `git commit` passes."""
    _stage_profile(gtask)
    for command in ("python - <<'EOF'\nimport subprocess\nsubprocess.run(['git', 'commit', '-m', 'x'])\nEOF",
                    "echo \"system('git commit -m x')\" | perl"):
        assert _kind(shell(gtask, command)) == "command-unparsed", command
    text_only = "python - <<'EOF'\ntext = open('notes.md').read().replace('git commit', 'git commit -s')\nEOF"
    assert shell(gtask, text_only).kind != "refuse"


def test_verify_first_powershell_command_prefixes_and_encoded_commands(gtask):
    """Item 1, verify first: for `pwsh` and `powershell` any prefix of `-Command` or `-CommandWithArgs` is a
    carrier; any prefix of `-EncodedCommand` and the aliases `-e` and `-ec` refuse, whatever the text."""
    _stage_profile(gtask)
    for command in ('pwsh -comm "git commit -m x"', 'powershell -cwa "git commit -m x"',
                    "powershell -enc ZwBpAHQA", "pwsh -e ZwBpAHQA", "pwsh -ec ZwBpAHQA",
                    "pwsh -EncodedC ZwBpAHQA"):
        assert _kind(shell(gtask, command)) == "command-unparsed", command
    assert shell(gtask, 'pwsh -comm "Get-ChildItem"').kind != "refuse"


def test_cmd_r_and_trap_text_are_carriers(gtask):
    """Item 1 (H8k, H8h): `cmd /r` is `cmd /c`, and a `trap` text runs as a command; both hid a commit."""
    _stage_profile(gtask)
    for command in ("cmd /r git commit -m x", "trap 'git commit -m x' EXIT"):
        assert _kind(shell(gtask, command)) == "command-unparsed", command


ENGINE_DENY = [
    ("H9a", "cat <(env -u CLAUDECODE python mkway/engine/mkway.py lock open engine)"),
    ("H9b", "stdbuf -oL env -u CLAUDECODE python mkway/engine/mkway.py lock open engine"),
    ("H9c", "trap 'python mkway/engine/mkway.py lock open engine' EXIT"),
    ("behind stdbuf, in bash -c", "stdbuf -oL bash -c 'python mkway/engine/mkway.py lock open engine'"),
    ("a check in <(…)", "cat <(python mkway/engine/mkway.py check --profile other.json)"),
    ("winpty", "winpty python mkway/engine/mkway.py lock open engine"),
    ("function body", "function f { python mkway/engine/mkway.py lock open engine; }; f"),
]
ENGINE_PASS = [  # close-fix item 4's four must-pass rows
    'git commit -m "mkway check prints the error" -- README.md',
    'grep -n "mkway card" README.md',
    'git log --grep "mkway lock"',
    "cat > notes.md <<'EOF'\nrun python mkway/engine/mkway.py card take CARD-001 first\nEOF",
]


def test_engine_calls_are_never_less_caught_than_before_the_parser_rule(gtask):
    """Item 2, R95 (3a) (H9): close-fix item 4 scanned only the carrier texts and shell heredocs, so an engine call
    behind `stdbuf`, `winpty`, in `<(…)`, a `trap` text or a function body passed, though the whole-text scan of the
    earlier round refused it. Now every match of the engine-call pattern in the text with quoted strings and
    non-shell heredoc bodies removed goes to the exact-form check, and so does every carrier text item 1 reads."""
    import helpers
    for cid, command in ENGINE_DENY:
        assert helpers.holds_engine_call(command, "bash"), (cid, command)
        assert _kind(shell(gtask, command)) == "engine-call-not-plain", (cid, command)
    for command in ENGINE_PASS:
        assert not helpers.holds_engine_call(command, "bash"), command
        assert _kind(shell(gtask, command)) != "engine-call-not-plain", command


DISGUISED = [  # A-H1's three inputs
    "python mkway/engine/mkwa?.py lock open engine",
    "S=mkway/engine/mkway.py; python $S lock open engine",
    "python mkway/eng$(echo ine)/mk$(echo way).py lock open engine",
]


def test_disguised_engine_script_names_are_engine_calls(gtask):
    """Item 3, close-fix item 17 (A-H1): an engine script named by a glob, a variable or a substitution was no
    engine call to the shell gate, so only the CLI's own `CLAUDECODE` tripwire stood in the way. An interpreter call
    whose script word, after same-command expansion, matches `mkway.py` as a glob, or still holds `$`, a backtick,
    `*`, `?`, `[` or `{`, is now an engine-call candidate, and the exact form refuses it."""
    import helpers
    for command in DISGUISED:
        assert helpers.holds_engine_call(command, "bash"), command
        assert _kind(shell(gtask, command)) == "engine-call-not-plain", command
    for command in ("python tools/report.py --out x.md", "python -m pytest -q", "python mkway/engine/mkway.py card list"):
        assert _kind(shell(gtask, command)) != "engine-call-not-plain", command


def test_powershell_dashes_and_splats(gtask):
    """Item 5 (H10): PowerShell takes U+2013, U+2014 and U+2015 as `-`, but the reader tested only `-`, so
    `–LiteralPath` was read as the positional path; and a splat (`@p`) hid every parameter. Both wrote a lock file
    with no log row. The three dashes now count as `-`, and a splat on a writer cmdlet makes the write `everywhere`."""
    import helpers
    for command in (f"Set-Content –LiteralPath {L} –Value '{{}}'",                  # H10a
                    f"$p=@{{LiteralPath='{L}';Value='x'}}; Set-Content @p",                     # H10b
                    f"Set-Content —LiteralPath {L} ―Value 'x'"):
        assert shell(gtask, command, tool="PowerShell").kind == "refuse", command
    assert helpers.shell_writes("Set-Content @p", "powershell").everywhere
    assert helpers.shell_writes("Set-Content –Path src/a.txt –Value x", "powershell").paths == ["src/a.txt"]


def test_target_directory_for_all_four_copy_programs(gtask):
    """Item 6 (H11): `-t` was read only for `cp` and `mv` and only as a separate word, so `install -t`, `ln -t`,
    `cp -t<dir>` and `cp --target=<dir>` (getopt takes a unique prefix) wrote a lock file read as a path outside the
    root or as the source. For `cp`, `mv`, `install` and `ln`, `-t`, `-t<dir>`, `--target-directory` and any unique
    prefix of it, attached or separate, are read; an unknown long option makes the write `everywhere`."""
    import helpers
    for command in ("install -t mkway/locks /tmp/engine.json",     # H11a
                    "ln -t mkway/locks /tmp/engine.json",          # H11b
                    "cp -tmkway/locks engine.json",                 # H11c
                    "cp --target=mkway/locks engine.json",          # H11d
                    "mv -vt mkway/locks /tmp/engine.json",
                    "ln --target-dir mkway/locks /tmp/engine.json"):
        assert shell(gtask, command).kind == "refuse", command
    assert helpers.shell_writes("install -t dir a b").paths == ["dir/a", "dir/b"]
    assert helpers.shell_writes("cp --frobnicate a b").everywhere
    assert not helpers.shell_writes("cp -r --preserve=mode --backup=numbered a b").everywhere


def test_git_restore_staged_only_by_its_exact_forms(gtask):
    """Item 7 (H12): close-fix item 13's «staged only» test took `--work` (git's prefix of `--worktree`) for no
    worktree, and the `S` of `-sS` (the source `S`) for `--staged`, so a rollback of the tracked profile was allowed
    with no log. Only an exact `--staged`, or `-S` with no attached value, means «staged»; any `--` prefix of
    `--worktree` means worktree; an unknown long option means a write. The refusal's own way out still passes."""
    import helpers
    for command in ("git restore --staged --work --source=HEAD~3 mkway/profile.json",   # H12a
                    "git restore -sS mkway/profile.json",                              # H12b
                    "git restore --staged --zork mkway/profile.json"):
        assert shell(gtask, command).kind == "refuse", command
    assert shell(gtask, "git restore --staged mkway/profile.json").kind != "refuse"
    assert helpers.shell_writes("git restore -qS src/a.py").paths == []


ENV_DENY = [
    ("H7a", f"env env -S 'cp /tmp/x {L}'"),
    ("H7b", f"timeout 9 env -S 'cp /tmp/x {L}'"),
    ("H7c", f"env --s='cp /tmp/x {L}'"),
    ("H7d", "env -vC mkway/locks cp /tmp/x engine.json"),
    ("H7e", "env --chd mkway/locks cp /tmp/x engine.json"),
    ("H7f", "timeout 9 env -C mkway/locks cp /tmp/x engine.json"),
    ("unknown long option", f"env --zork cp /tmp/x {L}"),
]


def test_every_env_in_the_wrapper_chain_is_read(gtask):
    """Item 8 (H7): only the first `env`, before any other wrapper, was read, with exact option names, so a second
    `env`, an `env` behind `timeout`, a `-vC`/`-…S…` cluster and getopt's prefixes (`--s=`, `--chd`) hid the command
    text or the folder: a lock file was written. Every `env` of the chain is read now; a cluster holding `S` or `C`
    is read; a `--` option that is a prefix of `--split-string` or `--chdir`, or an unknown long option, refuses."""
    import helpers
    for cid, command in ENV_DENY:
        assert shell(gtask, command).kind == "refuse", (cid, command)
    assert [c.cwd for c in helpers.commit_cmd("nice env -vC mkway git commit -m x -- profile.json")] == ["mkway"]
    assert shell(gtask, "env -u HOME --ignore-environment ls").kind != "refuse"


def test_hook_commands_run_python_isolated(tmp_path):
    """R111 (a): every hook command install writes ran `python "<…>/mkway.py" hook …`, so the per-user Python folder
    (user site-packages) and `PYTHONPATH`, which no file permission on the bundle covers, could put other code in
    front of the engine's own modules. Every command is now `python -I -X utf8 "<…>/mkway.py" hook …`, and the start
    line's interpreter check still reads `python` from it."""
    import install
    from _engine import make_profile
    manifest = [{"name": "a", "gate": "a", "group": "edit", "function": "x:check", "event": "PreToolUse",
                 "matcher": "Edit", "timeout": 10, "status": "on", "default_on": True}]
    entries = install.generate_entries(make_profile(), manifest)
    assert entries
    for e in entries:
        assert e["command"].startswith('python -I -X utf8 "${CLAUDE_PROJECT_DIR}/mkway/engine/mkway.py" hook '), e
        assert install.entry_interpreter(e["command"], "mkway") == "python", e


def test_a_commit_in_a_process_substitution_is_read(gtask):
    """Item 1 (H8g): the parser took the first word of `<(…)` as an input file, so `cat <(git commit -m x)` showed
    no commit at all. A process substitution's text is now read as a command substitution is, so its commit is
    checked (here: the staged profile refuses it)."""
    _stage_profile(gtask)
    assert shell(gtask, "cat <(git commit -m x)").kind == "refuse"


# ---- group 2, item 10: the unknown shapes (R95 (1b); H1-H6, M4) -------------------------------------------------------

SHAPE_COMMIT = [  # a commit whose folder or names the shape makes unknown
    ("H1b", "D=mkway #; D=a\ngit commit -m x -- $D/profile.json"),
    ("H2b", "D=mkway; if false; then for x in 1; do :; done; D=a; fi; git commit -m x -- $D/profile.json"),
    ("H3a", "function f { cd mkway; }; f; git commit -m x -- profile.json"),
    ("H3c", "D=a; function g { D=mkway; }; g; git commit -m x -- $D/profile.json"),
    ("H6a", "D=a; { for D in mkway; do :; done; }; git commit -m x -- $D/profile.json"),
    ("M4", "D=a; trap 'D=mkway' DEBUG; git commit -m x -- $D/profile.json"),
]
SHAPE_NAMED = [  # a write the shape hides, in a command that names a closed target
    ("H1a", f"echo hi #; cd mkway\necho {J} > {L}"),
    ("H2a", f"if false; then if :; then :; fi; cd mkway; fi; echo {J} > {L}"),
    ("H3b", f"function f {{ cd mkway/locks; }}; f; echo {J} > engine.json"),
    ("H3d", f"function f {{ cp /tmp/x {L}; }}; f"),
    ("H4a", f"(case x in x) ;; esac; cd mkway); echo {J} > {L}"),
    ("H6b", f"D=a; {{ for D in mkway/locks; do :; done; }}; echo {J} > $D/engine.json"),
]


def test_an_unknown_shape_makes_every_folder_and_name_unknown(gtask):
    """Item 10, R95 (1b) (H1a, H1b, H2a, H2b, H3a-H3d, H4a, H6a, H6b, M4): the tracker follows a `#` comment with a
    separator after it, a `case`, a `function`, a `trap` text and a nested keyword block as if the shell read them as
    it does, so a `cd` that never ran (or a name that was changed) moved the checked folder or a name and a closed
    target was written or committed unseen. A command text (quotes and heredoc bodies blanked) that holds one of those
    shapes now has every folder and name unknown and its writes `everywhere`: a commit it reads refuses
    `commit-folder-unreadable`, and a command that names a closed target refuses `lock-closed-shell`. The replayed
    commit rows name the profile, so literal reach (`lock-closed-shell`) refuses them first; the rows after them name
    no closed target and show the commit's own reason."""
    for cid, command in SHAPE_COMMIT:
        assert _kind(shell(gtask, command)) in ("lock-closed-shell", "commit-folder-unreadable"), (cid, command)
    for cid, command in SHAPE_NAMED:
        assert _kind(shell(gtask, command)) == "lock-closed-shell", (cid, command)
    for command in ("D=src #; D=a\ngit commit -m x -- $D/a.py",
                    "D=src; if false; then for x in 1; do :; done; D=a; fi; git commit -m x -- $D/a.py",
                    "function f { cd src; }; f; git commit -m x -- a.py",
                    "D=a; trap 'D=src' DEBUG; git commit -m x -- $D/a.py"):
        assert _kind(shell(gtask, command)) == "commit-folder-unreadable", command


def test_a_shape_with_no_closed_target_and_no_commit_is_only_logged(gtask):
    """Item 10: «writes everywhere» is the log row when the text names no closed target and no commit; a quoted or
    heredoc-body shape is no shape; a plain comment is none either."""
    (gtask / "src").mkdir()
    for command in ("echo a # b; c", "ls src # list; all", "case x in x) echo hi ;; esac"):
        assert shell(gtask, command).kind == "log", command
    for command in ("echo hi # a plain comment", 'echo "# not a comment; x"', "echo 'case function trap'",
                    "cat > notes.md <<'EOF'\n# note; x\ncase y\nfunction z\nEOF",
                    'git commit -m "fix case and function and trap" -- README.md',
                    "cd src && git commit -m m -- a.py", "echo $#"):
        assert shell(gtask, command).kind not in ("refuse", "log"), command


def test_a_commit_named_inside_a_shape_refuses(gtask):
    """Item 10: a command that names a git commit and holds a shape refuses even when its own paths are literal."""
    for command in ("git commit -m x -- src/a.py # keep; going", "case x in x) git commit -m x -- src/a.py ;; esac",
                    "git commit -m x -- src/a.py; trap ':' EXIT"):
        assert _kind(shell(gtask, command)) in ("commit-folder-unreadable", "command-unparsed"), command


def test_cdpath_with_a_cd_is_command_unparsed(gtask):
    """Item 10 (H5b): `CDPATH=… cd locks` lands in a folder the text does not show, and the write names a bare
    `engine.json` that literal reach cannot see. A command that assigns `CDPATH` and runs `cd` refuses
    `command-unparsed`; `CDPATH` with no `cd` is only a shape (its writes everywhere)."""
    root = gtask.as_posix()
    assert _kind(shell(gtask, f"CDPATH={root}/mkway cd locks; echo {J} > engine.json")) == "command-unparsed"
    assert _kind(shell(gtask, "export CDPATH=/x; cd y")) == "command-unparsed"
    assert _kind(shell(gtask, "CDPATH=/x; echo a")) != "command-unparsed"


SHAPE_TABLE = [  # B19 (O8): one row per shape, each with a name set before it and used after it
    ("hash then separator", "D=mkway #; D=a\necho $D/x"),
    ("hash after separator", "D=mkway;# c\necho $D/x"),
    ("case", "D=mkway; case x in x) ;; esac; echo $D/x"),
    ("function", "D=mkway; function f { :; }; echo $D/x"),
    ("trap", "D=mkway; trap ':' EXIT; echo $D/x"),
    ("process substitution <(", "D=mkway; cat <(echo a); echo $D/x"),
    ("process substitution >(", "D=mkway; echo a > >(cat); echo $D/x"),
    ("CDPATH", "D=mkway; CDPATH=a; echo $D/x"),
    ("then if", "D=mkway; if :; then if :; then :; fi; fi; echo $D/x"),
    ("do for", "D=mkway; while :; do for y in 1; do :; done; done; echo $D/x"),
    ("else while", "D=mkway; if :; then :; else while :; do :; done; fi; echo $D/x"),
    ("elif case", "D=mkway; if :; then :; elif :; then case x in x) ;; esac; fi; echo $D/x"),
    ("brace block", "D=mkway; { { :; }; }; echo $D/x"),
    ("bang subshell", "D=mkway; ! ( : ); echo $D/x"),
]


def test_every_shape_unknowns_folders_and_names_in_the_two_helpers():
    """Item 10, B19 (O8): one row per shape through `folder_track` (every folder None) and `expand_vars` (`$D` stays
    unexpanded). The control (no shape) expands `$D` to `mkway` and tracks a `cd`."""
    import helpers
    control = helpers.expand_vars(helpers.parse("D=mkway; echo $D/x"))
    assert control[-1].words == ["echo", "mkway/x"]
    assert [b for _s, b in helpers.folder_track(helpers.parse("cd a; echo x"), "")] == ["", "a"]
    for name, text in SHAPE_TABLE:
        simples = helpers.parse(text)
        assert helpers.expand_vars(simples)[-1].words == ["echo", "$D/x"], name
        assert all(b is None for _s, b in helpers.folder_track(simples, "")), name
        assert helpers.shell_writes(text).everywhere, name


# ---- group 2, item 11: writes the reader does not enter (H13) --------------------------------------------------------

def test_a_writer_behind_an_unknown_program_or_fed_by_stdin_can_write(gtask):
    """Item 11 (H13a-H13d): `stdbuf -o0 cp …`, `winpty cp …`, a shell fed by a heredoc and `cat <(cp …)` wrote a lock
    file with no log row, because the reader enters no program it does not know and reads a shell only by `-c`. An
    unknown program in front of a known writer, a shell fed by a heredoc or stdin, and a process substitution now make
    the write `capable`; literal reach then refuses a command that names a closed target, and the log row stands
    otherwise."""
    import helpers
    for cid, command in (("H13a", f"stdbuf -o0 cp /tmp/x {L}"),
                         ("H13b", f"winpty cp /tmp/x {L}"),
                         ("H13c", f"bash <<'EOF'\necho {J} > {L}\nEOF"),
                         ("H13d", f"cat <(cp /tmp/x {L})"),
                         ("pipe into a shell", f"echo 'cp /tmp/x {L}' | sh"),
                         ("behind ssh", f"ssh host rm {L}")):
        assert _kind(shell(gtask, command)) == "lock-closed-shell", (cid, command)
    for command in ("stdbuf -o0 cp a b", "winpty tee out.txt", "bash <<'EOF'\necho hi\nEOF", "echo hi | sh", "cat <(echo a)"):
        assert helpers.shell_writes(command).reason == "capable", command
        assert shell(gtask, command).kind == "log", command


def test_the_chain_reset_clears_the_depth_of_the_cd(gtask):
    """Item 12 (H4b): the reset that ends a `cd … &&` chain cleared the folder at the depth of the command that
    followed it, so a `(:)` after the `cd` cleared the subshell's folder and left the root's `mkway`: `(:); false &&
    cd mkway && (:); echo … > <lock file>` was read as a write to `mkway/mkway/…`, though `false` stopped the `cd`. The
    reset now clears the folder at the depth where the chain's `cd` ran, and below. A `)` that closes no `(` is not a
    depth change."""
    import helpers
    command = f"(:); false && cd mkway && (:); echo {J} > {L}"          # H4b
    assert _kind(shell(gtask, command)) == "lock-closed-shell"
    folders = [b for _s, b in helpers.folder_track(helpers.parse("(:); false && cd mkway && (:); echo x"), "")]
    assert folders[-1] is None
    folders = [b for _s, b in helpers.folder_track(helpers.parse("(:); false && cd a && (cd b); echo x"), "")]
    assert folders[-1] is None
    assert [s.depth for s in helpers.parse("x )( y")] == [0, 1]          # the stray `)` changes no depth
    assert [b for _s, b in helpers.folder_track(helpers.parse("(cd a; echo b); echo c"), "")] == ["", None, ""]


def test_a_cd_behind_a_wrapper_makes_the_folder_unknown(gtask):
    """Item 13 (H5a): `timeout 9 cd mkway` runs an external `cd` that changes nothing in the shell, but the tracker
    skipped the wrapper and moved the folder to `mkway`, so the next write was read from the wrong folder. A `cd` (or
    `pushd`, `popd`) behind any wrapper other than `builtin`, `command` or `time` now makes the folder unknown.
    `env cd`, `nice cd` and `nohup cd` (verify first) are the same."""
    import helpers
    for cid, wrapper in (("H5a", "timeout 9"), ("env", "env"), ("nice", "nice"), ("nohup", "nohup"),
                         ("exec", "exec"), ("sudo", "sudo")):
        command = f"{wrapper} cd mkway; echo {J} > {L}"
        assert _kind(shell(gtask, command)) == "lock-closed-shell", (cid, command)
        folders = [b for _s, b in helpers.folder_track(helpers.parse(f"{wrapper} cd a; echo x"), "")]
        assert folders[-1] is None, cid
    for wrapper in ("builtin", "command", "time", "X=1"):  # these run the shell's own `cd`
        folders = [b for _s, b in helpers.folder_track(helpers.parse(f"{wrapper} cd a; echo x"), "")]
        assert folders[-1] == "a", wrapper


def test_a_folder_stack_option_other_than_a_path_makes_the_folder_unknown(gtask):
    """Item 14 (M3): only `-n` and `±N` were read as stack options, so `Push-Location -StackName:s` and `Pop-Location
    -StackName:s` (a named stack) were followed as the one unnamed stack and the folder after them was wrong: a lock
    file was written. Any option other than a path (`-Path`, `-LiteralPath`, and `--`) on `pushd`, `popd`,
    `Push-Location` or `Pop-Location` now makes the folder unknown."""
    import helpers
    command = ("Set-Location mkway/locks; Push-Location -StackName:s ../..; Push-Location src; "
               "Pop-Location -StackName:s; Set-Content engine.json 'x'")          # M3
    assert shell(gtask, command, tool="PowerShell").kind == "refuse"
    for text in ("pushd -q src; echo x", "pushd -P src; echo x", "Push-Location -StackName:s src; echo x",
                 "Push-Location -PassThru src; echo x", "popd -x; echo x"):
        folders = [b for _s, b in helpers.folder_track(helpers.parse(text), "")]
        assert folders[-1] is None, text
    for text in ("pushd src; echo x", "pushd -- src; echo x", "Push-Location -Path src; echo x",
                 "Push-Location -LiteralPath src; echo x", "pushd src; popd; echo x"):
        folders = [b for _s, b in helpers.folder_track(helpers.parse(text), "")]
        assert folders[-1] == ("" if text.endswith("popd; echo x") else "src"), text


def test_a_reader_program_or_a_shell_with_a_script_is_not_capable(gtask):
    """Item 11: the rule is for an unknown program; a program that only reads, a shell given a script file or `-c`
    text, and a quoted writer name are not «can write»."""
    import helpers
    for command in ("echo cp a b", "grep -n cp README.md", "cat notes.md", "ls -l rm", "bash run_tests.sh",
                    "bash -c 'echo hi'", "git log --grep sed", "which cp"):
        assert not helpers.shell_writes(command).everywhere, command
        assert shell(gtask, command).kind not in ("refuse", "log"), command
