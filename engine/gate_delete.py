"""The delete gate (card MW-009; the owner's order of 2026-11-10: deletes are explicit, backed up, logged).

One manifest entry `delete` (shell group, `onFailure: block`). Since card MW-064 the gate is a thin shell around the pure
decisions of `core_delete`: it reads the shell command with the lock gate's reader (`helpers.parse`, `expand_vars`,
`folder_track`, `carriers`: quotes removed, a heredoc body blanked, every position entered: chains, substitutions,
`bash -c`, `cmd /c`, `pwsh -c`, `xargs`, `find -exec`) into small step records (`read`), answers the facts the core asks
for from the real tree and git (`check`), and writes the backup and its record. It refuses:
- a delete whose target is not a literal path inside the root that exists (`delete-target-unknown`): a variable, a
  substitution, an unknown PowerShell parameter, a splat, `find -delete`, `xargs rm`, a missing path, the state folder
  and anything that holds it;
- a target outside the root (`delete-outside-root`), a wildcard (`delete-wildcard`);
- destructive SQL (`delete-sql`), unless the profile key `delete.sql_allowed` is true;
- a session's `mkway trash ...` (`owner-only-command`).
The delete forms are the program of a simple command, never a word inside a text, so `echo "rm"`, a commit message and
a `grep` pattern are not deletes. The refusal text names the way out: `mkway delete --list <file>`.
"""
from __future__ import annotations

import os
import re

import core_delete as core
import gate
import helpers
import profiles
import runner
import trash

SHELL_TOOLS = ("Bash", "PowerShell")


def _start(ctx):
    """The folder the session's shell starts in: `""` the root, a repo path, or None when it cannot be read."""
    rel = ctx.norm(ctx.cwd) if isinstance(ctx.cwd, str) and ctx.norm else None
    return None if rel is None else ("" if rel == "." else rel)


def _backticks(cmd: str) -> list:
    """The texts of the backtick substitutions of a bash text: not those inside single quotes (a markdown span in a
    commit message is text), not a heredoc body, not an escaped backtick."""
    text = helpers._split_heredocs(cmd)[0]
    out, quote, i, n = [], "", 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        if ch == "`" and quote != "'":
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            out.append(text[i + 1:j])
            i = j
        i += 1
    return out


# ---- reading the command: no decision here, only the steps for the core ----------------------------------------------

def read(command: str, *, shell: str, start, root=None) -> list:
    """The steps (`core_delete` records) of a shell command, in the order the gate meets them. `start` is the folder the
    shell starts in (`""` the root, a repo path, or None). `root` is passed to the shared reader only so that a `cd` into
    a folder that does not exist makes the folder unknown, as in a real shell; with `None` (a table test) every `cd`
    target counts as a folder that exists."""
    steps = []
    for args in helpers.mkway_calls(command, shell):
        pos = [a for a in args if not a.startswith("-")]
        if pos[:1] == ["trash"]:
            steps.append(core.Trash(" ".join(pos[1:2])))
    _text(command, shell, "", start, 0, root, steps)
    return steps


def _text(cmd: str, shell: str, style: str, start, depth: int, root, steps: list):
    if depth > core.MAX_DEPTH:
        steps.append(core.TooDeep())
        return
    try:
        simples = helpers.expand_vars(helpers.parse(cmd, shell), shell, root=root, start=start)
    except helpers.ParseError:
        names = {core.prog_name(w) for w in re.split(r"\W+", cmd)}
        steps.append(core.Unparseable(word=bool(core.WORD.search(cmd)),
                                      sql_client=bool(core.SQL.search(cmd) and core.SQL_CLIENTS & names)))
        return
    for s, base in helpers.folder_track(simples, start, root=root):
        _simple(s, base, cmd, shell, style, depth, root, steps)
        for sub in s.subs:
            _text(sub, shell, style, base, depth + 1, root, steps)
    if shell == "bash":
        for sub in _backticks(cmd):
            _text(sub, shell, style, start, depth + 1, root, steps)


def _simple(s, base, whole, shell, style, depth, root, steps: list):
    words = list(s.words)
    while words and words[0] in helpers._COMPOUND_WORDS:
        words = words[1:]
    argv = helpers._argv(words)
    prog = helpers._prog(argv)
    args = argv[1:]
    if prog in core.DELETE_PROGS:
        steps.append(core.Delete(prog, tuple(args), base, shell, style))
    elif prog == "find" and "-delete" in args:
        steps.append(core.FindDelete())
    elif prog in core.SQL_CLIENTS:
        piped = "|" in s.before.replace("||", "")
        steps.append(core.Sql(" ".join(args + [h for h in s.heredocs if isinstance(h, str)] + ([whole] if piped else []))))
    elif prog == "git":
        steps.append(core.Git(tuple(argv), base))
    elif helpers._INTERPRETERS.match(prog or ""):
        code, _found = helpers._code_flag(re.sub(r"[\d.]+$", "", prog), args)
        bodies = [code] if code is not None else (
            [h for h in s.heredocs if isinstance(h, str)] if helpers._reads_stdin(prog, args) else [])
        steps.append(core.Python(tuple(bodies), base))
    for name, text in helpers.carriers(s, whole):
        if text.startswith("\0") or helpers._INTERPRETERS.match(name or ""):
            continue
        if name == "xargs" and any(core.prog_name(w) in core.DELETE_PROGS for w in text.split()):
            steps.append(core.XargsDelete())
        if name in ("pwsh", "powershell"):
            _text(text, "powershell", "", base, depth + 1, root, steps)
        elif name == "cmd":
            _text(text, "powershell", "cmd", base, depth + 1, root, steps)
        else:
            _text(text, "bash", "", base, depth + 1, root, steps)


# ---- the facts: what the real tree and git say ------------------------------------------------------------------------

def _git(ctx, *args):
    """`(failure, lines)` of a git read at the root: `failure` is None, or the words the refusal uses."""
    try:
        proc = runner.git(ctx.root, "--literal-pathspecs", *args)
    except (runner.SubprocessError, runner.Refused, OSError) as exc:
        return f"did not answer ({type(exc).__name__})", ()
    if proc.returncode != 0:
        return f"exited {proc.returncode}", ()
    return None, tuple(line for line in proc.stdout.splitlines() if line.strip())


def _answer(ctx, need: core.Need):
    if need.kind == "norm":
        return ctx.norm(need.key)
    if need.kind == "exists":
        return os.path.lexists(ctx.root / need.key)
    if need.kind == "status":
        return _git(ctx, "status", "--porcelain", "--untracked-files=no", *(["--", *need.key] if need.key else []))
    if need.kind == "tracked":
        return _git(ctx, "ls-files", "--", need.key)
    raise ValueError(f"unknown fact {need.kind!r}")


def judge(ctx, profile, command: str) -> core.Decision:
    """The core's decision for a shell command, with every fact it asks for read from the real tree and git."""
    shell = "powershell" if ctx.tool_name == "PowerShell" else "bash"
    steps = read(command, shell=shell, start=_start(ctx), root=ctx.root)
    facts = core.Facts(sql_allowed=profiles.delete_settings(profile)["sql_allowed"],
                       state=ctx.norm(str(profiles.state_dir(ctx.root, profile))),
                       vcs_git=profiles.vcs(profile) == "git")
    while True:
        try:
            return core.decide(steps, facts)
        except core.Need as need:
            facts.answers[(need.kind, need.key)] = _answer(ctx, need)


def check(event, ctx):
    if ctx.tool_name not in SHELL_TOOLS:
        return gate.allow()
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return gate.allow()
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    decision = judge(ctx, profile, command)
    if decision.verdict.kind == core.REFUSE:
        return gate.refuse(decision.verdict.reason, decision.verdict.message)
    if not core.needs_backup(decision):
        return gate.allow()
    try:  # the backup comes before the tool runs: no backup, no delete
        trash.backup(ctx.root, profiles.state_dir(ctx.root, profile), list(decision.targets), session=ctx.session_id,
                     max_mb=profiles.delete_settings(profile)["max_backup_mb"], kept=list(decision.kept),
                     order=list(decision.order))
    except trash.BackupError as exc:
        return gate.refuse(exc.reason, exc.message)
    return gate.allow()
