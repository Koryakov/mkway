"""Shared helpers in ctx (card MW-003, deliverable 1; spec section 0, defects 2 and 19; D-10).

Table tests, at least 12 shapes each. Synthetic paths and commands only.
"""
import os

import pytest

from _engine import REPO  # noqa: F401  (puts the engine on sys.path)
import helpers

NT = os.name == "nt"


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "task"
    (r / "src").mkdir(parents=True)
    return r


def _gitbash(path):
    """`C:\\x\\y` -> `/c/x/y`, the Git Bash form."""
    p = str(path).replace("\\", "/")
    return "/" + p[0].lower() + p[2:]


def test_norm_table(root):
    """E1: `norm` gives one repo-relative form with forward slashes for absolute, relative, `/c/...`, `C:\\...`,
    `~`, repo-top prefix and quoted paths; outside the root is None; it never matches by base name.
    Catches: a normaliser that keeps backslashes, drops the Git Bash form, joins a bare name to a folder, or lets
    `..` leave the root."""
    home = root / "home"
    rows = [
        ("src/a.py", "src/a.py"),
        ("./src/a.py", "src/a.py"),
        ("src\\a.py", "src/a.py"),
        (str(root / "src" / "a.py"), "src/a.py"),
        (root.as_posix() + "/src/a.py", "src/a.py"),
        ('"src/a.py"', "src/a.py"),
        ("'src/a.py'", "src/a.py"),
        ("  src/a.py  ", "src/a.py"),
        ("src/../src/a.py", "src/a.py"),
        ("../outside.py", None),
        (str(root.parent / "other" / "a.py"), None),
        ("~/x.py", "home/x.py"),
        ("${CLAUDE_PROJECT_DIR}/src/a.py", "src/a.py"),
        ("$CLAUDE_PROJECT_DIR/src/a.py", "src/a.py"),
        ("sub/task/src/a.py", "src/a.py"),  # written from the repository top (D-10)
        ("a.py", "a.py"),  # a bare name stays a bare name, never src/a.py
        (".", "."),
        ("src/", "src"),
        ('"' + str(root / "src" / "b c.py") + '"', "src/b c.py"),
    ]
    if NT:
        rows += [
            (_gitbash(root / "src" / "a.py"), "src/a.py"),
            (str(root)[0].swapcase() + str(root)[1:] + "\\src\\a.py", "src/a.py"),
            (str(root).replace("\\", "/") + "\\src/a.py", "src/a.py"),
        ]
    assert len(rows) >= 12
    for given, want in rows:
        got = helpers.norm(given, root, top_prefix="sub/task", home=home)
        assert got == want, (given, got, want)


def test_norm_home_outside_root_is_none(root, tmp_path):
    """E1: `~` expands to the home folder given; a home outside the root gives None (a user-home target is off).
    Catches: a `~` left as a literal folder name inside the root."""
    assert helpers.norm("~/x.py", root, home=tmp_path / "elsewhere") is None
    assert helpers.norm("~", root, home=root) == "."


def test_matches_never_by_base_name(root):
    """E1: an entry matches by repo path: an exact path, a folder (with or without a trailing `/`), or a glob;
    never by base name (defect 1: another folder's `conftest.py`).
    Catches: a match on the last path part only."""
    rows = [
        ("src/conftest.py", "conftest.py", False),
        ("conftest.py", "conftest.py", True),
        ("src/a.py", "src/", True),
        ("src/a.py", "src", True),
        ("srcx/a.py", "src", False),
        ("src/deep/a.py", "src/**", True),
        ("src/a.py", "src/*.py", True),
        ("src/deep/a.py", "src/*.py", False),
        ("docs/x.md", "*.md", True),
        ("docs/x.md", "**/*.md", True),
        ("src/a.py", "src/a.py", True),
        ("src/a.pyc", "src/a.py", False),
    ]
    if NT:
        rows.append(("SRC/A.py", "src/a.py", True))
    for rel, entry, want in rows:
        assert helpers.matches(rel, entry) is want, (rel, entry)


def _c(cmd, **kw):
    return helpers.commit_cmd(cmd, **kw)


def test_commit_cmd_table(tmp_path):
    """E2: `commit_cmd` finds each commit in a shell command: its message (`-m`, `-F`, `--file`, a heredoc, a
    `$(cat <<EOF)` body), its explicit paths (after `--`, or as arguments), `-a`/`--all` and `-i`/`--include`.
    Catches: a reader that sees a commit inside `echo`, misses a heredoc message, or takes an option value for a
    path."""
    (tmp_path / "msg.txt").write_text("CARD-002 from a file\n", encoding="utf-8")
    heredoc_m = "git commit -m \"$(cat <<'EOF'\nCARD-001 subject\n\nbody line\nEOF\n)\" -- a.py"
    heredoc_f = "git commit -F - -- a.py <<'EOF'\nCARD-003 piped\nEOF"
    rows = [
        ('git commit -m "CARD-001 x" -- a.py b.py', "CARD-001 x", ["a.py", "b.py"], False, False),
        ("git commit -m msg a.py", "msg", ["a.py"], False, False),
        ("git commit -am msg", "msg", [], True, False),
        ("git commit --all -m msg", "msg", [], True, False),
        ("git commit -F msg.txt -- a.py", "CARD-002 from a file\n", ["a.py"], False, False),
        ("git commit --file=msg.txt", "CARD-002 from a file\n", [], False, False),
        (heredoc_m, "CARD-001 subject\n\nbody line", ["a.py"], False, False),
        (heredoc_f, "CARD-003 piped", ["a.py"], False, False),
        ("git -C sub commit -m x -- a.py", "x", ["a.py"], False, False),
        ("git status && git commit -m x -- a.py", "x", ["a.py"], False, False),
        ("git commit -m a -m b -- x.py", "a\n\nb", ["x.py"], False, False),
        ("git commit -i -m x -- a.py", "x", ["a.py"], False, True),
        ("git commit --include -m x a.py", "x", ["a.py"], False, True),
        ('git commit -m"x" a.py', "x", ["a.py"], False, False),
        ("git --no-optional-locks -c user.name=x commit -m y z.py", "y", ["z.py"], False, False),
        ("git commit --message=x --author='A <a@b>' -- q.py", "x", ["q.py"], False, False),
    ]
    assert len(rows) >= 12
    for cmd, message, paths, all_, include in rows:
        (got,) = _c(cmd, root=tmp_path)
        assert (got.message, got.paths, got.all, got.include) == (message, paths, all_, include), cmd
    assert _c("git log --grep commit") == []
    assert _c("echo git commit -m x") == []
    assert _c("git commitx -m x") == []
    (c,) = _c("git -C sub commit -m x -- a.py")
    assert c.cwd == "sub"
    (c,) = _c("git commit --allow-empty -m x")
    assert c.allow_empty is True
    assert len(_c("git commit -m a -- x && git commit -m b -- y")) == 2
    (c,) = _c("git commit -m 'x' -- a.py; git status", shell="powershell")
    assert c.paths == ["a.py"]


def _w(cmd, shell="bash"):
    w = helpers.shell_writes(cmd, shell=shell)
    return "*" if w.everywhere else sorted(w.paths)


def test_shell_writes_table():
    """E3: `shell_writes` lists the paths a command may write: redirects, `tee`, `cp`, `mv`, `python -c` with
    `open(`, `Set-Content`, `Out-File` and the other write shapes; a command it cannot parse writes everywhere
    (`*`); a known program with no write shape writes nothing.
    Catches: a redirect target missed, a heredoc body parsed as a command, or a parse failure taken as «no
    write»."""
    rows = [
        ("echo hi > out.txt", ["out.txt"]),
        ("echo hi >> logs/a.txt", ["logs/a.txt"]),
        ("echo hi 1>x.txt", ["x.txt"]),
        ("cat a | tee b c", ["b", "c"]),
        ("cat a | tee -a b", ["b"]),
        ("cp a.txt b.txt", ["b.txt"]),
        ("cp -r src dst/", ["dst/src"]),  # MW-003 close-fix 15: a folder destination is <dest>/<basename(src)>
        ("cp -t dir a b", ["dir/a", "dir/b"]),  # MW-003 close-fix 15: `-t` names a folder destination
        ("mv a b", ["a", "b"]),
        ("python -c \"open('x.txt','w').write('1')\"", ["x.txt"]),
        ("python -c \"print(open('x.txt').read())\"", []),
        ("python -c \"import os; os.remove(p)\"", "*"),
        ("python -c \"from pathlib import Path; Path('y.txt').write_text('1')\"", ["y.txt"]),
        ("python -c \"import sys; sys.path.insert(0, 'e'); import m\"", "*"),
        ("python -c 'syntax error ('", "*"),
        ("python - <<'EOF'\nopen('q.txt', 'w')\nEOF", ["q.txt"]),
        ('echo "unbalanced', "*"),
        ("eval \"x\"", "*"),
        ("python -m pytest -q tests", []),
        ("python script.py --flag", []),
        ("git status && git log -1", []),
        ("ls 2>&1 > /dev/null", []),
        ("rm -f a b", ["a", "b"]),
        ("touch a", ["a"]),
        ("mkdir -p d/e", ["d/e"]),
        ("sed -i 's/a/b/' f.txt", ["f.txt"]),
        ("bash -c \"echo x > y\"", ["y"]),
        ("echo $(echo x > z)", ["z"]),
        ("cat <<'EOF' > f.md\nbody > not.txt\nEOF", ["f.md"]),
        ("git checkout -- a.txt", ["a.txt"]),
        ("git restore b.txt", ["b.txt"]),
        ("git reset --hard", "*"),
        ("git checkout main", "*"),
        ("dd if=a of=b", ["b"]),
        ("ln -s a b", ["b"]),
    ]
    for cmd, want in rows:
        assert _w(cmd) == want, (cmd, _w(cmd), want)
    ps = [
        ("Set-Content -Path x.txt -Value 1", ["x.txt"]),
        ("Set-Content x.txt 1", ["x.txt"]),
        ("Get-Content a | Out-File b.txt", ["b.txt"]),
        ("Out-File -FilePath c.txt -InputObject 1", ["c.txt"]),
        ("Add-Content -Path d.txt -Value 1", ["d.txt"]),
        ("Remove-Item e.txt", ["e.txt"]),
        ("Copy-Item a.txt -Destination f.txt", ["f.txt"]),
        ("echo 1 > mkway\\locks\\x.json", ["mkway/locks/x.json"]),
        ("Get-ChildItem", []),
    ]
    for cmd, want in ps:
        assert _w(cmd, "powershell") == want, (cmd, _w(cmd, "powershell"), want)
    assert len(rows) + len(ps) >= 12


def test_mkway_calls_table():
    """E4: `mkway_calls` finds every call of the engine's command line in a shell command, in any spelling: a
    Python or `py` interpreter with a path, the root launcher, `&&` and `;` chains, `bash -c`, an env prefix,
    PowerShell. It returns the arguments after `mkway.py`.
    Catches: a chained or re-spelled owner-only call that slips past, or an `echo` of the name taken as a call."""
    rows = [
        ("python mkway/engine/mkway.py lock open x", [["lock", "open", "x"]]),
        ('py -3 "C:/t/mkway/engine/mkway.py" gate off a', [["gate", "off", "a"]]),
        ("git status && python mkway/engine/mkway.py card open CARD-001", [["card", "open", "CARD-001"]]),
        ("cd mkway/engine; python mkway.py install --from x", [["install", "--from", "x"]]),
        ("python mkway.py card set CARD-001 open", [["card", "set", "CARD-001", "open"]]),
        ("X=1 python mkway/engine/mkway.py lock open x", [["lock", "open", "x"]]),
        ("python3 -u mkway/engine/mkway.py lock open x", [["lock", "open", "x"]]),
        ('bash -c "python mkway/engine/mkway.py lock open x"', [["lock", "open", "x"]]),
        ("./mkway/engine/mkway.py card close CARD-002", [["card", "close", "CARD-002"]]),
        ("echo mkway.py lock open", []),
        ("python -m pytest mkway.py", []),
        ("python mkway/engine/mkway.py card list | head", [["card", "list"]]),
        ("python a.py; python b/mkway.py card resync", [["card", "resync"]]),
        ("env python mkway/engine/mkway.py upgrade", [["upgrade"]]),
    ]
    for cmd, want in rows:
        assert helpers.mkway_calls(cmd) == want, cmd
    ps = [
        ("& python .\\mkway\\engine\\mkway.py card close CARD-002", [["card", "close", "CARD-002"]]),
        ("python mkway\\engine\\mkway.py lock open x; Get-ChildItem", [["lock", "open", "x"]]),
    ]
    for cmd, want in ps:
        assert helpers.mkway_calls(cmd, shell="powershell") == want, cmd
