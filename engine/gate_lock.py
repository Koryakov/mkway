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
  release of a card another session holds (`card-not-yours`, v3.1).
Every refusal quotes the path and the lock name. It allows everything else.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess

import cardtool
import gate
import helpers
import leads
import locks
import logs
import profiles
import register
import runner

SHELL_TOOLS = ("Bash", "PowerShell")
_VARIABLE = re.compile(r"[$`%(){}]")
WHY = {"unparsed": "the shell text or a Python body does not parse",
       "capable": "a computed path, a variable, or a program that can write anywhere"}
PATH_KEYS = ("file_path", "notebook_path", "path")
CLI = "python mkway/engine/mkway.py"
TERMINAL = "the owner runs it in their own terminal, where no hook runs"


def _owner_moves(profile) -> list:
    cards = profile.get("cards") if isinstance(profile, dict) else None
    moves = cards.get("owner_moves") if isinstance(cards, dict) else None
    return moves if isinstance(moves, list) else ["open", "closed"]


def _closed(ctx, profile, rel, how):
    """The refusal for a path inside a closed target, or one that holds a closed target (list item 2), or None."""
    target = locks.closed_target(ctx.root, profile, rel, ctx.profile_file)
    if target:
        return _refuse_target(target, rel, how)
    held = locks.held_target(ctx.root, profile, rel, ctx.profile_file)
    if held:
        return _refuse_target(held[0], rel, how, holds=held[1])
    return None


def _fix(target) -> str:
    """The way out named in a refusal for the closed target."""
    if target.open_by_default:  # the owner hold (MW-010)
        return (f"hold by the owner; wait for the owner's word (the owner lifts it with `{CLI} lock open "
                f"{target.name}`, {TERMINAL})")
    if target.name in locks.NEVER_OPEN:
        return "only the engine's own commands write it"
    if target.built_in:
        return f"the owner may open it with `{CLI} lock open {target.name}` ({TERMINAL})"
    return f"ask the owner to open it: `{CLI} lock open {target.name}` ({TERMINAL})"


def _glob_inside(ctx, profile, rel):
    """`lock-closed-shell` when the glob path `rel`'s literal folder (before its first wildcard) lies inside a closed
    target (close-fix 2, B-H1: `mkway/engine/*`); None otherwise."""
    if rel is None:
        return None
    head = rel[:min(i for i, ch in enumerate(rel) if ch in "*?[")]
    folder = head.rsplit("/", 1)[0] if "/" in head else ""
    target = locks.closed_target(ctx.root, profile, folder, ctx.profile_file) if folder else None
    if target is None:
        return None
    fix = _fix(target)
    return gate.refuse("lock-closed-shell", f"{rel} is a glob inside {folder}, which is inside the closed lock "
                                            f"{target.name!r}; {fix}")


def _refuse_target(target, rel, how, holds=None):
    if target.name == "locks" and holds is None:
        return gate.refuse("lock-file-by-session", f"{rel} is a lock file: lock files are written only by the "
                                                   f"owner's `mkway lock open|close` ({TERMINAL})")
    reason = {"edit": "lock-closed-edit", "shell": "lock-closed-shell", "commit": "lock-closed-commit"}[how]
    fix = _fix(target)
    if holds is not None:
        return gate.refuse(reason, f"{rel} holds {holds}, which is inside the closed lock {target.name!r}; {fix}")
    return gate.refuse(reason, f"{rel} is inside the closed lock {target.name!r}; {fix}")


def check(event, ctx):
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    if ctx.tool_name in SHELL_TOOLS:
        command = tool_input.get("command")
        return _shell(ctx, profile, command if isinstance(command, str) else "")
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            verdict = _closed(ctx, profile, ctx.norm(value), "edit")
            if verdict:
                return verdict
    return gate.allow()


def _positional(args: list) -> list:
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("--root", "--profile", "--minutes", "--text", "--source", "--from", "--ref", "--vcs", "--python"):
            i += 2
            continue
        if not a.startswith("-"):
            out.append(a)
        i += 1
    return out


def _status(ctx, profile, card_id):
    """The sealed register's status of a card; raises RegisterError when the seal fails."""
    register.check(ctx.root, profile)
    row = register.find(register.read(ctx.root, profile), card_id)
    return row.get("status") if row else None


def _owner_only(what: str):
    return gate.refuse("owner-only-command", f"`mkway {what}` is the owner's command: {TERMINAL}. A session never "
                                             "grants itself a card or a lock and never declares itself done")


def _close_by_orderer(ctx, profile, card_id, held):
    """MW-011, `cards.approver: orderer`: a session's `card close`. The orderer must be this session (the id of the
    hook input) and not the card's holder; the gate then leaves the one-use permit the CLI reads. The status and the
    tests are the CLI's to check."""
    if not card_id:
        return None  # the CLI refuses a close with no card id
    register.check(ctx.root, profile)
    row = register.find(register.read(ctx.root, profile), card_id)
    if row is None:
        return None  # the CLI says `card-unknown`
    problem = cardtool.orderer_problem(row, held, ctx.session_id)
    if problem:
        return gate.refuse(problem[0], problem[1])
    if not cardtool.issue_close_permit(profiles.state_dir(ctx.root, profile), card_id, ctx.session_id):
        return gate.refuse("close-not-orderer", f"{card_id}: the permit of this close could not be written; "
                                                f"{cardtool.OWNER_TERMINAL}")
    return None


def _open_by_lead(ctx, profile, card_id, shared):
    """MW-028, `cards.approver: orderer`: a registered lead's `card open` of a proposed card it ordered leaves the
    one-use permit the CLI reads; any other card (the owner's, another session's, one past `proposed`) stays the
    owner's to open."""
    if not card_id:
        return None  # the CLI refuses an open with no card id
    register.check(ctx.root, profile)
    row = register.find(register.read(ctx.root, profile), card_id)
    if row is None:
        return None  # the CLI says `card-unknown`
    problem = cardtool.open_problem(row, ctx.session_id, leads.is_lead(shared, ctx.session_id))
    if problem:
        return gate.refuse("owner-only-command", problem[1])
    if not cardtool.issue_close_permit(profiles.state_dir(ctx.root, profile), card_id, ctx.session_id, kind="open"):
        return _owner_only("card open")
    return None


def _call(ctx, profile, args: list):
    pos = _positional(args)
    if not pos:
        return None
    head = pos[0]
    if head == "lock" and pos[1:2] and pos[1] in ("open", "close"):
        return _owner_only(" ".join(pos[:2]))
    if head == "gate" and pos[1:2] and pos[1] in ("off", "on", "watch"):  # `watch`: MW-012
        return _owner_only(" ".join(pos[:2]))
    if head in ("install", "upgrade", "hold", "go", "delivered"):  # `hold` and `go`: the short forms of the lock close
        return _owner_only(head)                                   # and open; `delivered` (MW-020): the owner's base
    state = profiles.state_dir(ctx.root, profile)  # the permits stay in this work tree's state folder
    if head == "built":  # MW-020: the provenance row names the session; the CLI reads it from this one-use permit
        cardtool.issue_by_permit(state, ctx.session_id)
        return None
    shared = profiles.shared_state_dir(ctx.root, profile)  # the leads cross work trees (MW-017)
    if head == "give":  # MW-011: the owner says who ordered a card; MW-017: a registered lead's give is a hand-off
        if not leads.is_lead(shared, ctx.session_id):
            return _owner_only(head)
        cardtool.issue_by_permit(state, ctx.session_id)  # the CLI reads the session id from this one-use permit
        return None
    if head == "lead" and pos[1:2]:  # MW-017: `lead add|remove` are the owner's; register and accept name the session
        if pos[1] in ("add", "remove"):
            return _owner_only(f"lead {pos[1]}")
        if pos[1] in ("register", "accept"):
            cardtool.issue_by_permit(state, ctx.session_id)
        return None
    if (head == "ledger" and pos[1:2] == ["add"]) or (head == "ask" and pos[1:2] == ["default"]) or head in (
            "ack", "send", "inbox"):
        cardtool.issue_by_permit(state, ctx.session_id)  # MW-015: names the session (MW-017: `ack`; MW-018: `send`, `inbox`)
        return None
    if head != "card" or len(pos) < 2:
        return None
    sub, card_id = pos[1], (pos[2] if len(pos) > 2 else None)
    if sub == "new":  # MW-017: a lead's new card gets its order file; the CLI reads who ran it from the permit
        if leads.is_lead(shared, ctx.session_id):
            cardtool.issue_by_permit(state, ctx.session_id)
        return None
    moves = _owner_moves(profile)
    if sub == "resync":
        return _owner_only("card resync")
    held = ctx.records.holders()
    if sub == "release":
        if any(a == "--force" or a.startswith("--force=") for a in args):
            return _owner_only("card release --force")
        holder = held.get(card_id)
        if holder and holder != ctx.session_id:
            return gate.refuse("card-not-yours", f"{card_id} is held by another session; a session releases only "
                                                 f"its own card. The owner frees it with `{CLI} card release "
                                                 f"{card_id} --force` ({TERMINAL})")
        return None
    orderer = cardtool.approver(profile) == "orderer"
    if sub == "close" and orderer:
        return _close_by_orderer(ctx, profile, card_id, held)
    if sub == "open" and orderer and "open" in moves and leads.is_lead(shared, ctx.session_id):
        return _open_by_lead(ctx, profile, card_id, shared)  # MW-028
    if sub in ("open", "close"):
        status = "open" if sub == "open" else "closed"
        return _owner_only(f"card {sub}") if status in moves else None
    if sub == "set":
        status = pos[3] if len(pos) > 3 else None
        if status == "closed" and orderer:  # MW-011: `closed` by a session goes through `card close` only
            return _owner_only("card set closed")
        if status == "waiting" and (not card_id or held.get(card_id) != ctx.session_id):
            return gate.refuse("card-not-yours", f"{card_id} is not the card this session holds; a session pauses "
                                                 f"only its own card (`{CLI} card take <id>` first)")
        if status not in moves:
            return None
        if status == "open" and card_id and held.get(card_id) == ctx.session_id:
            if _status(ctx, profile, card_id) == "waiting":
                return None  # R19c: the holder reopens its own pause
        return _owner_only(f"card set {status}")
    if sub == "take":
        holder = held.get(card_id)
        if holder and holder != ctx.session_id:
            return gate.refuse("card-not-yours", f"{card_id} is held by another session. The owner frees it with "
                                                 f"`{CLI} card release {card_id} --force` ({TERMINAL})")
        mine = ctx.records.card()
        if mine and mine != card_id and _status(ctx, profile, mine) != "closed":
            return gate.refuse("session-has-card", f"this session holds {mine}, which is not closed: one card per "
                                                   f"session. Free it with `{CLI} card release {mine}` first")
        for other_card, other in held.items():  # MW-034: one builder per task root, so one worktree and one index
            if other != ctx.session_id and _status(ctx, profile, other_card) == "open":
                return gate.refuse("take-root-busy", f"session {other[:8]} already holds {other_card} in this task "
                                                     f"root: one builder per worktree and index. Wait until that "
                                                     f"session closes or hands off {other_card}, or work in your "
                                                     f"own worktree")
    return None


def _start(ctx):
    """The folder the session's shell starts in, as `dispatch.make_context` reads it for the commit and write checks:
    `""` the root, a repo path, or None when it cannot be read."""
    rel = ctx.norm(ctx.cwd) if isinstance(ctx.cwd, str) and ctx.norm else None
    return None if rel is None else ("" if rel == "." else rel)


def _shell(ctx, profile, command: str):
    shell = "powershell" if ctx.tool_name == "PowerShell" else "bash"
    start = _start(ctx)
    # H4 (R54): the exact form first, then the call's own rules; false blocks (E98): a variable assigned a literal in
    # the same command is read, so `python $D/tool.py` is no disguised engine script
    if helpers.holds_engine_call(command, shell, root=ctx.root, start=start):
        problem = helpers.engine_call_problem(command, profiles.bundle_root(profile), ctx.norm)
        if problem:
            return gate.refuse("engine-call-not-plain", f"the engine call is refused: {problem}. Run the mkway "
                                                        f"command alone, in its plain form: `{CLI} <command> "
                                                        f"<args>`")
    try:
        for args in ctx.mkway_calls(command):
            verdict = _call(ctx, profile, args)
            if verdict is not None:
                return verdict
        if profiles.vcs(profile) == "git" and not helpers.parse_ok(command, shell) and \
                helpers.names_git_commit(command):  # list item 7 (R43 point 2): an integrity gate fails closed
            return gate.refuse("command-unparsed", "this command cannot be parsed and holds a `git ... commit`, so "
                                                   "its commit cannot be checked; run the commit alone, in a plain "
                                                   "form: `git commit -m \"<message>\" -- <paths>`")
        carrier = helpers.carried_commit(command, shell) if profiles.vcs(profile) == "git" else None
        if carrier:  # close-fix 3 (B-H5, R83), remainder item 1 (R95 (2a)): an unread commit fails closed
            return gate.refuse("command-unparsed", f"this command may run a `git ... commit` the gate cannot read "
                                                   f"(through {carrier}), so its commit cannot be checked; run the "
                                                   "commit alone, in a plain form: `git commit -m \"<message>\" -- "
                                                   "<paths>`")
        form = (helpers.git_form_problem(command, shell, profiles.git_builtins_extra(profile))
                if profiles.vcs(profile) == "git" else None)
        if form:  # close-fix 8 (A-M2, R83): a git form the reader cannot check is refused outright
            return gate.refuse(form[0], f"{form[1]}, so its effect cannot be checked; run the plain form: `git commit "
                                        f"-m \"<message>\" -- <paths>` with exact option names")
        env = helpers.env_problem(command, shell)
        if env:  # close-fix 7 (B-H4), remainder item 8 (H7): an `env` the gate cannot read
            return gate.refuse("command-unparsed", f"{env}; run the command directly, without that `env` option")
        if helpers.cdpath_cd(command, shell):  # remainder item 10 (H5b): `cd` under `CDPATH` lands where it is not named
            return gate.refuse("command-unparsed", "this command holds `CDPATH` and a `cd`, so the folder it runs in "
                                                   "cannot be read; run the `cd` without `CDPATH`, to a literal folder")
        writes = ctx.shell_writes(command)
        why = writes.reason
        for path in writes.paths:
            if _VARIABLE.search(path):  # a variable or substitution path is `capable` (R43)
                why = why or helpers.CAPABLE
                continue
            rel = ctx.norm(path)
            if any(ch in path for ch in "*?["):  # a glob: refused when it matches a closed target or its folder
                hit = locks.glob_target(ctx.root, profile, rel, ctx.profile_file)
                if hit:
                    return _refuse_target(hit[0], rel, "shell", holds=hit[1])
                inside = _glob_inside(ctx, profile, rel)
                if inside:
                    return inside
                continue
            verdict = _closed(ctx, profile, rel, "shell")  # (a)
            if verdict:
                return verdict
        pending = None
        if why:
            hit = locks.named_target(ctx.root, profile, command, ctx.profile_file) or locks.named_target(
                ctx.root, profile, helpers.expanded_text(command, shell, root=ctx.root, start=start),
                ctx.profile_file)  # item 12: expanded too
            if hit:  # (b) literal reach
                return gate.refuse("lock-closed-shell", f"this command's write targets cannot all be read ({why}: "
                                                        f"{WHY[why]}), and it names {hit[1]}, which is inside the "
                                                        f"closed lock {hit[0].name!r}; split it into plain commands "
                                                        f"that write literal paths")
            pending = gate.log("write-target-unresolved", f"write targets not read ({why}: {WHY[why]})")  # (c)
        if profiles.vcs(profile) == "git":
            for commit in ctx.commit_cmd(command):
                verdict = _commit(ctx, profile, commit)
                if verdict is not None:
                    return verdict
            shape = helpers.unknown_shape(command, shell)
            if shape and helpers.names_git_commit(command):  # remainder item 10 (R95 (1b)): a commit the shape hides
                return gate.refuse("command-unparsed", f"this command holds a shape the gate does not follow "
                                                       f"({shape}) and names a `git ... commit`, so its commit cannot "
                                                       "be checked; run the commit alone, in a plain form: `git "
                                                       "commit -m \"<message>\" -- <paths>`")
    except register.RegisterError as exc:
        return gate.refuse(exc.reason, exc.message)
    except subprocess.TimeoutExpired as exc:  # list item 11 (R44 row 4)
        return gate.refuse("gate-git-timeout", f"a git read did not answer within {exc.timeout:g} s, so the commit "
                                               f"could not be checked; run it again")
    return pending or gate.allow()


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
        if isinstance(row, dict) and row.get("session") == ctx.session_id and \
                row.get("reason_id") == "write-target-unresolved" and row.get("kind") == "log" and \
                ctx.once([f"row {n}"]):  # the reminder's own warn row is not counted
            count += 1
    if not count:
        return gate.allow()
    return gate.warn("write-target-unresolved", f"{count} of your shell commands since the last prompt wrote to "
                                                f"targets the lock gate could not read (not blocked, logged). A "
                                                f"lock-target path built without its literal is not seen: write "
                                                f"literal paths")


def _commit(ctx, profile, commit):
    if commit.folder_unreadable:  # list item 9 (R44 row 2)
        return gate.refuse("commit-folder-unreadable", "this commit runs in a folder the gate cannot read (a `cd` or "
                                                       "`-C` to a variable or an unreadable target), so its paths "
                                                       "cannot be checked; `cd` to a literal folder, or commit from "
                                                       "the root with repo paths")
    unresolved = [p for p in commit.paths if "$" in p or "`" in p]  # `:(glob)` pathspec magic is not one
    if unresolved:  # list item 12 (R44 row 5): only a path still unresolved after the same-command expansion
        return gate.refuse("pathspec-unparsed", f"the commit path {unresolved[0]} holds a variable or a substitution "
                                                f"that is not a literal assigned earlier in this command, so it "
                                                f"cannot be checked; name the path literally")
    reg_rel = ctx.norm(str(register.path(ctx.root, profile)))
    cwd = commit.cwd
    if cwd:  # close-fix 14 (B-M1): an absolute folder, a Git-Bash one (`/c/...`) included, as a repo path first
        rel = ctx.norm(cwd)
        if rel is not None:
            cwd = None if rel == "." else rel
    rels = [ctx.norm(p, cwd=(ctx.root / cwd) if cwd else None) for p in commit.paths]
    if commit.paths:  # list item 2: a pathspec is the changed tracked files it matches, each checked
        expanded, problem = _expand(ctx, (ctx.root / cwd) if cwd else ctx.root, commit.paths)
        if problem:
            return gate.refuse("lock-closed-commit", f"the commit pathspec could not be expanded ({problem}), so "
                                                     f"its files could not be checked; name plain paths")
        rels += [r for r in expanded if r not in rels]
    staged = []
    if commit.include:
        proc = runner.git(ctx.root, "diff", "--cached", "--name-only")
        if proc.returncode != 0:  # list item 3: a failed read refuses, never an empty list
            return gate.refuse("lock-closed-commit", f"the staged names could not be read (git exit "
                                                     f"{proc.returncode}), so the commit could not be checked")
        staged = [ctx.norm(p) for p in proc.stdout.splitlines() if p.strip()]
    elif commit.amend or not commit.paths:  # list item 16 (R68): the commit takes the index, or with -a the changes
        names, problem = _index_names(ctx, commit.all and not commit.paths)
        if problem:
            return gate.refuse("lock-closed-commit", f"the files this commit takes could not be read ({problem}), "
                                                     f"so it could not be checked; name your paths after `--`")
        for rel in names:
            verdict = _index_commit(ctx, profile, rel, reg_rel, commit.all and not commit.paths)
            if verdict is not None:
                return verdict
    for rel in rels + staged:
        if rel is None:
            continue
        if rel == reg_rel:
            verdict = _register_commit(ctx, profile, rel, rel in staged or commit.include)
            if verdict is not None:
                return verdict
            continue
        target = locks.closed_target(ctx.root, profile, rel, ctx.profile_file)
        if target:
            return _refuse_target(target, rel, "commit")
    return None


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


def _index_commit(ctx, profile, rel, reg_rel, every: bool):
    """The refusal for one file a commit with no pathspec takes, naming the session's own step; or None."""
    if rel is None:
        return None
    if rel == reg_rel:
        return _register_commit(ctx, profile, rel, not every)
    target = locks.closed_target(ctx.root, profile, rel, ctx.profile_file)
    if not target:
        return None
    if every:
        return gate.refuse("lock-closed-commit", f"{rel} has a change inside the closed lock {target.name!r} and "
                                                 f"`-a` would commit it; commit without -a and name your own paths "
                                                 f"after `--`")
    return gate.refuse("lock-closed-commit", f"{rel} is staged and inside the closed lock {target.name!r}; unstage "
                                             f"it with `git restore --staged {rel}` and commit without it")


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


def _register_commit(ctx, profile, rel, include_index):
    sha_file = register.sha_path(ctx.root, profile)
    if not sha_file.is_file():
        return gate.refuse("lock-closed-commit", f"{rel}: {sha_file.name} is missing, so the register cannot be "
                                                 f"checked; {register.OWNER_FIX}")
    seal = sha_file.read_text(encoding="utf-8").strip()
    reg = register.path(ctx.root, profile)
    work = hashlib.sha256(reg.read_bytes()).hexdigest() if reg.is_file() else None
    if work != seal:
        return gate.refuse("lock-closed-commit", f"{rel} differs from its seal; only the engine's own commands "
                                                 f"write it. {register.OWNER_FIX}")
    if include_index:
        proc = runner.git(ctx.root, "cat-file", "blob", f":./{rel}", text=False)  # list item 3: from the root
        if proc.returncode != 0:
            return gate.refuse("lock-closed-commit", f"the staged {rel} could not be read (git exit "
                                                     f"{proc.returncode}), so it could not be checked against its "
                                                     f"seal; stage it with `git add {rel}` or leave it out")
        staged = hashlib.sha256(proc.stdout).hexdigest()
        if staged != seal:
            return gate.refuse("lock-closed-commit", f"the staged {rel} differs from its seal; only the engine's own "
                                                     f"commands write it. {register.OWNER_FIX}")
    return None
