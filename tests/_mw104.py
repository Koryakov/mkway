"""Card MW-104 helpers for the upgrade tests (shell and e2e). Not a test module. Synthetic data only.

`hermetic(monkeypatch, tmp_path)` is the body of the autouse fixture of every MW-104 test module: the upgrade folder, APPDATA,
XDG_CONFIG_HOME, the home, the temp folders and git's own config all point under tmp_path, so even a default can only land
there (owner 13.11: no reading of a real repo, no real installation).

`World` builds, under tmp_path, an engine repository (a stub engine whose `install` and `ledger add` write small files and
print the real line shapes) and a customer repository holding one task root, and runs the upgrade shell on them. The e2e
builds its engine repository from the files of the running checkout on disk (`real_engine`)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import _engine

REPO = _engine.REPO
CMD_LIST = ["python", "-m", "pytest"]
CMD_TEXT = "python -m pytest"
NARROW_CMD = ["python", "-m", "pytest", "tests/test_meta_cards.py", "tests/test_register.py"]
RELEASE = {"branch": "main", "full_command": CMD_LIST, "narrow_paths": [["cards/**", "cards/REGISTER.md", "CHANGELOG.md"]],
           "narrow_command": NARROW_CMD}
GIT_NAMES = {"GIT_AUTHOR_NAME": "mkway-test", "GIT_AUTHOR_EMAIL": "mkway-test", "GIT_COMMITTER_NAME": "mkway-test",
             "GIT_COMMITTER_EMAIL": "mkway-test"}


def hermetic(monkeypatch, tmp_path):
    """Point every folder an upgrade could read or write at tmp_path (the autouse fixture of the MW-104 modules)."""
    folders = {"APPDATA": "appdata", "XDG_CONFIG_HOME": "xdg", "HOME": "home", "USERPROFILE": "home", "TEMP": "tmp",
               "TMP": "tmp", "TMPDIR": "tmp"}
    for name, folder in folders.items():
        path = tmp_path / "hermetic" / folder
        path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(name, str(path))
    monkeypatch.setenv("MKWAY_UPGRADE_DIR", str(tmp_path / "upgrade-dir"))
    (tmp_path / "hermetic" / "gitconfig").write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "hermetic" / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    for name, value in GIT_NAMES.items():
        monkeypatch.setenv(name, value)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "hermetic" / "tmp"))


def env_for_children(extra=None):
    """The environment of a child process: the current one without the session marker (the owner's terminal)."""
    env = {k: v for k, v in os.environ.items() if k.upper() != "CLAUDECODE"}
    env.update(extra or {})
    return env


def sh(args, cwd, env=None, check=True):
    """Run a program in `cwd`; returns the completed process (text, utf-8)."""
    proc = subprocess.run([str(a) for a in args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env or env_for_children(), timeout=120)
    if check and proc.returncode != 0:
        raise AssertionError(f"{args} failed in {cwd}: {proc.stdout}\n{proc.stderr}")
    return proc


def git(repo, *args, check=True):
    return sh(["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args], repo, check=check)


def out(repo, *args):
    return git(repo, *args).stdout.strip()


def lines_of(path):
    path = Path(path)
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []


# ---- the stub engine ------------------------------------------------------------------------------------------------------

STUB = r'''
import json
import os
import subprocess
import sys
from pathlib import Path

MODE = "@MODE@"
MARK = "@MARK@"
argv = sys.argv[1:]


def opt(name):
    return argv[argv.index(name) + 1] if name in argv else None


here = Path(__file__).resolve()
if argv[:3] == ["ledger", "add", "--help"]:
    print("usage: mkway ledger add --card C --topic T --quote Q --source S" + ("" if MODE == "nobyledger" else " --by BY"))
    sys.exit(0)
if argv[:2] == ["ledger", "add"]:
    if MODE == "ledgerfail":
        sys.stderr.write("ledger broke\n")
        sys.exit(1)
    root = Path(opt("--root"))
    row = {"card": opt("--card"), "topic": opt("--topic"), "quote": opt("--quote"), "source": opt("--source"),
           "by": opt("--by"), "claudecode": "CLAUDECODE" in os.environ}
    ledger = root / "mkway" / "ledger" / "ledger.md"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    print("ledger row written")
    sys.exit(0)
if argv[:1] == ["install"]:
    src, ref, root = opt("--from"), opt("--ref"), Path(opt("--root"))
    if MODE == "fail":
        (root / "mkway").mkdir(parents=True, exist_ok=True)
        (root / "mkway" / "PARTIAL.txt").write_text("half", encoding="utf-8")
        sys.stderr.write("install broke\n")
        sys.exit(3)
    if MODE == "hang":
        import time
        time.sleep(30)
    semver = subprocess.run(["git", "-C", src, "show", ref + ":VERSION"], capture_output=True, text=True,
                            check=True).stdout.strip()
    bundle = root / "mkway"
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}, "ref": ref}) + "\n", encoding="utf-8")
    (bundle / "engine").mkdir(parents=True, exist_ok=True)
    (bundle / "state").mkdir(parents=True, exist_ok=True)
    (bundle / ".gitignore").write_text("state/\n", encoding="utf-8")
    (bundle / ".gitattributes").write_text("engine/** -text\n", encoding="utf-8")
    (bundle / "mkway.lock").write_text(json.dumps({"version": "x", "semver": semver, "source_sha": ref}) + "\n",
                                       encoding="utf-8")
    (bundle / "engine" / "mkway.py").write_text(here.read_text(encoding="utf-8"), encoding="utf-8")
    (bundle / "MARK.txt").write_text(MARK, encoding="utf-8")
    (bundle / "state" / "ARGS.json").write_text(json.dumps({"argv": argv, "claudecode": "CLAUDECODE" in os.environ,
                                                           "cwd": os.getcwd()}), encoding="utf-8")
    prefix = ""
    profile = bundle / "profile.json"
    if profile.is_file():
        prefix = (json.loads(profile.read_text(encoding="utf-8")).get("commit") or {}).get("message_prefix") or ""
    paths = [".claude/settings.json", "mkway/.gitignore", "mkway/.gitattributes", "mkway/mkway.lock", "mkway/engine"]
    if MODE == "unsafe":
        paths.append("../escape.txt")
    message = f"mkway {semver}: install"
    if prefix:
        message = prefix + " " + message
    if MODE == "badmsg":
        message = "fix things"
    print("copy: 1 files")
    if MODE != "noline":
        text = " ".join(paths)
        git_root = 'git -C "' + str(root).replace("\\", "/") + '"'
        print(git_root + " add " + text + "; " + git_root + ' commit -m "' + message + '" -- ' + text)
    sys.exit(0)
sys.stderr.write("stub: unknown command\n")
sys.exit(2)
'''


def stub_text(mode="ok", mark="head"):
    return STUB.replace("@MODE@", mode).replace("@MARK@", mark)


class World:
    """An engine repository with a stub engine, and a customer repository with one task root named `app`."""

    def __init__(self, tmp_path, release=None, branch="main"):
        self.tmp = tmp_path
        self.engine = tmp_path / "engine-repo"
        self.target = tmp_path / "customer"
        self.root = self.target / "app"
        self.cfg = tmp_path / "upgrade-dir"
        self.green_file = self.cfg / "green.jsonl"
        self.grant_file = self.cfg / "policy.json"
        self.log_file = self.cfg / "updates.jsonl"
        self.release = dict(RELEASE, branch=branch) if release is None else release
        self.shas = {}
        self.engine.mkdir(parents=True)
        git(self.engine, "init", "-q", "-b", branch)
        self.cfg.mkdir(parents=True, exist_ok=True)

    # engine side
    def move_cfg(self, path):
        """Use another upgrade folder (the grant, the green record and the log live in it)."""
        self.cfg = Path(path)
        self.green_file, self.grant_file, self.log_file = (self.cfg / "green.jsonl", self.cfg / "policy.json",
                                                           self.cfg / "updates.jsonl")

    def commit(self, name, *, version="0.1.0", mode="ok", mark="head", files=None, message=None, tag=None, release=True,
               delete=(), untrack=()):
        """One engine commit; `files` maps a path to its text; `delete` lists paths removed; `untrack` lists paths dropped
        from the index but kept on disk; `tag` makes a lightweight tag."""
        (self.engine / "engine").mkdir(exist_ok=True)
        (self.engine / "engine" / "mkway.py").write_text(stub_text(mode, mark), encoding="utf-8", newline="\n")
        (self.engine / "VERSION").write_text(version + "\n", encoding="utf-8", newline="\n")
        if release is True:
            (self.engine / "release.json").write_text(json.dumps(self.release, indent=2) + "\n", encoding="utf-8",
                                                      newline="\n")
        for rel, text in (files or {}).items():
            path = self.engine / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        for rel in delete:
            git(self.engine, "rm", "-q", "-f", rel)
        for rel in untrack:
            git(self.engine, "rm", "-q", "--cached", "-f", rel)
        git(self.engine, "add", "-A")
        git(self.engine, "commit", "-q", "--allow-empty", "-m", message or name)
        sha = out(self.engine, "rev-parse", "HEAD")
        self.shas[name] = sha
        if tag:
            git(self.engine, "tag", tag)
        return sha

    def sha(self, name):
        return self.shas[name]

    def green(self, sha, kind="full", frm=None, command=None, repo=None, into=None, extra=None):
        """Append one green record row the way the owner-only command would (the e2e uses the real command)."""
        row = {"kind": kind, "repo": repo or str(self.engine.resolve()), "into": into or self.release["branch"],
               "branch": "feature", "from": frm or ("0" * 40), "sha": self.shas.get(sha, sha),
               "command": command or CMD_TEXT, "rule": None, "seconds": 1.0, "time": "2026-11-14T10:00:00Z",
               "version": "0.1.0"}
        row.update(extra or {})
        self.cfg.mkdir(parents=True, exist_ok=True)
        with open(self.green_file, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row) + "\n")

    # customer side
    def install_at(self, name, *, profile=None, roots=("app",)):
        """The customer repository with each root installed at the engine commit `name` by the stub's own install."""
        if not (self.target / ".git").exists():
            git(self.target.parent, "init", "-q", "-b", "main", str(self.target))
        sha = self.shas[name]
        script = self.tmp / f"stub-{name}.py"
        script.write_text(out(self.engine, "show", sha + ":engine/mkway.py") + "\n", encoding="utf-8")
        for root_name in roots:
            root = self.target / root_name
            (root / "mkway" / "ledger").mkdir(parents=True, exist_ok=True)
            (root / "mkway" / "ledger" / "ledger.md").write_text("# ledger\n", encoding="utf-8", newline="\n")
            if profile is not None:
                (root / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
            sh([sys.executable, script, "install", "--from", self.engine, "--ref", sha, "--root", root], root)
        git(self.target, "add", "-A")
        git(self.target, "commit", "-q", "--allow-empty", "-m", "customer install " + name)

    def lock(self, root="app"):
        return json.loads((self.target / root / "mkway" / "mkway.lock").read_text(encoding="utf-8"))

    def set_lock(self, root="app", **fields):
        path = self.target / root / "mkway" / "mkway.lock"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(fields)
        path.write_text(json.dumps(data) + "\n", encoding="utf-8")
        git(self.target, "add", "-A")
        git(self.target, "commit", "-q", "-m", "edit the lock")

    def grant(self, **over):
        """The owner's grant file; returns its path."""
        data = {"target": str(self.target), "root": "app"}
        data.update(over)
        data = {k: v for k, v in data.items() if v is not None}
        self.cfg.mkdir(parents=True, exist_ok=True)
        self.grant_file.write_text(json.dumps(data), encoding="utf-8")
        return self.grant_file

    # running
    def env(self, **extra):
        env = dict(os.environ)
        env["CLAUDECODE"] = "1"  # the upgrade must strip it from every engine command it runs
        env.update(extra)
        return env

    def run(self, *, root=None, target=None, dry_run=False, from_head=False, env=None, engine_file=None):
        """The upgrade shell on this world: (exit code, result dict)."""
        import upgrade
        return upgrade.run_upgrade(target=str(target) if target is not None else str(self.target), root=root,
                                   dry_run=dry_run, from_head=from_head, env=env or self.env(),
                                   engine_file=engine_file or (self.engine / "engine" / "mkway.py"))

    def log(self):
        return lines_of(self.log_file)

    def customer_head(self):
        return out(self.target, "rev-parse", "HEAD")

    def customer_subjects(self, count=3):
        return out(self.target, "log", f"-{count}", "--format=%s").splitlines()

    def files_of(self, rev):
        return out(self.target, "show", "--name-only", "--format=", rev).splitlines()

    def tree_state(self):
        """Everything the upgrade must leave alone on a refusal: the customer HEAD, its status, the grant and the green record."""
        return (self.customer_head(), out(self.target, "status", "--porcelain", "--untracked-files=all"),
                self.grant_file.read_bytes() if self.grant_file.is_file() else None,
                self.green_file.read_bytes() if self.green_file.is_file() else None)

    def standard(self, *, tags=True, profile=None):
        """The usual setup: commit A (v0.0.1) installed in the customer repository, commit B (v0.0.2) green; a grant."""
        a = self.commit("A", version="0.1.0", tag="v0.0.1" if tags else None, mark="a")
        self.green(a)
        self.install_at("A", profile=profile)
        b = self.commit("B", version="0.1.1", tag="v0.0.2" if tags else None, mark="b")
        self.green(b)
        self.grant()
        return a, b


def real_engine(tmp_path):
    """An engine repository built from the files of the running checkout on disk (the install set of core_install plus
    release.json), committed in tmp_path: this works in a normal run and in the commit gate's exported tree."""
    import core_install
    engine = tmp_path / "real-engine"
    names = []
    for path in sorted(REPO.rglob("*")):
        rel = path.relative_to(REPO).as_posix()
        if path.is_file() and (core_install.in_set(rel) or rel == "release.json"):
            names.append(rel)
    for rel in names:
        target = engine / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, target)
    if "release.json" not in names:  # an engine checkout that predates the file: write the order's four values
        (engine / "release.json").write_text(json.dumps(RELEASE, indent=2) + "\n", encoding="utf-8")
    # the engine's own run writes byte code beside its modules; the real repository ignores it, so the copy must too
    (engine / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8", newline="\n")
    branch = json.loads((engine / "release.json").read_text(encoding="utf-8"))["branch"]
    git(tmp_path, "init", "-q", "-b", branch, str(engine))
    return engine
