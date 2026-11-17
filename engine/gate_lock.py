"""The lock gate (card MW-003, deliverable 3; spec section 1, L1-L8; replaces regs 3, 4, 5, 6, 8).

Two manifest entries on this one function (decision 1): `lock.edit` (edit-tool writes) and `lock.shell` (shell
commands). It refuses:
- an edit-tool write inside a closed target (`lock-closed-edit`); any write into `locks/` (`lock-file-by-session`);
- a shell command whose `shell_writes` touches a closed target (`lock-closed-shell`); a command it cannot read
  writes everywhere;
- a commit that touches a closed target (`lock-closed-commit`); the register passes only when its sha256 (the
  working tree's bytes, and with `-i` the staged blob too) equals `register.sha` (R19a);
- a session's call of an owner-only command (`owner-only-command`), in any spelling: `lock open|close`,
  `gate off|on`, `install`, `upgrade`, `card resync`, `card release --force`, and `card open`, `card close` and
  `card set <id> <status>` while that status is in `cards.owner_moves`. The one exception (R19c): the holding
  session's `card set <id> open` passes when the sealed register's current status of that card is `waiting`;
- a session's `card take` while it holds a card that is not closed (`session-has-card`, R15 A2), and a take or a
  release of a card another session holds (`card-not-yours`, v3.1); MW-045: the session that ordered the card may
  release it (a one-use permit), and a holder unseen for `cards.stale_hours` no longer blocks a take.
Every refusal quotes the path and the lock name. It allows everything else.

MW-063: the decisions are `core_lock.decide`, a pure function of facts. This module is the shell: it reads the facts
the core asks for (the markers, the register, the records, git, the command reader), asks again until the core has
what it needs, leaves the one-use permits and the log row, and returns the verdict.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess

import cardtool
import core_lock
import gate
import helpers
import leads
import ledger
import locks
import logs
import messages
import profiles
import register
import runner

SHELL_TOOLS = core_lock.SHELL_TOOLS
_positional = core_lock.positional  # the lead gate reads a command's words the same way
CLI = core_lock.CLI
TERMINAL = core_lock.TERMINAL
MAX_READS = 200  # a decision asks for each fact once; a gate that asks for more than this is a bug


def _owner_moves(profile) -> tuple:
    cards = profile.get("cards") if isinstance(profile, dict) else None
    moves = cards.get("owner_moves") if isinstance(cards, dict) else None
    return tuple(moves) if isinstance(moves, list) else ("open", "closed")


EXPANDED = ("APPDATA", "USERPROFILE", "HOME", "XDG_CONFIG_HOME", "MKWAY_UPGRADE_DIR")  # the variables that build a folder of the guard
_NAME = "(?i:" + "|".join(EXPANDED) + ")" if helpers.CASE_FOLD else "(?:" + "|".join(EXPANDED) + ")"  # the name keeps the OS case rule
_FORM = re.compile(  # the `env:` prefix is read in any case on every OS (PowerShell's Env: drive)
    r"\$\{(?i:env:)?(?P<braced>" + _NAME + r")(?:(?P<op>:-|:=|:\?|:\+|-|=|\?|\+)(?P<word>[^{}]*))?\}"
    r"|\$(?i:env:)?(?P<plain>" + _NAME + r")(?!\w)"
    r"|%(?P<percent>" + _NAME + r")%")
_KEY = {name.casefold(): name for name in EXPANDED}


class Outside:
    """MW-105 (R260 a to c, R260a, R260b, R260d to R260g): the class of a path that may lie outside the repository, read for one
    hook call. `upgrade`: the path equals the guarded upgrade folder (either of its two folders), lies below it, or is one of its
    ancestors, compared on real paths (`helpers._canon`: links, `..`, 8.3 names, case on Windows) with a separator boundary; for
    a glob path, its literal head's folder is compared. `unc`: a network path, decided on the raw text before any other step, and
    a path outside the repository whose real form starts with two slashes (a mapped drive); a network guard entry is compared as
    folded text, never resolved on disk. `~` is the home `mkway upgrade` resolves: HOME, else USERPROFILE.
    A shell path is first expanded from the environment of the call (`_expand`): the five variables that build the folder
    (`EXPANDED`) in the forms `$env:X` (the prefix in any case), `${env:X}`, `$X`, `${X}`, `%X%` and the operator forms `${X:-d}`,
    `${X-d}`, `${X:=d}`, `${X=d}`, `${X:?d}`, `${X:+w}`, always, whatever the command does to the name (R260f), so a command that
    re-points one and writes under it is refused on the real folder; in a PowerShell call `$HOME` is HOME, else USERPROFILE
    (R260g). A name missing from the environment, any other variable and the other operators stay unexpanded: such a path has no
    class (the core's literal-reach rule reads it)."""

    def __init__(self, ctx, targets):
        self.ctx, self._targets, self._folders, self._root_canon = ctx, targets, None, None
        self.env = dict(ctx.env) if ctx.env else {}
        self.home = self.env.get("HOME") or self.env.get("USERPROFILE") or None
        self.prefix = None

    @property
    def folders(self) -> tuple:
        """The canonical form of each folder entry of the closed `upgrade` target, read on first use; a network entry is its
        folded text (nothing is resolved on disk for it)."""
        if self._folders is None:
            self._folders = tuple(helpers._fold(e.rstrip("/")) if helpers.is_unc(e) else helpers._canon(e.rstrip("/"))
                                  for t in self._targets if t.closed and t.name == core_lock.UPGRADE for e in t.entries)
        return self._folders

    def _in_repo(self, canon: str) -> bool:
        """True when the canonical path is the repository's real path or lies below it, on a separator boundary: a repo on a
        mapped drive has a real path that starts with two slashes, and none of its paths is a network path for that reason."""
        if self._root_canon is None:
            self._root_canon = helpers._canon(str(self.ctx.root))
        root = self._root_canon.rstrip("/")
        return canon.rstrip("/") == root or canon.startswith(root + "/")

    def _value(self, name: str):
        """The value of an expandable name in the environment of the call; in a PowerShell call `$HOME` is the profile."""
        if name == "HOME" and self.ctx.tool_name == "PowerShell":
            return self.env.get("HOME") or self.env.get("USERPROFILE")
        return self.env.get(name)

    def _expand(self, text: str, values: dict) -> str:
        """The text with each expandable form replaced; a value becomes a token (`values` maps token to value), so a value that
        holds a character of a variable form (a parenthesis in a folder name) is not read as one. `${X:-d}`, `${X-d}`, `${X:=d}`
        and `${X=d}` give X when it is set (non-empty for the colon forms), else d, expanded once more (a word holds no brace, so one pass reads all of it); `${X:?d}` gives
        X; `${X:+w}` gives w, expanded once more, when X is set (non-empty for the colon form), else nothing. A name that is
        missing or empty is left as it is."""
        def token(value: str) -> str:
            values[f"\x00{len(values)}\x00"] = value
            return f"\x00{len(values) - 1}\x00"

        def sub(m):
            name = _KEY[(m.group("braced") or m.group("plain") or m.group("percent")).casefold()]
            value, op = self._value(name), m.group("op")
            if op is None:
                return token(value) if value else m.group(0)
            is_set = value is not None and (value != "" or not op.startswith(":"))
            if op[-1] in "-=":
                return token(value) if is_set else self._expand(m.group("word"), values)
            if op[-1] == "?":
                return token(value) if is_set and value else m.group(0)
            return self._expand(m.group("word"), values) if is_set else ""

        return _FORM.sub(sub, text)

    def classify(self, raw: str, *, shell: bool, cwd=None):
        if helpers.is_unc(raw):
            return core_lock.UNC
        text = helpers.strip_device_prefix(helpers._clean(raw))
        if shell:
            values: dict = {}
            text = self._expand(text, values)
            if core_lock.VARIABLE.search(text):
                return None
            for token, value in values.items():
                text = text.replace(token, value)
            if helpers.is_unc(text):
                return core_lock.UNC
        if self.prefix is None:
            self.prefix = helpers.top_prefix(self.ctx.root)
        full = helpers.absolute(helpers.strip_stream(text) if helpers.CASE_FOLD else text, self.ctx.root,
                                top_prefix=self.prefix, home=self.home, cwd=cwd)
        if full is None:
            return None
        if shell and any(ch in full for ch in "*?["):
            full = helpers.glob_head_folder(full) + "/"  # the folder before the first wildcard; "/" keeps a drive's own root
        canon = helpers._canon(full)
        if canon.startswith("//") and not self._in_repo(canon):  # a share by its real path, unless it is the repo's own (C4, F1, G3)
            return core_lock.UNC
        return core_lock.UPGRADE if any(helpers.touches_folder(g, canon) for g in self.folders) else None


def _note_problems(event, ctx, profile, tool_input, problems) -> None:
    """One log row for the folders of the upgrade guard the hook could not resolve (R260d C6, C7): the home cannot be found, or an
    override is not an absolute path. It is the guard's own row (it carries a `note`), not a path the session wrote; a failed
    write never fails the call."""
    try:
        logs.write_refusal(profiles.state_dir(ctx.root, profile), logs.row(
            session=ctx.session_id, event=event, tool=ctx.tool_name, gate=ctx.gate, reason_id="write-target-unresolved",
            target=logs.target_of(tool_input), kind="log", note="; ".join(problems)))
    except OSError:
        pass


def check(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    shell = ctx.tool_name in core_lock.SHELL_TOOLS
    command = tool_input.get("command") if shell else None
    targets = locks.core_targets(ctx.root, profile, ctx.profile_file, env=ctx.env)
    outside = Outside(ctx, targets)
    problems = locks.upgrade_resolution(ctx.env)[1]
    if problems:
        _note_problems(event, ctx, profile, tool_input, problems)
    paths = () if shell else tuple(
        tool_input[key] for key in core_lock.PATH_KEYS if isinstance(tool_input.get(key), str) and tool_input.get(key))
    cwd = edit_cwd(ctx)  # MW-107 (round-2 item 1): one base for a relative edit path in every gate of the edit group
    facts = core_lock.Facts(
        tool_name=ctx.tool_name,
        command=command if isinstance(command, str) else "",
        targets=targets,
        session_id=ctx.session_id,
        edit_rels=tuple(ctx.norm(path, cwd=cwd) for path in paths),
        edit_classes=tuple((path, outside.classify(path, shell=False, cwd=cwd)) for path in paths),
        vcs_git=profiles.vcs(profile) == "git",
        owner_moves=_owner_moves(profile),
        orderer=cardtool.approver(profile) == "orderer",
        stale_hours=profiles.cards_stale_hours(profile),
        register_rel=ctx.norm(str(register.path(ctx.root, profile))),
        owner_terminal=cardtool.OWNER_TERMINAL,
        owner_fix=register.OWNER_FIX,
        owner_name=register.OWNER)
    reader = Reader(ctx, profile, facts.command, outside)
    for _ in range(MAX_READS):
        verdict = core_lock.decide(facts)
        if verdict.kind != core_lock.NEED:
            return _finish(ctx, profile, verdict)
        facts = facts.with_read(verdict.need, reader.read(verdict.need))
    raise RuntimeError("the lock gate asked for more facts than it has")


def _finish(ctx, profile, verdict):
    """The one-use permits the core named, then the verdict as the dispatcher reads it."""
    if verdict.permits:
        state = profiles.state_dir(ctx.root, profile)
        for permit in verdict.permits:
            ok = True
            if permit.kind == "by" and permit.scope == "messaging":
                messages.issue_message_permit(state, ctx.session_id)  # MW-110, R279c Q1: the session's own file
            elif permit.kind == "by":
                cardtool.issue_by_permit(state, ctx.session_id)
            elif permit.kind == "close":
                ok = cardtool.issue_close_permit(state, permit.card, ctx.session_id)
            else:
                ok = cardtool.issue_close_permit(state, permit.card, ctx.session_id, kind=permit.kind)
            if not ok and permit.on_fail is not None:
                return _gate_verdict(permit.on_fail)
    return _gate_verdict(verdict)


def _gate_verdict(v):
    if v.kind == core_lock.REFUSE:
        return gate.refuse(v.reason, v.text)
    if v.kind == core_lock.LOG:
        return gate.log(v.reason, v.text)
    return gate.allow()


def edit_cwd(ctx):
    """MW-107 (R274e 11, round-2 reader item 1): the folder a relative edit-tool path is joined to, the hook input's cwd read as
    an absolute path (a relative cwd is read from the root, as the shell reader reads it; None when the input names none). The
    lock, outside, subtask and lead gates all read a relative edit path from this one base."""
    if not (isinstance(ctx.cwd, str) and ctx.cwd.strip()):
        return None
    env = ctx.env if isinstance(ctx.env, dict) else {}
    return helpers.absolute(ctx.cwd, ctx.root, top_prefix=helpers.top_prefix(ctx.root),
                            home=env.get("USERPROFILE") or env.get("HOME") or None)


def _start(ctx):
    """The folder the session's shell starts in, as `dispatch.make_context` reads it for the commit and write checks:
    `""` the root, a repo path, or None when it cannot be read."""
    rel = ctx.norm(ctx.cwd) if isinstance(ctx.cwd, str) and ctx.norm else None
    return None if rel is None else ("" if rel == "." else rel)


class Reader:
    """Reads the one fact the core asks for, by its key (`("register",)`, `("expanded", 0)`, ...)."""

    def __init__(self, ctx, profile, command: str, outside=None):
        self.ctx, self.profile, self.command = ctx, profile, command
        self.outside = outside or Outside(ctx, locks.core_targets(ctx.root, profile, ctx.profile_file, env=ctx.env))
        self.shell = "powershell" if ctx.tool_name == "PowerShell" else "bash"
        self.start = _start(ctx) if ctx.tool_name in core_lock.SHELL_TOOLS else None
        self._commits: list = []  # (the reader's commit, the folder it runs in as a repo path or None)
        self._holders = None
        self._lead = None

    def read(self, key: tuple):
        return getattr(self, "fact_" + key[0])(*key[1:])

    # ---- what the command reader says
    def fact_engine_call(self):
        # H4 (R54): the exact form first; false blocks (E98): a variable assigned a literal in the same command is read
        if helpers.holds_engine_call(self.command, self.shell, root=self.ctx.root, start=self.start):
            return helpers.engine_call_problem(self.command, profiles.bundle_root(self.profile), self.ctx.norm)
        return None

    def fact_calls(self):
        return tuple(tuple(args) for args in self.ctx.mkway_calls(self.command))

    def fact_parse_ok(self):
        return helpers.parse_ok(self.command, self.shell)

    def fact_names_commit(self):
        return helpers.names_git_commit(self.command)

    def fact_carrier(self):
        return helpers.carried_commit(self.command, self.shell)

    def fact_form(self):
        return helpers.git_form_problem(self.command, self.shell, profiles.git_builtins_extra(self.profile))

    def fact_env(self):
        return helpers.env_problem(self.command, self.shell)

    def fact_cdpath(self):
        return helpers.cdpath_cd(self.command, self.shell)

    def fact_unknown_shape(self):
        return helpers.unknown_shape(self.command, self.shell)

    def fact_expanded_text(self):
        return helpers.expanded_text(self.command, self.shell, root=self.ctx.root, start=self.start)

    def fact_writes(self):
        writes = self.ctx.shell_writes(self.command, home=self.outside.home)
        return core_lock.WriteFacts(writes.reason, tuple(self._write_entry(path) for path in writes.paths))

    def _write_entry(self, path):
        """(text, repo path) of one written path; MW-105: a third item, its class, when it is `upgrade` or `unc`."""
        entry = (path, None if core_lock.VARIABLE.search(path) else self.ctx.norm(path))
        cls = self.outside.classify(path, shell=True)
        return entry + (cls,) if cls else entry

    def fact_commits(self):
        out = []
        for commit in self.ctx.commit_cmd(self.command):
            cwd = commit.cwd
            if cwd:  # close-fix 14 (B-M1): an absolute folder, a Git-Bash one (`/c/...`) included, as a repo path first
                rel = self.ctx.norm(cwd)
                if rel is not None:
                    cwd = None if rel == "." else rel
            self._commits.append((commit, cwd))
            folder = (self.ctx.root / cwd) if cwd else None
            out.append(core_lock.CommitFacts(
                folder_unreadable=bool(commit.folder_unreadable), paths=tuple(commit.paths),
                include=bool(commit.include), amend=bool(commit.amend), all=bool(commit.all),
                rels=tuple(self.ctx.norm(p, cwd=folder) for p in commit.paths)))
        return tuple(out)

    # ---- what the markers and the disk say
    def fact_disk(self, rel, entry):
        return locks._file_in(self.ctx.root, rel, entry)

    def fact_seal(self):
        sha_file = register.sha_path(self.ctx.root, self.profile)
        if not sha_file.is_file():
            return core_lock.Seal(sha_file.name, False)
        seal = sha_file.read_text(encoding="utf-8").strip()
        reg = register.path(self.ctx.root, self.profile)
        work = hashlib.sha256(reg.read_bytes()).hexdigest() if reg.is_file() else None
        return core_lock.Seal(sha_file.name, True, seal, work)

    # ---- what git says (a read that does not answer in time is a fact, `Timeout`)
    def fact_expanded(self, i):
        commit, cwd = self._commits[i]
        folder = (self.ctx.root / cwd) if cwd else self.ctx.root
        return self._names(lambda: _expand(self.ctx, folder, list(commit.paths)))

    def fact_staged(self, i):
        def read():
            proc = runner.git(self.ctx.root, "diff", "--cached", "--name-only")
            if proc.returncode != 0:  # list item 3: a failed read refuses, never an empty list
                return [], f"git exit {proc.returncode}"
            return [self.ctx.norm(p) for p in proc.stdout.splitlines() if p.strip()], None
        return self._names(read)

    def fact_index(self, i, every):
        return self._names(lambda: _index_names(self.ctx, every))

    def fact_blob(self, rel):
        try:
            proc = runner.git(self.ctx.root, "cat-file", "blob", f":./{rel}", text=False)  # list item 3: from the root
        except subprocess.TimeoutExpired as exc:  # list item 11 (R44 row 4)
            return core_lock.Timeout(exc.timeout)
        if proc.returncode != 0:
            return core_lock.Blob(None, proc.returncode)
        return core_lock.Blob(hashlib.sha256(proc.stdout).hexdigest(), 0)

    @staticmethod
    def _names(read):
        try:
            names, problem = read()
        except subprocess.TimeoutExpired as exc:  # list item 11 (R44 row 4)
            return core_lock.Timeout(exc.timeout)
        return core_lock.Names(tuple(names), problem)

    # ---- what the records, the register and the leads say
    def _held(self):
        if self._holders is None:
            self._holders = dict(self.ctx.records.holders())
        return self._holders

    def fact_holders(self):
        return self._held()

    def fact_mine(self):
        return self.ctx.records.card()

    def fact_stale(self):
        return cardtool.stale_holders(self.ctx.root, self.profile, self._held())

    def fact_lead(self):
        if self._lead is None:
            self._lead = leads.is_lead(profiles.shared_state_dir(self.ctx.root, self.profile), self.ctx.session_id)
        return self._lead

    def fact_register(self):
        """The sealed register as facts: the seal's refusal, or each row with the card tool's answers for this session."""
        root, profile, session = self.ctx.root, self.profile, self.ctx.session_id
        try:
            register.check(root, profile)
        except register.RegisterError as exc:
            return core_lock.RegisterFacts(problem=(exc.reason, exc.message))
        held, lead = self._held(), self.fact_lead()
        rows = {}
        for row in register.read(root, profile):
            rows.setdefault(row.get("id"), core_lock.Row(
                status=row.get("status"), ordered_by=row.get(register.ORDERED) or register.OWNER,
                orderer_problem=cardtool.orderer_problem(row, held, session),
                open_problem=cardtool.open_problem(row, session, lead)))
        return core_lock.RegisterFacts(rows=rows)

    def fact_quote_rel(self, value):
        return self.ctx.norm(value) if self.ctx.norm else None

    def fact_quote_folders(self):
        return (profiles.owner_ask(self.profile)["dir"], f"{profiles.bundle_root(self.profile)}/{ledger.LEDGER_DIR}")


def _expand(ctx, folder, specs: list):
    """(repo paths, problem): the files a `git commit -- <specs>` takes, from `folder`. With a HEAD, the tracked
    files that differ from it (the commit takes their working-tree content); with no HEAD yet, the index. A git exit
    that is not 0 is a problem, never an empty list."""
    proc = runner.git(folder, "diff", "--name-only", "--no-renames", "HEAD", "--", *specs)
    if proc.returncode != 0:
        head = runner.git(folder, "rev-parse", "--verify", "-q", "HEAD")
        if head.returncode == 0:
            return [], f"git exit {proc.returncode}"
        proc = runner.git(folder, "ls-files", "--full-name", "--", *specs)
        if proc.returncode != 0:
            return [], f"git exit {proc.returncode}"
    return [ctx.norm(p) for p in proc.stdout.splitlines() if p.strip()], None


def _index_names(ctx, every: bool):
    """(repo paths, problem): what a commit with no pathspec takes. The staged names; with `-a` (`every`) the staged
    names and the tracked changes, which are the tracked files that differ from HEAD, one read; with no HEAD yet,
    the index. A git exit that is not 0 is a problem; under `-a` the one exception is no HEAD, shown by
    `rev-parse --verify HEAD`, as in `_expand` (close-fix 9, A-L2)."""
    proc = runner.git(ctx.root, "diff", "--name-only", "--no-renames", "HEAD") if every else None
    if proc is not None and proc.returncode != 0:
        head = runner.git(ctx.root, "rev-parse", "--verify", "-q", "HEAD")
        if head.returncode == 0:
            return [], f"git exit {proc.returncode}"
    if proc is None or proc.returncode != 0:
        proc = runner.git(ctx.root, "diff", "--cached", "--name-only", "--no-renames")
        if proc.returncode != 0:
            return [], f"git exit {proc.returncode}"
    return [ctx.norm(p) for p in proc.stdout.splitlines() if p.strip()], None


def remind(event, ctx):
    """The `unresolved` gate (prompt group, list item 5, R43 (c)): at the next prompt, the count of this session's
    `write-target-unresolved` rows not yet reminded, once per row. It reads the log and writes nothing."""
    path = profiles.state_dir(ctx.root, ctx.profile if isinstance(ctx.profile, dict) else {}) / logs.REFUSALS
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return gate.allow()
    count = 0
    for n, line in enumerate(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("session") == ctx.session_id and not row.get("note") and \
                row.get("reason_id") == "write-target-unresolved" and row.get("kind") == "log" and \
                ctx.once([f"row {n}"]):  # the reminder's own warn row is not counted
            count += 1
    if not count:
        return gate.allow()
    return gate.warn("write-target-unresolved", f"{count} of your shell commands since the last prompt wrote to "
                                                f"targets the lock gate could not read (not blocked, logged). A "
                                                f"lock-target path built without its literal is not seen: write "
                                                f"literal paths")
