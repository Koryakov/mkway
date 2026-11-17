"""Shared helpers in ctx (card MW-003, deliverable 1; spec section 0, defects 2 and 19; D-10).

Table tests, at least 12 shapes each. Synthetic paths and commands only.
"""
import os

import pytest

from _engine import REPO  # noqa: F401  (puts the engine on sys.path)
import helpers

NT = os.name == "nt"
ON_NT = pytest.mark.skipif(not NT, reason="a Windows path form")

HEREDOC_M = "git commit -m \"$(cat <<'EOF'\nCARD-001 subject\n\nbody line\nEOF\n)\" -- a.py"
HEREDOC_F = "git commit -F - -- a.py <<'EOF'\nCARD-003 piped\nEOF"


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "task"
    (r / "src").mkdir(parents=True)
    return r


def _gitbash(path):
    """`C:\\x\\y` -> `/c/x/y`, the Git Bash form."""
    p = str(path).replace("\\", "/")
    return "/" + p[0].lower() + p[2:]


def _fill(template, root):
    """The template with each marker replaced by one form of the fixture root (helper, one replace per marker)."""
    forms = {"<root>": lambda: str(root), "<posix>": lambda: root.as_posix(), "<parent>": lambda: str(root.parent),
             "<gitbash>": lambda: _gitbash(root), "<swap>": lambda: str(root)[0].swapcase() + str(root)[1:],
             "<sep>": lambda: os.sep}
    for marker, form in forms.items():
        if marker in template:
            template = template.replace(marker, form())
    return template


@pytest.mark.parametrize("given, want", [
    pytest.param("src/a.py", "src/a.py", id="plain"),
    pytest.param("./src/a.py", "src/a.py", id="dot-slash"),
    pytest.param("src\\a.py", "src/a.py", id="backslash"),
    pytest.param("<root><sep>src<sep>a.py", "src/a.py", id="native-absolute"),
    pytest.param("<posix>/src/a.py", "src/a.py", id="posix-absolute"),
    pytest.param('"src/a.py"', "src/a.py", id="double-quoted"),
    pytest.param("'src/a.py'", "src/a.py", id="single-quoted"),
    pytest.param("  src/a.py  ", "src/a.py", id="padded"),
    pytest.param("src/../src/a.py", "src/a.py", id="dotdot-inside"),
    pytest.param("../outside.py", None, id="dotdot-outside"),
    pytest.param("<parent><sep>other<sep>a.py", None, id="other-folder"),
    pytest.param("~/x.py", "home/x.py", id="tilde-home"),
    pytest.param("${CLAUDE_PROJECT_DIR}/src/a.py", "src/a.py", id="braced-project-var"),
    pytest.param("$CLAUDE_PROJECT_DIR/src/a.py", "src/a.py", id="bare-project-var"),
    pytest.param("sub/task/src/a.py", "src/a.py", id="top-prefix"),  # written from the repository top (D-10)
    pytest.param("a.py", "a.py", id="bare-name"),  # a bare name stays a bare name, never src/a.py
    pytest.param(".", ".", id="dot"),
    pytest.param("src/", "src", id="trailing-slash"),
    pytest.param('"<root><sep>src<sep>b c.py"', "src/b c.py", id="quoted-space"),
    pytest.param("<gitbash>/src/a.py", "src/a.py", id="nt-gitbash", marks=ON_NT),
    pytest.param("<swap>\\src\\a.py", "src/a.py", id="nt-drive-case", marks=ON_NT),
    pytest.param("<posix>\\src/a.py", "src/a.py", id="nt-mixed-separators", marks=ON_NT),
])
def test_norm_table(root, given, want):
    """Checks: norm gives one repo-relative form with forward slashes for absolute, relative, Git Bash, drive, tilde, repo-top prefix and quoted paths, None outside the root, and never matches by base name (E1)."""
    # a normaliser that keeps backslashes, drops the Git Bash form, joins a bare name to a folder, or lets `..` leave the root fails here
    home = root / "home"
    got = helpers.norm(_fill(given, root), root, top_prefix="sub/task", home=home)
    assert got == want, (given, got, want)


def test_norm_home_outside_root_is_none(root, tmp_path):
    """Checks: tilde expands to the home folder given, and a home outside the root gives None so a user-home target is off (E1)."""
    # a tilde left as a literal folder name inside the root fails here
    assert helpers.norm("~/x.py", root, home=tmp_path / "elsewhere") is None
    assert helpers.norm("~", root, home=root) == "."


@pytest.mark.parametrize("rel, entry, want", [
    pytest.param("src/conftest.py", "conftest.py", False, id="base-name-in-subfolder"),
    pytest.param("conftest.py", "conftest.py", True, id="bare-conftest"),
    pytest.param("src/a.py", "src/", True, id="folder-trailing-slash"),
    pytest.param("src/a.py", "src", True, id="folder-no-slash"),
    pytest.param("srcx/a.py", "src", False, id="folder-prefix-sibling"),
    pytest.param("src/deep/a.py", "src/**", True, id="double-star-deep"),
    pytest.param("src/a.py", "src/*.py", True, id="single-star"),
    pytest.param("src/deep/a.py", "src/*.py", False, id="single-star-deep"),
    pytest.param("docs/x.md", "*.md", True, id="ext-glob"),
    pytest.param("docs/x.md", "**/*.md", True, id="double-star-ext"),
    pytest.param("src/a.py", "src/a.py", True, id="exact"),
    pytest.param("src/a.pyc", "src/a.py", False, id="longer-name"),
    pytest.param("SRC/A.py", "src/a.py", True, id="nt-case-insensitive", marks=ON_NT),
])
def test_matches_never_by_base_name(root, rel, entry, want):
    """Checks: an entry matches by repo path, an exact path, a folder with or without a trailing slash, or a glob, and never by base name (E1, defect 1: another folder's conftest.py)."""
    # a match on the last path part only fails here
    assert helpers.matches(rel, entry) is want, (rel, entry)


def _c(cmd, **kw):
    return helpers.commit_cmd(cmd, **kw)


@pytest.mark.parametrize("cmd, message, paths, all_, include", [
    pytest.param('git commit -m "CARD-001 x" -- a.py b.py', "CARD-001 x", ["a.py", "b.py"], False, False, id="two-paths"),
    pytest.param("git commit -m msg a.py", "msg", ["a.py"], False, False, id="path-as-argument"),
    pytest.param("git commit -am msg", "msg", [], True, False, id="am-flag"),
    pytest.param("git commit --all -m msg", "msg", [], True, False, id="all-flag"),
    pytest.param("git commit -F msg.txt -- a.py", "CARD-002 from a file\n", ["a.py"], False, False, id="file-option"),
    pytest.param("git commit --file=msg.txt", "CARD-002 from a file\n", [], False, False, id="file-equals"),
    pytest.param(HEREDOC_M, "CARD-001 subject\n\nbody line", ["a.py"], False, False, id="heredoc-message"),
    pytest.param(HEREDOC_F, "CARD-003 piped", ["a.py"], False, False, id="heredoc-piped-file"),
    pytest.param("git -C sub commit -m x -- a.py", "x", ["a.py"], False, False, id="dash-c-folder"),
    pytest.param("git status && git commit -m x -- a.py", "x", ["a.py"], False, False, id="chained"),
    pytest.param("git commit -m a -m b -- x.py", "a\n\nb", ["x.py"], False, False, id="two-messages"),
    pytest.param("git commit -i -m x -- a.py", "x", ["a.py"], False, True, id="include-short"),
    pytest.param("git commit --include -m x a.py", "x", ["a.py"], False, True, id="include-long"),
    pytest.param('git commit -m"x" a.py', "x", ["a.py"], False, False, id="glued-message"),
    pytest.param("git --no-optional-locks -c user.name=x commit -m y z.py", "y", ["z.py"], False, False, id="global-options"),
    pytest.param("git commit --message=x --author='A <a@b>' -- q.py", "x", ["q.py"], False, False, id="message-equals-author"),
])
def test_commit_cmd_table(tmp_path, cmd, message, paths, all_, include):
    """Checks: commit_cmd finds each commit in a shell command with its message, explicit paths, all and include flags, and sees no commit inside echo, log or a longer word (E2)."""
    # a reader that sees a commit inside echo, misses a heredoc message, or takes an option value for a path fails here;
    # the lines after the row check are the edge cases of the same table and run in every case
    (tmp_path / "msg.txt").write_text("CARD-002 from a file\n", encoding="utf-8")
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


@pytest.mark.parametrize("cmd, shell, want", [
    pytest.param("echo hi > out.txt", "bash", ["out.txt"], id="redirect"),
    pytest.param("echo hi >> logs/a.txt", "bash", ["logs/a.txt"], id="append"),
    pytest.param("echo hi 1>x.txt", "bash", ["x.txt"], id="fd-redirect"),
    pytest.param("cat a | tee b c", "bash", ["b", "c"], id="tee"),
    pytest.param("cat a | tee -a b", "bash", ["b"], id="tee-append"),
    pytest.param("cp a.txt b.txt", "bash", ["b.txt"], id="cp"),
    pytest.param("cp -r src dst/", "bash", ["dst/src"], id="cp-folder"),  # MW-003 close-fix 15: a folder destination is <dest>/<basename(src)>
    pytest.param("cp -t dir a b", "bash", ["dir/a", "dir/b"], id="cp-t"),  # MW-003 close-fix 15: `-t` names a folder destination
    pytest.param("mv a b", "bash", ["a", "b"], id="mv"),
    pytest.param("python -c \"open('x.txt','w').write('1')\"", "bash", ["x.txt"], id="py-open-write"),
    pytest.param("python -c \"print(open('x.txt').read())\"", "bash", [], id="py-open-read"),
    pytest.param("python -c \"import os; os.remove(p)\"", "bash", "*", id="py-os-remove"),
    pytest.param("python -c \"from pathlib import Path; Path('y.txt').write_text('1')\"", "bash", ["y.txt"], id="py-pathlib-write"),
    pytest.param("python -c \"import sys; sys.path.insert(0, 'e'); import m\"", "bash", "*", id="py-sys-path"),
    pytest.param("python -c 'syntax error ('", "bash", "*", id="py-syntax-error"),
    pytest.param("python - <<'EOF'\nopen('q.txt', 'w')\nEOF", "bash", ["q.txt"], id="py-stdin-heredoc"),
    pytest.param('echo "unbalanced', "bash", "*", id="unbalanced-quote"),
    pytest.param("eval \"x\"", "bash", "*", id="eval"),
    pytest.param("python -m pytest -q tests", "bash", [], id="pytest-run"),
    pytest.param("python script.py --flag", "bash", [], id="py-script"),
    pytest.param("git status && git log -1", "bash", [], id="git-reads"),
    pytest.param("ls 2>&1 > /dev/null", "bash", [], id="dev-null"),
    pytest.param("rm -f a b", "bash", ["a", "b"], id="rm"),
    pytest.param("touch a", "bash", ["a"], id="touch"),
    pytest.param("mkdir -p d/e", "bash", ["d/e"], id="mkdir"),
    pytest.param("sed -i 's/a/b/' f.txt", "bash", ["f.txt"], id="sed-in-place"),
    pytest.param("bash -c \"echo x > y\"", "bash", ["y"], id="bash-c"),
    pytest.param("echo $(echo x > z)", "bash", ["z"], id="command-substitution"),
    pytest.param("cat <<'EOF' > f.md\nbody > not.txt\nEOF", "bash", ["f.md"], id="heredoc-body"),
    pytest.param("git checkout -- a.txt", "bash", ["a.txt"], id="checkout-path"),
    pytest.param("git restore b.txt", "bash", ["b.txt"], id="restore-path"),
    pytest.param("git reset --hard", "bash", "*", id="reset-hard"),
    pytest.param("git checkout main", "bash", "*", id="checkout-branch"),
    pytest.param("dd if=a of=b", "bash", ["b"], id="dd"),
    pytest.param("ln -s a b", "bash", ["b"], id="ln"),
    pytest.param("Set-Content -Path x.txt -Value 1", "powershell", ["x.txt"], id="ps-set-content-path"),
    pytest.param("Set-Content x.txt 1", "powershell", ["x.txt"], id="ps-set-content-positional"),
    pytest.param("Get-Content a | Out-File b.txt", "powershell", ["b.txt"], id="ps-out-file-pipe"),
    pytest.param("Out-File -FilePath c.txt -InputObject 1", "powershell", ["c.txt"], id="ps-out-file-path"),
    pytest.param("Add-Content -Path d.txt -Value 1", "powershell", ["d.txt"], id="ps-add-content"),
    pytest.param("Remove-Item e.txt", "powershell", ["e.txt"], id="ps-remove-item"),
    pytest.param("Copy-Item a.txt -Destination f.txt", "powershell", ["f.txt"], id="ps-copy-item"),
    pytest.param("echo 1 > mkway\\locks\\x.json", "powershell", ["mkway/locks/x.json"], id="ps-redirect-backslash"),
    pytest.param("Get-ChildItem", "powershell", [], id="ps-get-childitem"),
])
def test_shell_writes_table(cmd, shell, want):
    """Checks: shell_writes lists the paths a command may write, redirects, tee, cp, mv, python with open, Set-Content, Out-File and the other write shapes, a command it cannot parse writes everywhere, and a known program with no write shape writes nothing (E3)."""
    # a redirect target missed, a heredoc body parsed as a command, or a parse failure taken as «no write» fails here
    assert _w(cmd, shell) == want, (cmd, _w(cmd, shell), want)


@pytest.mark.parametrize("cmd, shell, want", [
    pytest.param("python mkway/engine/mkway.py lock open x", "bash", [["lock", "open", "x"]], id="python-path"),
    pytest.param('py -3 "C:/t/mkway/engine/mkway.py" gate off a', "bash", [["gate", "off", "a"]], id="py-launcher"),
    pytest.param("git status && python mkway/engine/mkway.py card open CARD-001", "bash", [["card", "open", "CARD-001"]], id="and-chain"),
    pytest.param("cd mkway/engine; python mkway.py install --from x", "bash", [["install", "--from", "x"]], id="semicolon-chain"),
    pytest.param("python mkway.py card set CARD-001 open", "bash", [["card", "set", "CARD-001", "open"]], id="root-launcher"),
    pytest.param("X=1 python mkway/engine/mkway.py lock open x", "bash", [["lock", "open", "x"]], id="env-prefix"),
    pytest.param("python3 -u mkway/engine/mkway.py lock open x", "bash", [["lock", "open", "x"]], id="python3-flag"),
    pytest.param('bash -c "python mkway/engine/mkway.py lock open x"', "bash", [["lock", "open", "x"]], id="bash-c"),
    pytest.param("./mkway/engine/mkway.py card close CARD-002", "bash", [["card", "close", "CARD-002"]], id="direct-script"),
    pytest.param("echo mkway.py lock open", "bash", [], id="echo-of-the-name"),
    pytest.param("python -m pytest mkway.py", "bash", [], id="pytest-argument"),
    pytest.param("python mkway/engine/mkway.py card list | head", "bash", [["card", "list"]], id="pipe"),
    pytest.param("python a.py; python b/mkway.py card resync", "bash", [["card", "resync"]], id="second-command"),
    pytest.param("env python mkway/engine/mkway.py upgrade", "bash", [["upgrade"]], id="env-command"),
    pytest.param("& python .\\mkway\\engine\\mkway.py card close CARD-002", "powershell", [["card", "close", "CARD-002"]], id="ps-call-operator"),
    pytest.param("python mkway\\engine\\mkway.py lock open x; Get-ChildItem", "powershell", [["lock", "open", "x"]], id="ps-chain"),
])
def test_mkway_calls_table(cmd, shell, want):
    """Checks: mkway_calls finds every call of the engine's command line in a shell command in any spelling and returns the arguments after mkway.py, and takes an echo of the name for no call (E4)."""
    # a chained or re-spelled owner-only call that slips past, or an echo of the name taken as a call, fails here:
    # a Python or py interpreter with a path, the root launcher, && and ; chains, bash -c, an env prefix, PowerShell
    assert helpers.mkway_calls(cmd, shell=shell) == want, cmd
