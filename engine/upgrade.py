"""The shell of `mkway upgrade` and `mkway green record` (card MW-104; rulings R257 to R257h): the git, the files and the
processes. What is accepted, refused and said is decided in `core_upgrade.py`; this module reads the facts, calls it, and does
what it allows.

`run_upgrade` answers `(exit code, result)`; the result is the one JSON object `mkway upgrade` prints, also on a refusal
(`ok` false, `error` set). It changes nothing before every check has passed, and a dry run changes nothing at all except one
`update` line in the log. The release's OWN code (a `git archive` of the chosen commit, extracted to a temp folder that is
removed afterwards) runs `install` and `ledger add`, so the engine that is installed is the engine that wrote it.

The config folder (`<upgrade dir>`, `core_upgrade.upgrade_folder`) holds the owner's grant `policy.json`, the green record
`green.jsonl` and the log `updates.jsonl`. The command is the owner's: `mkway.py` refuses it to a session, and every engine
command run here has the session marker removed. Neither this module nor the upgrade ever writes `policy.json`.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import core_upgrade as core
import profiles

ENGINE_FILE = Path(__file__).resolve().with_name("mkway.py")  # the running engine; tests patch it
GIT_TIMEOUT = 120
INSTALL_TIMEOUT = 300
LEDGER_TIMEOUT = 60
INSTALL_PATHS = [".claude/settings.json", "mkway/.gitignore", "mkway/.gitattributes", "mkway/mkway.lock", "mkway/engine"]
LEDGER_PATH = "mkway/ledger/ledger.md"
DROPPED_ENV = ("CLAUDECODE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")


def _windows() -> bool:
    return os.name == "nt"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _engine_env(env) -> dict:
    """The environment of every engine and git command: the session marker and the git location variables removed."""
    out = {k: v for k, v in dict(env).items() if k.upper() not in DROPPED_ENV}
    out["GIT_TERMINAL_PROMPT"] = "0"
    return out


def _home(env) -> str:
    return env.get("HOME") or env.get("USERPROFILE") or str(Path.home())


def _tail(text: str) -> str:
    text = " ".join(text.split())
    return text[-500:] if len(text) > 500 else text


def _run(cmd, cwd, env, timeout, data=False):
    """(code, stdout, stderr); code None when the command did not run or ran out of time (the text says why)."""
    try:
        proc = subprocess.run([str(x) for x in cmd], cwd=str(cwd), env=env, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, b"" if data else "", f"timed out after {timeout} seconds"
    except OSError as exc:
        return None, b"" if data else "", f"{exc.__class__.__name__}: {exc}"
    out = proc.stdout if data else proc.stdout.decode("utf-8", errors="replace")
    return proc.returncode, out, proc.stderr.decode("utf-8", errors="replace")


def _version_of(top) -> str:
    """The text of the engine's VERSION file, or an empty text when there is none."""
    path = Path(top) / "VERSION"
    return path.read_text(encoding="utf-8", errors="replace").strip() if path.is_file() else ""


def _git(cwd, args, env, data=False):
    return _run(["git", "--no-optional-locks", "-C", str(cwd), *args], cwd, env, GIT_TIMEOUT, data)


def _real(path) -> str:
    return str(Path(path).resolve())


def _same(a, b) -> bool:
    return core.folder_key(_real(a), _windows()) == core.folder_key(_real(b), _windows())


def _display(cmd) -> str:
    return core.display_command([str(x) for x in cmd])


class _Stop(Exception):
    """A refusal: the text goes to the answer and (when the flag allows) the log."""

    def __init__(self, text, log=True):
        super().__init__(text)
        self.text, self.log = text, log


class _Upgrade:
    def __init__(self, target, root, dry_run, from_head, env, engine_file):
        self.target_arg, self.root_arg, self.dry_run, self.from_head = target, root, dry_run, from_head
        self.env = _engine_env(env)
        self.engine_file = Path(engine_file)
        self.windows = _windows()
        self.folder, self.override = core.upgrade_folder(env, self.windows, _home(env))
        self.folder_path = Path(self.folder)
        self.green_file = self.folder_path / "green.jsonl"
        self.grant_file = self.folder_path / "policy.json"
        self.log_file = self.folder_path / "updates.jsonl"
        self.version = ""
        self.result = {"ok": False, "updated": False, "upToDate": False, "summary": "", "target": None, "root": None,
                       "engine": None, "branch": None, "oldSha": None, "newSha": None, "checks": [], "commands": [],
                       "upgradeDir": self.folder}

    # ---- small helpers -------------------------------------------------------------------------------------------------
    def check(self, name, detail="", ok=True):
        self.result["checks"].append({"check": name, "ok": ok, "detail": detail})

    def git(self, cwd, *args, data=False):
        return _git(cwd, args, self.env, data)

    def log(self, row) -> str | None:
        """Append one row to the log; None when written, else why not."""
        try:
            self.folder_path.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps({"time": _now(), "version": self.version, **row}) + "\n")
        except OSError as exc:
            return exc.strerror or exc.__class__.__name__
        return None

    # ---- the run -------------------------------------------------------------------------------------------------------
    def go(self):
        try:
            self.checks_before()
            return self.finish()
        except _Done:
            return 0, self.result
        except _Stop as stop:
            return self.refuse(stop)

    def refuse(self, stop):
        self.result["ok"] = False
        self.result["error"] = stop.text
        if stop.log:
            self.log({"event": "refused", "error": stop.text, "target": self.result["target"]})
        return 1, self.result

    def checks_before(self):
        self.h0_engine()
        self.h1_folder()
        self.h2_grant()
        self.root_and_lock()
        self.engine_state()
        self.read_release()
        self.choose()
        self.guard()
        self.paths_clean()

    # ---- H0: which engine ----------------------------------------------------------------------------------------------
    def h0_engine(self):
        bundle = self.engine_file.resolve().parent.parent
        if (bundle / "mkway.lock").is_file():
            raise _Stop(core.installed_copy_text(), log=False)
        code, out, _err = self.git(self.engine_file.resolve().parent, "rev-parse", "--show-toplevel")
        top = Path(out.strip()).resolve() if code == 0 and out.strip() else None
        if top is None or not (top / "release.json").is_file():
            raise _Stop(core.installed_copy_text(), log=False)
        self.top = top
        self.result["engine"] = str(top)
        self.version = _version_of(top)

    # ---- H1: the config folder -----------------------------------------------------------------------------------------
    def h1_folder(self):
        near = self.folder_path
        while not near.exists() and near != near.parent:
            near = near.parent
        code, out, _err = self.git(near, "rev-parse", "--show-toplevel")
        if code != 0 or not out.strip():
            return
        for name in ("policy.json", "green.jsonl", "updates.jsonl"):
            probe = (self.folder_path / name).as_posix()
            code, _o, _e = self.git(near, "check-ignore", "-q", "--", probe)
            if code != 0:
                raise _Stop(core.folder_in_tree_text(self.folder, out.strip()), log=False)

    # ---- H2: the grant, the target, the root ---------------------------------------------------------------------------
    def h2_grant(self):
        try:  # a file that is missing, a folder, or one that cannot be opened is no grant
            text = self.grant_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raise _Stop(core.grant_missing_text(str(self.grant_file)))
        grant, error = core.parse_grant(text, str(self.grant_file), self.windows)
        if error:
            raise _Stop(error)
        self.grant = grant
        self.check("policy.json is valid", str(self.grant_file))
        problem = core.target_problem(self.target_arg, grant["target"], self.windows)
        if problem:
            raise _Stop(problem)
        self.target = Path(grant["target"]).resolve()
        self.result["target"] = str(self.target)
        self.check("target is the folder the policy names", str(self.target))

    def root_and_lock(self):
        name, error = core.pick_root(str(self.target), self.grant["roots"], self.root_arg, self.windows)
        if error:
            raise _Stop(error)
        self.root = (self.target / name).resolve()
        self.result["root"] = str(self.root)
        lock_file = self.root / "mkway" / "mkway.lock"
        if not lock_file.is_file():
            raise _Stop(core.lock_missing_text(str(self.root)))
        try:
            lock = json.loads(lock_file.read_text(encoding="utf-8"))
            if not isinstance(lock, dict):
                raise ValueError("not an object")
        except (OSError, ValueError) as exc:
            raise _Stop(core.lock_unreadable_text(str(lock_file), _tail(str(exc))))
        self.lock = lock
        code, out, _err = self.git(self.target, "rev-parse", "--show-toplevel")
        if code != 0 or not out.strip() or not _same(out.strip(), self.target):
            raise _Stop(core.not_top_text(str(self.target)))
        self.check("root is listed and has an installed engine", f"{self.root} (mkway.lock)")

    # ---- the engine repository -----------------------------------------------------------------------------------------
    def engine_state(self):
        top = self.top
        code, out, err = self.git(top, "status", "--porcelain", "--untracked-files=all")
        code_head, head, err_head = self.git(top, "rev-parse", "HEAD")
        if code != 0 or code_head != 0:
            raise _Stop(core.engine_unreadable_text(str(top), _tail(err or err_head) or "git failed"))
        count = len([x for x in out.splitlines() if x.strip()])
        if count:
            raise _Stop(core.engine_dirty_text(str(top), count))
        self.head = head.strip()

    def read_release(self):
        code, out, _err = self.git(self.top, "show", "HEAD:release.json")
        if code != 0:
            raise _Stop(core.release_missing_text())
        release, error = core.parse_release(out)
        if error:
            raise _Stop(error + ". Nothing was changed.")
        self.release = release
        code, branch, _err = self.git(self.top, "symbolic-ref", "--short", "-q", "HEAD")
        current = branch.strip() if code == 0 and branch.strip() else None
        self.result["branch"] = release["branch"]
        if current != release["branch"]:
            raise _Stop(core.wrong_branch_text(release["branch"], current))
        self.check("engine repository is clean and on " + release["branch"], f"{self.top} at {self.head[:8]}")
        self.check("release.json read from HEAD", f"full_command {release['full_display']}")

    # ---- which commit ------------------------------------------------------------------------------------------------------
    def read_green(self):
        if not self.green_file.exists():
            return []
        try:
            return core.parse_green(self.green_file.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            raise _Stop(core.green_unreadable_text(str(self.green_file), exc.strerror or exc.__class__.__name__))

    def chain(self):
        code, out, _err = self.git(self.top, "rev-list", "--first-parent", "HEAD")
        return [x.strip() for x in out.splitlines() if x.strip()] if code == 0 else []

    def choose(self):
        rows = self.read_green()
        rel = self.release
        repo, into, command = str(self.top), rel["branch"], rel["full_display"]
        chain = self.chain()
        self.tag, self.narrow = None, None
        if not self.from_head:
            code, out, _err = self.git(self.top, "for-each-ref", "--format=%(refname:short) %(objectname) %(*objectname)",
                                       "refs/tags")
            tags = core.parse_tag_refs(out) if code == 0 else []
            chosen = core.choose_release(tags, chain, rows, repo, into, command, self.windows, rel["branch"])
            for tag, why in chosen["skipped"]:
                self.check("release tag skipped", f"{tag}: {why}")
            if chosen["tag"] is None:
                raise _Stop(core.no_tag_text())
            self.sha, self.tag = chosen["sha"], chosen["tag"]
            self.result["release"] = self.tag
            self.check("release tag is proven green", f'{self.tag} ({self.sha[:8]}) has a full test run "{command}"')
            return
        self.sha = self.head
        if core.find_row(rows, self.sha, repo, into, command, self.windows, "full"):
            self.check("engine HEAD is proven green", f'{self.sha[:8]} has a full test run "{command}"')
            return
        walk, reason = core.narrow_walk(self.sha, rows, repo, into, command, self.windows)
        narrow = None
        if walk is not None:
            paths = self.changed_paths(walk["green"])
            narrow, reason = core.narrow_cover(walk["green"], self.sha, paths, rel["narrow_paths"], chain, rel["branch"])
        if narrow is None:
            raise _Stop(core.no_proof_text(str(self.green_file), command, self.sha, rel["branch"], reason))
        narrow["mergeResults"] = walk["mergeResults"]
        self.narrow = narrow
        self.result["narrow"] = narrow
        self.check("narrow test runs only", f"rule {narrow['rule']} covers the {narrow['changedPaths']} changed paths since the "
                   f"full-green head {narrow['fullGreenHead'][:8]}; narrow merge results: {narrow['mergeResults']}; full test "
                   f'run "{command}"')

    def changed_paths(self, green):
        code, out, _err = self.git(self.top, "diff", "--name-only", "--no-renames", "-z", green, self.sha)
        return [x for x in out.split("\0") if x] if code == 0 else None

    # ---- the downgrade guard ---------------------------------------------------------------------------------------------
    def guard(self):
        source = self.lock.get("source_sha")
        source = source if isinstance(source, str) else None
        mode = "head" if self.from_head else "release"
        facts = dict(chosen=self.sha, mode=mode, tag=self.tag, lock_source=source)
        self.result["oldSha"] = source
        self.result["newSha"] = self.sha
        if source and core.SHA_RE.fullmatch(source) and source != self.sha:
            code, _o, _e = self.git(self.top, "cat-file", "-e", source + "^{commit}")
            facts["source_in_repo"] = code == 0
            if code == 0:
                facts["chosen_is_ancestor"] = self.ancestor(self.sha, source)
                facts["source_is_ancestor"] = self.ancestor(source, self.sha)
                code, text, _e = self.git(self.top, "show", self.sha + ":VERSION")
                facts["chosen_version"] = text if code == 0 else ""
                semver = self.lock.get("semver")
                facts["lock_semver"] = semver if isinstance(semver, str) else None
        verdict = core.decide_upgrade(core.GuardFacts(**facts))
        if verdict.kind == "refuse":
            raise _Stop(verdict.text)
        if verdict.kind == "uptodate":
            self.up_to_date()
            raise _Done()
        self.check("not a downgrade", f"{source[:8]} -> {self.sha[:8]}")

    def ancestor(self, older, newer):
        code, _o, _e = self.git(self.top, "merge-base", "--is-ancestor", older, newer)
        return True if code == 0 else False if code == 1 else None

    def migrate_records(self, profile_text):
        """MW-129 (R310 3, R312): copy the card record rows of the main checkout and of every live work tree into the shared
        folder of the profile the task will have (`profile_text` when the upgrade renames a key, else the profile on disk).
        Runs also when the engine is up to date; a dry run prints the same plan and writes nothing. A copy that fails stops
        the upgrade before the install: the task stays on its old engine with a clean tree."""
        import shared_records
        try:
            profile = json.loads(profile_text) if profile_text is not None else json.loads(
                (Path(self.root) / core.PROFILE_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            profile = {}
        if isinstance(profile, dict) and self.grant.get("shared"):  # the install writes `--shared` into the profile (R310 3 c)
            profile = {**profile, "state": {**(profile.get("state") if isinstance(profile.get("state"), dict) else {}),
                                            "shared_dir": self.grant["shared"]}}
        try:
            report = shared_records.migrate(self.root, profile if isinstance(profile, dict) else {}, write=not self.dry_run)
        except shared_records.MigrationFailed as exc:
            raise _Stop(core.migration_failed_text(str(exc)))
        self.result["migration"] = report
        self.check("the card records are in the shared folder", report["lines"][0])

    def up_to_date(self):
        self.migrate_records(None)  # R312: the migration also runs when the engine is already up to date
        res = self.result
        res.update(ok=True, upToDate=True, summary=core.up_to_date_summary(res["target"], self.sha))
        self.check("the lock is at the chosen commit", self.sha[:8])
        written = self.log(self.plan_row())
        written = written or self.log({"event": "update-result", "ok": True, "updated": False, "upToDate": True,
                                       "newSha": self.sha})
        if written:
            raise _Stop(core.log_unwritable_after_text(written), log=False)

    def plan_row(self):
        row = {"event": "update", "target": self.result["target"], "root": self.result["root"],
               "engine": self.result["engine"], "branch": self.result["branch"], "oldSha": self.result["oldSha"],
               "newSha": self.sha, "dryRun": bool(self.dry_run)}
        if self.tag:
            row["release"] = self.tag
        if self.narrow:
            row["narrow"] = self.narrow
        return row

    # ---- install paths ------------------------------------------------------------------------------------------------------
    def paths_clean(self):
        code, out, err = self.git(self.root, "status", "--porcelain", "--untracked-files=all", "--", *INSTALL_PATHS)
        if code != 0:
            raise _Stop(core.root_unreadable_text(str(self.root), _tail(err) or "git status failed"))
        lines = [x for x in out.splitlines() if x.strip()]
        if lines:
            raise _Stop(core.dirty_paths_text(lines))
        self.check("the install paths have no other changes", ", ".join(INSTALL_PATHS))

    # ---- the rest: the release's own code ---------------------------------------------------------------------------------
    def extract(self, tmp):
        code, data, err = self.git(self.top, "archive", "--format=tar", self.sha, data=True)
        if code != 0:
            raise _Stop(core.engine_unreadable_text(str(self.top), _tail(err) or "git archive failed"))
        base = Path(tmp).resolve()
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:  # files and folders only, none outside the temp folder
            members = [m for m in tar.getmembers() if (m.isfile() or m.isdir()) and (base / m.name).resolve().is_relative_to(base)]
            for member in members:
                where = base / member.name
                where.parent.mkdir(parents=True, exist_ok=True)
                where.mkdir(exist_ok=True) if member.isdir() else where.write_bytes(tar.extractfile(member).read())

    def finish(self):
        tmp = tempfile.mkdtemp(prefix="mkway-upgrade-")
        try:
            return self.with_release(tmp)
        except _Stop as stop:
            return self.refuse(stop)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def with_release(self, tmp):
        self.extract(tmp)
        code_file = Path(tmp) / "engine" / "mkway.py"
        python = sys.executable
        code, out, err = _run([python, code_file, "ledger", "add", "--help"], self.root, self.env, LEDGER_TIMEOUT)
        if code is None:
            raise _Stop(core.ledger_unrunnable_text(python, _tail(err)))
        if code != 0 or "--by" not in out:
            raise _Stop(core.no_by_text())
        self.check("the ledger command has --by", core.TOOL_ID)
        profile_text = self.profile_plan()
        quote = core.ledger_quote(self.result["oldSha"], self.sha, self.narrow, self.tag, self.folder if self.override else None,
                                  migrated=profile_text is not None)
        install_cmd = [python, code_file, "install", "--from", self.top, "--ref", self.sha, "--root", self.root]
        if self.grant["shared"]:
            install_cmd += ["--shared", self.grant["shared"]]
        ledger_cmd = [python, code_file, "ledger", "add", "--root", self.root, "--card", "-", "--topic", core.TOPIC,
                      "--quote", quote, "--source", core.SOURCE_TEXT, "--by", core.TOOL_ID]
        self.result["commands"] = [_display(install_cmd).replace(str(code_file), "<release>/engine/mkway.py"),
                                   _display(ledger_cmd).replace(str(code_file), "<release>/engine/mkway.py"),
                                   f'git -C "{self.root}" add <the paths install prints, and the ledger when tracked>',
                                   f'git -C "{self.root}" commit -m "<prefix >mkway install {self.sha[:8]}" -- <the same paths>']
        written = self.log(self.plan_row())
        if written:
            raise _Stop(core.log_unwritable_text(written), log=False)
        self.migrate_records(profile_text)  # MW-129: the LAST step before the install command (R310 3 c); a dry run only plans
        if self.dry_run:
            self.result.update(ok=True, summary=f"Dry run: the engine in {self.result['target']} would be updated "
                               f"{self.result['oldSha'][:8]} -> {self.sha[:8]}; nothing was changed.")
            return 0, self.result
        return self.install(install_cmd, ledger_cmd, quote, profile_text)

    def profile_plan(self):
        """MW-107 (R274a 5 and 10): the profile text with `leads.outside_writable` renamed to `paths.outside_writable`, or None
        when there is nothing to rename. Fills the answer with the rename (`migrations`) and with the rule and the effective
        outside-writable list the task will have (`outsideWritable`), for a dry run and a real run alike. A profile with the
        key that has changes that are not committed is refused: the upgrade commits the profile."""
        file = Path(self.root) / core.PROFILE_FILE
        try:
            profile = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            profile = None
        new, count = core.migrate_profile(profile)
        listed = profiles.outside_writable(new if new is not None else profile if isinstance(profile, dict) else {})
        said = core.migration_text(count, core.ignored_text(profile))
        self.result["migrations"] = [] if new is None else [said]
        self.result["outsideWritable"] = {"rule": core.OUTSIDE_RULE, "list": listed}
        if new is None:
            return None
        code, status, err = self.git(self.root, "status", "--porcelain", "--", core.PROFILE_FILE)
        if code != 0:
            raise _Stop(core.root_unreadable_text(str(self.root), _tail(err) or "git status failed"))
        if status.strip():
            raise _Stop(core.profile_dirty_text())
        self.check("the profile key is renamed", said)
        return json.dumps(new, indent=2, ensure_ascii=False) + "\n"

    def fail_after_write(self, text):
        full = text + " " + core.written_note(str(self.root))
        self.result["error"] = full
        self.log({"event": "update-result", "ok": False, "updated": False, "newSha": self.sha, "error": full,
                  **({"narrow": self.narrow} if self.narrow else {})})
        return 1, self.result

    def install(self, install_cmd, ledger_cmd, quote, profile_text=None):
        code, out, err = _run(install_cmd, self.root, self.env, INSTALL_TIMEOUT)
        if code != 0:
            how = "timed out" if code is None else f"exit {code}"
            return self.fail_after_write(core.install_failed_text(how, _tail(err if code is None else (err or out))))
        line, error = core.read_install_line(out)
        if error:
            return self.fail_after_write(error)
        if profile_text is not None:  # MW-107 (R274a 10): engine-written, in the upgrade's own commit
            try:
                (Path(self.root) / core.PROFILE_FILE).write_text(profile_text, encoding="utf-8", newline="\n")
            except OSError as exc:
                return self.fail_after_write(f"the profile could not be written ({exc.strerror or exc.__class__.__name__})")
        code, out, err = _run(ledger_cmd, self.root, self.env, LEDGER_TIMEOUT)
        if code != 0:
            return self.fail_after_write(core.ledger_failed_text(_tail(err or out)))
        paths = list(line["paths"]) + ([core.PROFILE_FILE] if profile_text is not None else [])
        code, _o, _e = self.git(self.root, "ls-files", "--error-unmatch", "--", LEDGER_PATH)
        if code == 0:
            paths.append(LEDGER_PATH)
        message = core.commit_message_for(line["prefix"], self.sha)
        code, _o, err = self.git(self.root, "add", "--", *paths)
        if code != 0:
            return self.fail_after_write(f"git add failed: {_tail(err)}")
        code, o, err = self.git(self.root, "commit", "-q", "-m", message, "--", *paths)
        if code != 0:
            return self.fail_after_write(f"git commit failed: {_tail(err or o)}")
        _c, commit, _e = self.git(self.root, "rev-parse", "HEAD")
        commit = commit.strip()
        res = self.result
        res.update(ok=True, updated=True, commit=commit, message=message, files=paths, ledgerRow=quote,
                   summary=core.updated_summary(res["target"], res["oldSha"], self.sha, commit, message))
        self.log({"event": "update-result", "ok": True, "updated": True, "newSha": self.sha, "commit": commit,  # best effort:
                  **({"narrow": self.narrow} if self.narrow else {}),                                       # the commit is made
                  **({"release": self.tag} if self.tag else {})})
        return 0, res


class _Done(Exception):
    """The answer is already complete (up to date)."""


def run_upgrade(target, root, dry_run, from_head, env, engine_file):
    """`mkway upgrade`: (exit code, result). Exit 0 only when `ok`; the result is printed as one JSON object either way."""
    return _Upgrade(target, root, dry_run, from_head, env, engine_file).go()


def record_green(fields, env, engine_file=None):
    """`mkway green record`: append one row to the green record; (exit code, text). A bad field refuses and writes nothing."""
    windows = _windows()
    row, error = core.check_green_record(fields, windows)
    if error:
        return 1, "green record refused: " + error
    folder, _override = core.upgrade_folder(env, windows, _home(env))
    top = Path(engine_file if engine_file is not None else ENGINE_FILE).resolve().parent.parent
    version = _version_of(top)
    line = json.dumps({"kind": row["kind"], "repo": row["repo"], "into": row["into"], "branch": row["branch"],
                       "from": row["from"], "sha": row["sha"], "command": row["command"], "rule": row["rule"],
                       "seconds": row["seconds"], "time": _now(), "version": version}) + "\n"
    path = Path(folder) / "green.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lead = ""
        if path.is_file() and path.stat().st_size:
            with open(path, "rb") as fh:
                fh.seek(-1, os.SEEK_END)
                lead = "" if fh.read(1) == b"\n" else "\n"
        with open(path, "ab") as fh:
            fh.write((lead + line).encode("utf-8"))
    except OSError as exc:
        return 1, f"green record refused: cannot write {path} ({exc.strerror or exc.__class__.__name__})"
    return 0, f"green record written: {row['kind']} {row['sha'][:8]} into {row['into']}"
