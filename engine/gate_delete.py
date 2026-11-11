"""The delete gate (card MW-009; the owner's order of 2026-11-10: deletes are explicit, backed up, logged).

One manifest entry `delete` (shell group, `onFailure: block`). A shell command is read with the lock gate's reader
(`helpers.parse`, `expand_vars`, `folder_track`, `carriers`): quotes removed, a heredoc body blanked, every position
entered (chains, substitutions, `bash -c`, `cmd /c`, `pwsh -c`, `xargs`, `find -exec`). It refuses:
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

import ast
import os
import re

import gate
import helpers
import profiles
import runner
import trash

SHELL_TOOLS = ("Bash", "PowerShell")
LIST_FIX = "name the exact paths, or use `mkway delete --list <file>`"
TERMINAL = "your own terminal"
DELETE_PROGS = {"rm", "rmdir", "unlink", "del", "erase", "rd", "remove-item", "ri"}
CMD_PROGS = {"del", "erase", "rd"}
SQL_CLIENTS = {"psql", "sqlite3", "sqlite", "duckdb", "mysql", "mariadb", "sqlcmd", "sqlplus", "isql", "usql",
               "pgcli", "mycli", "clickhouse-client", "invoke-sqlcmd"}
SQL_CALLS = {"execute", "executemany", "executescript", "sql", "read_sql", "read_sql_query"}
_SQL = re.compile(r"\bdrop\s+(?:table|database|schema|view|index|materialized|trigger|function|procedure|sequence|"
                  r"type|column|constraint|user|role|extension|if)\b|\bdelete\s+from\b|\btruncate\b", re.I)
_VARIABLE = re.compile(r"[$`%(){}]")
_CMD_OPTION = re.compile(r"^/[A-Za-z](?::[A-Za-z-]*)?$")
_PS_PATTERN_PARAMS = {"-include", "-exclude", "-filter"}
_PY_REMOVERS = {"remove", "unlink", "rmdir", "removedirs"}
_PY_BARE = {"rmtree", "removedirs", "unlink", "rmdir"}
_PY_TEXT = re.compile(r"rmtree|os\.remove|os\.unlink|os\.rmdir|removedirs|\.unlink\(|\.rmdir\(")
_WORD = re.compile(r"\b(?:rm|rmdir|unlink|del|erase|rd|remove-item|ri)\b|-delete\b", re.I)
MAX_DEPTH = 8


class _Refused(Exception):
    def __init__(self, verdict):
        super().__init__(verdict.message)
        self.verdict = verdict


def _name(word: str) -> str:
    name = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


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


def _python_calls(code: str):
    """(deletes, sql): the path arguments of the removal calls in a Python body (a literal text, or None when the path
    is computed) and whether a SQL call holds a destructive statement. A syntax error with a removal word in it is one
    computed delete."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return ([None] if _PY_TEXT.search(code) else []), bool(_SQL.search(code))
    deletes, sql = [], False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
        owner = fn.value if isinstance(fn, ast.Attribute) else None
        if name in SQL_CALLS:
            sql = sql or any(isinstance(c, ast.Constant) and isinstance(c.value, str) and _SQL.search(c.value)
                             for arg in node.args for c in ast.walk(arg))
        first = node.args[0] if node.args else None
        if isinstance(fn, ast.Name) and name in _PY_BARE or isinstance(fn, ast.Attribute) and name == "rmtree":
            arg = first
        elif isinstance(fn, ast.Attribute) and name in _PY_REMOVERS and isinstance(owner, ast.Name) \
                and owner.id == "os":
            arg = first
        elif isinstance(fn, ast.Attribute) and name in ("unlink", "rmdir"):  # a Path: `Path("x").unlink()`
            arg = owner.args[0] if isinstance(owner, ast.Call) and len(owner.args) == 1 else None
        else:
            continue  # `items.remove(x)`, `d.pop(k)` and the like are no file removal
        deletes.append(arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None)
    return deletes, sql


class _Reader:
    def __init__(self, ctx, profile):
        self.ctx, self.profile = ctx, profile
        self.targets, self.kept, self.order = [], [], []
        self.sql_allowed = profiles.delete_settings(profile)["sql_allowed"]
        self.state = ctx.norm(str(profiles.state_dir(ctx.root, profile)))

    def refuse(self, reason, message):
        raise _Refused(gate.refuse(reason, message))

    def trash(self, command: str):
        for args in self.ctx.mkway_calls(command):
            pos = [a for a in args if not a.startswith("-")]
            if pos[:1] == ["trash"]:
                self.refuse("owner-only-command", f"`mkway trash {' '.join(pos[1:2])}` is the owner's command: run it "
                                                  f"in {TERMINAL}. A session never reads or empties the trash of its "
                                                  "own deletes")

    def text(self, cmd: str, shell: str, style: str, start, depth: int):
        if depth > MAX_DEPTH:
            self.refuse("delete-target-unknown", f"this command nests too deep to read; {LIST_FIX}")
        try:
            simples = helpers.expand_vars(helpers.parse(cmd, shell), shell, root=self.ctx.root, start=start)
        except helpers.ParseError:
            if _WORD.search(cmd) or (not self.sql_allowed and _SQL.search(cmd) and SQL_CLIENTS & {
                    _name(w) for w in re.split(r"\W+", cmd)}):
                self.refuse("delete-target-unknown", f"this command cannot be parsed and may delete; {LIST_FIX}")
            return
        for s, base in helpers.folder_track(simples, start, root=self.ctx.root):
            self.simple(s, base, cmd, shell, style, depth)
            for sub in s.subs:
                self.text(sub, shell, style, base, depth + 1)
        if shell == "bash":
            for sub in _backticks(cmd):
                self.text(sub, shell, style, start, depth + 1)

    def simple(self, s, base, whole, shell, style, depth):
        words = list(s.words)
        while words and words[0] in helpers._COMPOUND_WORDS:
            words = words[1:]
        argv = helpers._argv(words)
        prog = helpers._prog(argv)
        args = argv[1:]
        if prog in DELETE_PROGS:
            self.delete(prog, args, base, shell, style)
        elif prog == "find" and "-delete" in args:
            self.refuse("delete-target-unknown", f"`find -delete` deletes a set of files computed at run time; "
                                                 f"{LIST_FIX}")
        elif prog in SQL_CLIENTS:
            piped = "|" in s.before.replace("||", "")
            self.sql(" ".join(args + [h for h in s.heredocs if isinstance(h, str)] + ([whole] if piped else [])))
        elif prog == "git":
            self.git(argv, base)
        elif helpers._INTERPRETERS.match(prog or ""):
            self.python(prog, args, s, base)
        for name, text in helpers.carriers(s, whole):
            if text.startswith("\0") or helpers._INTERPRETERS.match(name or ""):
                continue
            if name == "xargs" and any(_name(w) in DELETE_PROGS for w in text.split()):
                self.refuse("delete-target-unknown", f"`xargs` takes the delete's targets from its input; {LIST_FIX}")
            if name in ("pwsh", "powershell"):
                self.text(text, "powershell", "", base, depth + 1)
            elif name == "cmd":
                self.text(text, "powershell", "cmd", base, depth + 1)
            else:
                self.text(text, "bash", "", base, depth + 1)

    def sql(self, text: str):
        if _SQL.search(text):
            self.sql_refuse()

    def sql_refuse(self):
        if not self.sql_allowed:
            self.refuse("delete-sql", "this command holds a destructive SQL statement (DROP, DELETE FROM or "
                                      "TRUNCATE); a task with a scratch database sets `delete.sql_allowed: true` in "
                                      "its profile")

    def python(self, prog, args, s, base):
        code, _found = helpers._code_flag(re.sub(r"[\d.]+$", "", prog), args)
        bodies = [code] if code is not None else (
            [h for h in s.heredocs if isinstance(h, str)] if helpers._reads_stdin(prog, args) else [])
        for body in bodies:
            deletes, sql = _python_calls(body)
            if sql:
                self.sql_refuse()
            for path in deletes:
                self.target(path, base)

    def delete(self, prog, args, base, shell, style):
        if shell == "powershell" and style != "cmd":
            paths, pattern, unknown = self.ps_args(args)
            if unknown:
                self.refuse("delete-target-unknown", f"{unknown} in a PowerShell delete hides its targets; {LIST_FIX}")
            if pattern:
                self.refuse("delete-wildcard", f"{pattern} selects files by pattern; {LIST_FIX}")
        else:
            paths, options = [], True
            for a in args:
                if options and a == "--":
                    options = False
                elif options and (a.startswith("-") and len(a) > 1 or (
                        (style == "cmd" or prog in CMD_PROGS) and _CMD_OPTION.match(a))):
                    continue
                else:
                    paths.append(a)
        if not paths:
            self.refuse("delete-target-unknown", f"`{prog}` names no target here (it may read them from input); "
                                                 f"{LIST_FIX}")
        for path in paths:
            self.target(path, base)

    @staticmethod
    def ps_args(args):
        """(paths, a pattern parameter or None, an unreadable parameter or None) of a PowerShell delete."""
        paths, pattern, unknown, i = [], None, None, 0
        while i < len(args):
            a = args[i]
            if re.match(r"@[A-Za-z_]", a):
                unknown = "a splat"
            elif a.startswith("-") and len(a) > 1:
                name, colon, value = a.lower().partition(":")
                name = helpers._ps_param(name)
                if name in helpers._PS_SWITCHES:
                    pass
                elif name in helpers._PS_VALUED or name in helpers._PS_PATH_PARAMS:
                    if not colon:
                        value = args[i + 1] if i + 1 < len(args) else ""
                        i += 1
                    else:
                        value = a.split(":", 1)[1]
                    if name in _PS_PATTERN_PARAMS:
                        pattern = f"`{a.split(':', 1)[0]}`"
                    elif name in helpers._PS_PATH_PARAMS:
                        paths.append(value)
                else:
                    unknown = unknown or f"the parameter `{a}`"
            else:
                paths.append(a)
            i += 1
        return paths, pattern, unknown

    def place(self, raw, base):
        """The repo path of a literal path, or the refusal: computed, outside the root, a wildcard."""
        text = (raw or "").strip()
        probe = text
        for var in helpers._ROOT_VARS:  # the project folder variable is a literal root
            if probe == var or probe.startswith(var + "/"):
                probe = "." + probe[len(var):]
        if raw is None or not probe or _VARIABLE.search(probe):
            self.refuse("delete-target-unknown", f"the target {raw!r} is computed (a variable, a substitution or "
                                                 f"empty), so it cannot be backed up; {LIST_FIX}")
        joined = helpers.join_folder(base, probe)
        if joined is None:
            self.refuse("delete-target-unknown", f"the folder this command runs in cannot be read, so the target "
                                                 f"{text} cannot be placed; {LIST_FIX}")
        rel = self.ctx.norm(joined)
        if rel is None:
            self.refuse("delete-outside-root", f"{text} lies outside the root: a session never deletes outside its "
                                               f"task; the owner does it in {TERMINAL}")
        if any(ch in probe for ch in "*?["):
            self.refuse("delete-wildcard", f"{text} is a wildcard: {LIST_FIX}")
        return rel

    def broad(self, rel, text):
        st = self.state
        if rel == "." or st and (rel == st or st.startswith(rel + "/") or rel.startswith(st + "/")):
            self.refuse("delete-target-unknown", f"{text} is the root, the engine's state folder or a folder that "
                                                 f"holds it: too broad to back up; {LIST_FIX}")

    def target(self, raw, base):
        rel = self.place(raw, base)
        self.broad(rel, raw.strip())
        if not os.path.lexists(self.ctx.root / rel):
            self.refuse("delete-target-unknown", f"{raw.strip()} does not exist; {LIST_FIX}")
        if rel not in self.targets:
            self.targets.append(rel)
            self.order.append(rel)

    # ---- git: loss of uncommitted work is a delete ------------------------------------------------------------

    def git_read(self, what, *args):
        """The stdout lines of a git read at the root, or the refusal when git does not answer."""
        try:
            proc = runner.git(self.ctx.root, "--literal-pathspecs", *args)
        except (runner.SubprocessError, runner.Refused, OSError) as exc:
            self.refuse("delete-uncommitted", f"git did not answer ({type(exc).__name__}), so the changes of {what} "
                                              "could not be read; no delete is allowed until it does")
        if proc.returncode != 0:
            self.refuse("delete-uncommitted", f"git exited {proc.returncode}, so the changes of {what} could not be "
                                              "read; no delete is allowed until it does")
        return [line for line in proc.stdout.splitlines() if line.strip()]

    def changes(self, what, *paths):
        """The changed tracked files under the paths (all with none); a deletion is no work to lose."""
        lines = self.git_read(what, "status", "--porcelain", "--untracked-files=no", *(["--", *paths] if paths else []))
        return [line[3:] for line in lines if line[:2] not in (" D", "D ")]

    def lose(self, what, names, effect):
        self.refuse("delete-uncommitted", f"{what} has uncommitted changes ({', '.join(names[:5])}"
                                          f"{', ...' if len(names) > 5 else ''}); {effect} would lose work that no "
                                          "commit holds. Commit the changes first; reverting them is the owner's "
                                          f"step in {TERMINAL}")

    def git(self, argv, base):
        sub, args, folder = helpers._git_sub(argv)
        if sub not in ("clean", "reset", "restore", "checkout", "rm"):
            return
        if folder is not None:
            if _VARIABLE.search(folder):
                self.refuse("delete-target-unknown", f"the `git -C` folder {folder} is computed; {LIST_FIX}")
            base = helpers.join_folder(base, folder)
        valued = {"restore": {"-s", "--source"}, "checkout": {"-b", "-B", "--orphan"}}.get(sub, set())
        opts, pos, after, i = [], [], None, 0
        while i < len(args):
            a = args[i]
            if a == "--":
                after = args[i + 1:]
                break
            if a in valued:
                i += 1
            elif a.startswith("-") and len(a) > 1:
                opts.append(a)
            else:
                pos.append(a)
            i += 1

        def has(long, short):
            return long in opts or any(o.startswith("-") and not o.startswith("--") and short in o[1:] for o in opts)
        git_on = profiles.vcs(self.profile) == "git"
        if sub == "clean":
            if has("--force", "f") and not has("--dry-run", "n"):
                self.refuse("delete-uncommitted", "`git clean -f` deletes untracked files that no commit holds and "
                                                  f"that cannot be backed up here; delete exact files: {LIST_FIX}")
            return
        if not git_on:
            return
        if sub == "reset":
            if "--hard" in opts:
                names = self.changes("the tree")
                if names:
                    self.lose("the tree", names, "`git reset --hard`")
            return
        if sub == "restore":
            if has("--staged", "S") and not has("--worktree", "W"):
                return  # the index only
            paths = pos + (after or [])
        elif sub == "checkout":
            paths = after if after is not None else ["."] if "." in pos else []
        else:  # rm
            if "--cached" in opts or has("--dry-run", "n"):
                return
            paths = pos + (after or [])
        for raw in paths:
            rel = self.place(raw, base)
            if sub == "rm":
                self.broad(rel, raw.strip())
            names = self.changes(rel, rel)
            if names:
                self.lose(rel, names, f"`git {sub}`")
            if sub == "rm" and self.git_read(rel, "ls-files", "--", rel) and rel not in self.kept:
                self.kept.append(rel)  # clean and tracked: git keeps it
                self.order.append(rel)


def scan(ctx, profile, command: str):
    """(a refusal verdict or None, the reader: `targets` the paths to copy, `kept` the clean tracked paths a `git rm`
    deletes (git keeps them), `order` both in command order)."""
    shell = "powershell" if ctx.tool_name == "PowerShell" else "bash"
    reader = _Reader(ctx, profile)
    try:
        reader.trash(command)
        reader.text(command, shell, "", _start(ctx), 0)
    except _Refused as exc:
        return exc.verdict, reader
    return None, reader


def check(event, ctx):
    if ctx.tool_name not in SHELL_TOOLS:
        return gate.allow()
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return gate.allow()
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    verdict, reader = scan(ctx, profile, command)
    if verdict or not reader.order:
        return verdict or gate.allow()
    try:  # the backup comes before the tool runs: no backup, no delete
        trash.backup(ctx.root, profiles.state_dir(ctx.root, profile), reader.targets, session=ctx.session_id,
                     max_mb=profiles.delete_settings(profile)["max_backup_mb"], kept=reader.kept,
                     order=reader.order)
    except trash.BackupError as exc:
        return gate.refuse(exc.reason, exc.message)
    return gate.allow()
