"""The pure decisions of the delete family (card MW-064; the test concept of 2026-11-12).

`decide(steps, facts)` judges what the delete gate read from a shell command: the `steps` (small data records the shell
reader `gate_delete.read` made, in command order) against the `facts` the shell collected. It returns a `Decision`: the
verdict, and the paths to back up. It never touches the disk, git, the environment or the clock: a fact it needs and
does not hold is asked for with `Need(kind, key)`; the shell answers it (`Facts.answers`) and calls `decide` again, so
the same facts always give the same decision (a table test fills the answers by hand).

The same module holds the other decisions of the family: the size limit of a backup, the record row, the trash folders
that are old enough to be emptied, and the lines of a `mkway delete --list` file. Behaviour is that of the gate and
`trash` before the move: the reasons, their order and their texts did not change.
"""
from __future__ import annotations

import ast
import calendar
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import helpers

ALLOW, REFUSE = "allow", "refuse"
LIST_FIX = "name the exact paths, or use `mkway delete --list <file>`"
TERMINAL = "your own terminal"
OUTSIDE_WAY_OUT = "name the path in your DONE line; the owner removes it"  # MW-107 (R274b, the chief's sentence): text only
DELETE_PROGS = {"rm", "rmdir", "unlink", "del", "erase", "rd", "remove-item", "ri"}
CMD_PROGS = {"del", "erase", "rd"}
SQL_CLIENTS = {"psql", "sqlite3", "sqlite", "duckdb", "mysql", "mariadb", "sqlcmd", "sqlplus", "isql", "usql",
               "pgcli", "mycli", "clickhouse-client", "invoke-sqlcmd"}
SQL_CALLS = {"execute", "executemany", "executescript", "sql", "read_sql", "read_sql_query"}
SQL = re.compile(r"\bdrop\s+(?:table|database|schema|view|index|materialized|trigger|function|procedure|sequence|"
                 r"type|column|constraint|user|role|extension|if)\b|\bdelete\s+from\b|\btruncate\b", re.I)
WORD = re.compile(r"\b(?:rm|rmdir|unlink|del|erase|rd|remove-item|ri)\b|-delete\b", re.I)
_VARIABLE = re.compile(r"[$`%(){}]")
_CMD_OPTION = re.compile(r"^/[A-Za-z](?::[A-Za-z-]*)?$")
_PS_PATTERN_PARAMS = {"-include", "-exclude", "-filter"}
_PY_REMOVERS = {"remove", "unlink", "rmdir", "removedirs"}
_PY_BARE = {"rmtree", "removedirs", "unlink", "rmdir"}
_PY_TEXT = re.compile(r"rmtree|os\.remove|os\.unlink|os\.rmdir|removedirs|\.unlink\(|\.rmdir\(")
STAMP = re.compile(r"^(\d{8}T\d{6}-\d{6})(?:-\d+)?$")
MB = 1024 * 1024
MAX_DEPTH = 8


# ---- data -------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Verdict:
    kind: str = ALLOW
    reason: Optional[str] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    targets: tuple = ()  # the paths to copy
    kept: tuple = ()  # clean tracked paths a `git rm` deletes (git keeps them)
    order: tuple = ()  # both, in command order


class Need(Exception):
    """A fact `decide` does not hold yet: `kind` is `norm` (a repo path of a joined path, or None outside the root),
    `exists` (does the repo path exist), `status` (the git status lines of a path list), `tracked` (the ls-files lines
    of a path) or, for a list file, `lnorm`, `lexists`, `locks`."""

    def __init__(self, kind: str, key: Any):
        super().__init__(f"{kind}: {key!r}")
        self.kind, self.key = kind, key


@dataclass
class Facts:
    """What the shell read: the profile's `sql_allowed`, the repo path of the state folder (or None), whether the profile
    is `vcs: git`, and the `answers` to the `Need`s, keyed `(kind, key)`. A git answer is `(failure, lines)`: `failure`
    is None, or the words `did not answer (<ErrorName>)` or `exited <code>`; `lines` are the non-blank output lines."""
    sql_allowed: bool = False
    state: Optional[str] = ""
    vcs_git: bool = False
    answers: dict = field(default_factory=dict)

    def ask(self, kind: str, key: Any):
        if (kind, key) not in self.answers:
            raise Need(kind, key)
        return self.answers[(kind, key)]


# ---- what the reader found --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Trash:
    arg: str  # the word after `trash` in a session's `mkway trash ...` call


@dataclass(frozen=True)
class TooDeep:
    pass


@dataclass(frozen=True)
class Unparseable:
    word: bool  # a remove word is in the text
    sql_client: bool  # destructive SQL words and a SQL client's name are in the text


@dataclass(frozen=True)
class Delete:
    prog: str
    args: tuple
    base: Optional[str]
    shell: str
    style: str


@dataclass(frozen=True)
class FindDelete:
    pass


@dataclass(frozen=True)
class XargsDelete:
    pass


@dataclass(frozen=True)
class Sql:
    text: str


@dataclass(frozen=True)
class Git:
    argv: tuple
    base: Optional[str]


@dataclass(frozen=True)
class Python:
    bodies: tuple  # the Python code texts of the command
    base: Optional[str]


def prog_name(word: str) -> str:
    name = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def python_calls(code: str):
    """(deletes, sql): the path arguments of the removal calls in a Python body (a literal text, or None when the path
    is computed) and whether a SQL call holds a destructive statement. A syntax error with a removal word in it is one
    computed delete."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return ([None] if _PY_TEXT.search(code) else []), bool(SQL.search(code))
    deletes, sql = [], False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
        owner = fn.value if isinstance(fn, ast.Attribute) else None
        if name in SQL_CALLS:
            sql = sql or any(isinstance(c, ast.Constant) and isinstance(c.value, str) and SQL.search(c.value)
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


# ---- the gate's decision ----------------------------------------------------------------------------------------------

class _Refused(Exception):
    def __init__(self, verdict: Verdict):
        super().__init__(verdict.message)
        self.verdict = verdict


class _Decider:
    def __init__(self, facts: Facts):
        self.facts = facts
        self.targets, self.kept, self.order = [], [], []

    def refuse(self, reason, message):
        raise _Refused(Verdict(REFUSE, reason, message))

    def step(self, step):
        if isinstance(step, Trash):
            self.refuse("owner-only-command", f"`mkway trash {step.arg}` is the owner's command: run it in {TERMINAL}. "
                                              "A session never reads or empties the trash of its own deletes")
        elif isinstance(step, TooDeep):
            self.refuse("delete-target-unknown", f"this command nests too deep to read; {LIST_FIX}")
        elif isinstance(step, Unparseable):
            if step.word or (not self.facts.sql_allowed and step.sql_client):
                self.refuse("delete-target-unknown", f"this command cannot be parsed and may delete; {LIST_FIX}")
        elif isinstance(step, Delete):
            self.delete(step)
        elif isinstance(step, FindDelete):
            self.refuse("delete-target-unknown", f"`find -delete` deletes a set of files computed at run time; "
                                                 f"{LIST_FIX}")
        elif isinstance(step, XargsDelete):
            self.refuse("delete-target-unknown", f"`xargs` takes the delete's targets from its input; {LIST_FIX}")
        elif isinstance(step, Sql):
            if SQL.search(step.text):
                self.sql_refuse()
        elif isinstance(step, Python):
            for body in step.bodies:
                deletes, sql = python_calls(body)
                if sql:
                    self.sql_refuse()
                for path in deletes:
                    self.target(path, step.base)
        elif isinstance(step, Git):
            self.git(list(step.argv), step.base)

    def sql_refuse(self):
        if not self.facts.sql_allowed:
            self.refuse("delete-sql", "this command holds a destructive SQL statement (DROP, DELETE FROM or "
                                      "TRUNCATE); a task with a scratch database sets `delete.sql_allowed: true` in "
                                      "its profile")

    def delete(self, step):
        prog, args, base, shell, style = step.prog, list(step.args), step.base, step.shell, step.style
        if shell == "powershell" and style != "cmd":
            paths, pattern, unknown = ps_args(args)
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
        rel = self.facts.ask("norm", joined)
        if rel is None:
            self.refuse("delete-outside-root", f"{text} lies outside the root: a session never deletes outside its "
                                               f"task; the owner does it in {TERMINAL}; {OUTSIDE_WAY_OUT}")
        if any(ch in probe for ch in "*?["):
            self.refuse("delete-wildcard", f"{text} is a wildcard: {LIST_FIX}")
        return rel

    def broad(self, rel, text):
        st = self.facts.state
        if rel == "." or st and (rel == st or st.startswith(rel + "/") or rel.startswith(st + "/")):
            self.refuse("delete-target-unknown", f"{text} is the root, the engine's state folder or a folder that "
                                                 f"holds it: too broad to back up; {LIST_FIX}")

    def target(self, raw, base):
        rel = self.place(raw, base)
        self.broad(rel, raw.strip())
        if not self.facts.ask("exists", rel):
            self.refuse("delete-target-unknown", f"{raw.strip()} does not exist; {LIST_FIX}")
        if rel not in self.targets:
            self.targets.append(rel)
            self.order.append(rel)

    # ---- git: loss of uncommitted work is a delete ------------------------------------------------------------

    def git_read(self, what, kind, key):
        """The output lines of a git read the shell made, or the refusal when git did not answer."""
        failure, lines = self.facts.ask(kind, key)
        if failure:
            self.refuse("delete-uncommitted", f"git {failure}, so the changes of {what} could not be read; no delete "
                                              "is allowed until it does")
        return list(lines)

    def changes(self, what, *paths):
        """The changed tracked files under the paths (all with none); a deletion is no work to lose."""
        lines = self.git_read(what, "status", tuple(paths))
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
        if sub == "clean":
            if has("--force", "f") and not has("--dry-run", "n"):
                self.refuse("delete-uncommitted", "`git clean -f` deletes untracked files that no commit holds and "
                                                  f"that cannot be backed up here; delete exact files: {LIST_FIX}")
            return
        if not self.facts.vcs_git:
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
            if sub == "rm" and self.git_read(rel, "tracked", rel) and rel not in self.kept:
                self.kept.append(rel)  # clean and tracked: git keeps it
                self.order.append(rel)


def decide(steps, facts: Facts) -> Decision:
    """The decision on the steps the reader found, in command order: the first refusal wins; else allow, with the paths
    to back up. Raises `Need` for a fact `facts` does not hold yet."""
    decider = _Decider(facts)
    try:
        for step in steps:
            decider.step(step)
    except _Refused as exc:
        return Decision(exc.verdict)
    return Decision(Verdict(ALLOW), tuple(decider.targets), tuple(decider.kept), tuple(decider.order))


def needs_backup(decision: Decision) -> bool:
    """True when the command passed and names something the gate must copy or record; a refused command and a command
    that deletes nothing leave no copy and no row."""
    return decision.verdict.kind == ALLOW and bool(decision.order)


# ---- the backup, its record and the trash -----------------------------------------------------------------------------

def outermost(rels) -> list:
    """The targets that lie inside no other target: copying `d` copies `d/b.txt` too."""
    return [r for r in rels if not any(o != r and r.startswith(o + "/") for o in rels)]


def too_large(total: int, max_mb: float, rels) -> Optional[Verdict]:
    """The refusal when the targets are above `delete.max_backup_mb` (a size exactly at the limit passes), else None."""
    if total > max_mb * MB:
        return Verdict(REFUSE, "delete-too-large", f"the backup of {', '.join(rels)} is {total / MB:.1f} MB, above "
                                                   f"`delete.max_backup_mb` ({max_mb:g}); this delete needs the "
                                                   "owner's terminal")
    return None


def record_row(time_text: str, session, via: str, targets, backup, by=None) -> dict:
    """The row of `deletes.jsonl`: `backup` is the backup folder as a repo path, or None; `by` only when given."""
    row = {"time": time_text, "session": session, "via": via, "targets": list(targets), "backup": backup}
    if by is not None:
        row["by"] = by
    return row


def stamp_epoch(stamp: str) -> float:
    """Seconds since 1970 (UTC) of a trash folder stamp `YYYYmmddTHHMMSS-ffffff`."""
    date, _, micro = stamp.partition("-")
    return calendar.timegm((int(date[0:4]), int(date[4:6]), int(date[6:8]), int(date[9:11]), int(date[11:13]),
                            int(date[13:15]))) + int(micro) / 1_000_000


def stale_folders(names, now_epoch: float, days: float) -> list:
    """The trash folders older than `days` by the stamp in their name, in the order given; a name that is no stamp is
    never listed."""
    out = []
    for name in names:
        m = STAMP.match(name)
        if m and now_epoch - stamp_epoch(m.group(1)) > days * 86400:
            out.append(name)
    return out


def list_problems(text: str, facts: Facts):
    """(repo paths, problems) of a `mkway delete --list` file: one exact repo path per line; each must exist, lie inside
    the root, hold no wildcard, and lie in or hold neither a closed lock target nor the state folder. A problem names
    the line number, the line and the reason. Facts asked: `lnorm` (line -> repo path or None), `lexists` (repo path ->
    bool), `locks` (repo path -> (name of the closed lock it is in or None, (name, path) of a path it holds in a
    closed lock or None))."""
    state = facts.state
    rels, problems = [], []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        why = None
        wild = any(ch in line for ch in "*?[")
        rel = None if wild else facts.ask("lnorm", line)
        if wild:
            why = "is a wildcard: list exact paths"
        elif rel is None:
            why = "lies outside the root"
        elif rel == ".":
            why = "is the root itself"
        elif state and (rel == state or state.startswith(rel + "/") or rel.startswith(state + "/")):
            why = "is or holds the engine's state folder"
        elif not facts.ask("lexists", rel):
            why = "does not exist"
        else:
            closed, held = facts.ask("locks", rel)
            if closed:
                why = f"is inside the closed lock {closed!r}"
            elif held:
                why = f"holds {held[1]}, which is inside the closed lock {held[0]!r}"
        if why:
            problems.append(f"line {number}: {line} {why}")
        elif rel not in rels:
            rels.append(rel)
    if not rels and not problems:
        problems.append("the list holds no path")
    return rels, problems
