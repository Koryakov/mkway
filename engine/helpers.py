"""Shared helpers for the gates (card MW-003, deliverable 1; spec section 0, defects 2 and 19; D-10).

- `norm(path, root)`: one repo-relative form with forward slashes, for absolute, relative, Git Bash `/c/...`,
  `C:\\...`, `~`, `${CLAUDE_PROJECT_DIR}`, repo-top prefixed and quoted paths; None outside the root. It never
  matches by base name; `matches(rel, entry)` compares whole repo paths, folders and globs.
- `commit_cmd(cmd)`: each `git commit` in a shell command: its message (`-m`, `-F`, `--file`, a heredoc), its
  explicit paths (after `--`, or as arguments), `-a`/`--all`, `-i`/`--include`.
- `shell_writes(cmd)`: the paths a shell command may write. Decided limit (ruled 09.11): it detects
  cheap shapes on a best-effort basis; a command it cannot parse writes everywhere; a known program with no write
  shape writes nothing. The backstop for anything that reaches git is `lock-closed-commit`.
- `mkway_calls(cmd)`: the arguments of every call of the engine's command line, in any spelling.

Pure functions: no file is written, no program is run.
"""
from __future__ import annotations

import ast
import fnmatch
import json
import os
import re
import shlex
from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Optional

CASE_FOLD = os.name == "nt"
_DRIVE = re.compile(r"^[A-Za-z]:[/\\]")
_GITBASH = re.compile(r"^/([A-Za-z])(/|$)")
_ROOT_VARS = ("${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR", "%CLAUDE_PROJECT_DIR%", "$env:CLAUDE_PROJECT_DIR")


# ---- paths --------------------------------------------------------------------------------------------------------

def _clean(path: str) -> str:
    p = path.strip()
    while len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'":
        p = p[1:-1].strip()
    return p


def _fold(text: str) -> str:
    return text.casefold() if CASE_FOLD else text


def _posix_abs(text: str, drive_root: bool) -> str:
    """An absolute path text in one posix form: `C:/x/y` on a drive root, `/x/y` otherwise; `..` collapsed."""
    text = text.replace("\\", "/")
    m = _GITBASH.match(text)
    if drive_root and m:
        text = m.group(1) + ":/" + text[m.end():]
    if _DRIVE.match(text):
        head, rest = text[:2].upper(), text[2:]
        return head + os.path.normpath(rest).replace("\\", "/") if rest else head + "/"
    return str(PurePosixPath(os.path.normpath(text).replace("\\", "/")))


def norm(path, root, *, top_prefix: str = "", home=None, cwd=None) -> Optional[str]:
    """The repo-relative posix form of `path`, `.` for the root itself, or None outside the root."""
    if not isinstance(path, str) or not path.strip():
        return None
    p = _clean(path).replace("\\", "/")
    for var in _ROOT_VARS:
        if p == var or p.startswith(var + "/"):
            p = "./" + p[len(var) + 1:]
            break
    root_text = str(Path(root)).replace("\\", "/")
    drive_root = bool(_DRIVE.match(root_text))
    if p == "~" or p.startswith("~/"):
        if home is None:
            home = os.path.expanduser("~")
        p = str(home).replace("\\", "/") + p[1:]
    is_abs = bool(_DRIVE.match(p)) or p.startswith("/")
    if not is_abs:
        rel = p[2:] if p.startswith("./") else p
        prefix = top_prefix.strip("/") if top_prefix else ""
        if prefix and (_fold(rel) == _fold(prefix) or _fold(rel).startswith(_fold(prefix) + "/")):
            rel = rel[len(prefix):].lstrip("/") or "."
            base = root_text
        else:
            base = str(cwd).replace("\\", "/") if cwd is not None else root_text
        p = base.rstrip("/") + "/" + rel
    full = _posix_abs(p, drive_root)
    top = _posix_abs(root_text, drive_root).rstrip("/")
    if _fold(full) == _fold(top):
        return "."
    if not _fold(full).startswith(_fold(top) + "/"):
        return None
    return full[len(top) + 1:].rstrip("/") or "."


def top_prefix(root) -> str:
    """The root's path below the top of its git work tree (`sub/task`), found by walking up to a `.git` entry;
    "" at the top or with no git. No program is run."""
    here = Path(root).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".git").exists():
            return here.relative_to(parent).as_posix() if parent != here else ""
    return ""


def matches(rel: Optional[str], entry: str) -> bool:
    """True when the repo path `rel` is the entry, lies in the entry folder, or matches the entry glob. Never by
    base name: a bare entry matches only a path at the root."""
    if rel is None or not entry:
        return False
    e = entry.strip().replace("\\", "/")
    if e.startswith("./"):
        e = e[2:]
    r, e = _fold(rel), _fold(e)
    if any(ch in e for ch in "*?["):
        if "/" not in e.rstrip("/"):
            return glob_re(e.rstrip("/")).fullmatch(r.rsplit("/", 1)[-1]) is not None  # gitignore: any folder
        if e.endswith("/**") and r == e[:-3]:
            return True
        return glob_re(e.rstrip("/")).fullmatch(r) is not None
    e = e.rstrip("/")
    return r == e or (e not in ("", ".") and r.startswith(e + "/")) or e in ("", ".")


def glob_re(pattern: str):
    """A path glob as a regex: `**` crosses folders, `*` and `?` stay inside one folder."""
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "[":
            j = pattern.find("]", i + 1)
            if j < 0:
                out.append(re.escape(ch))
                i += 1
            else:
                out.append("[" + pattern[i + 1:j].replace("\\", "\\\\") + "]")
                i = j + 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("".join(out), re.S)


# ---- shell parsing ---------------------------------------------------------------------------------------------------

HEREDOC = re.compile(r"(?<!<)<<(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PREFIXES = {"env", "command", "exec", "nohup", "time", "sudo", "then", "do", "else", "if", "while", "until",
             "!", "{", "}", "builtin", "nice"}
_CAT_SUB = re.compile(r"^\$\(\s*cat\s+<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\)$", re.S)
_INTERPRETERS = re.compile(r"^(python[0-9.]*|py|pythonw)(\.exe)?$", re.I)
_SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
_PWSH = {"powershell", "pwsh", "powershell.exe", "pwsh.exe"}


_PS_DASHES = {0x2013: "-", 0x2014: "-", 0x2015: "-"}


class ParseError(Exception):
    pass


@dataclass
class Simple:
    """One simple command: its words (env prefixes kept), its redirect targets, its heredoc bodies."""
    words: list = field(default_factory=list)
    redirects: list = field(default_factory=list)
    heredocs: list = field(default_factory=list)
    subs: list = field(default_factory=list)  # command substitutions inside words
    depth: int = 0  # parenthesis depth: a subshell's folder change ends with it (batch 3, H5)
    before: str = ""  # the separator tokens in front of it ("" at the start; close-fix 11)
    after: str = ""  # the separator token after it ("" at the end)
    shape: str = ""  # the unknown shapes of the text it came from, comma-joined (remainder item 10, R95 (1b))


def _split_heredocs(text: str):
    lines = text.split("\n")
    out, bodies, i = [], defaultdict(deque), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in HEREDOC.finditer(line):
            dash, delim, body = m.group(1), m.group(3), []
            while i < len(lines):
                cur = lines[i].rstrip("\r")
                i += 1
                if (cur.lstrip("\t") if dash else cur) == delim:
                    break
                body.append(cur)
            bodies[delim].append("\n".join(body))
    return "\n".join(out), bodies


_SEP_CHARS = ";&|()"
_WORD_BOUNDARY = r"(?:^|[\s;&|(){}])"
_KEYWORD_SHAPES = (  # written for this reader: a keyword is a whole word that the tracker does not model
    ("case", re.compile(_WORD_BOUNDARY + r"case(?=\s)")),
    ("function", re.compile(_WORD_BOUNDARY + r"function(?=\s)")),
    ("trap", re.compile(_WORD_BOUNDARY + r"trap(?=\s)")),
    ("process substitution", re.compile(r"[<>]\(")),
    ("CDPATH", re.compile(r"CDPATH")),
    ("nested block", re.compile(_WORD_BOUNDARY + r"(?:then|do|else|elif|\{|!)\s+(?:if|for|while|until|case|select|\{|\()"
                                                  r"(?=[\s(])")),
)


def _blank_text(text: str, shell: str):
    """(the text with quoted strings and comment text turned to spaces, whether a comment has a separator after it on
    its line or stands right after a separator). A `#` is a comment only at the start of a word, as the shell reads it;
    the tracker's own lexer reads it as a word (remainder item 10, H1)."""
    esc = "`" if shell == "powershell" else "\\"
    out, comment_shape, i, n = [], False, 0, len(text)
    while i < n:
        ch = text[i]
        if ch == esc:
            out.append(ch)
            if i + 1 < n:
                out.append(text[i + 1])
            i += 2
            continue
        if ch in "'\"":
            ansi = ch == "'" and i > 0 and text[i - 1] == "$" and shell != "powershell"
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if (text[j] == esc and (ch == '"' or ansi)) else 1
            out.append(ch)
            out.append(" " * max(0, min(j, n) - i - 1))
            if j < n:
                out.append(ch)
            i = j + 1
            continue
        if ch == "#" and (i == 0 or text[i - 1].isspace() or text[i - 1] in _SEP_CHARS):
            end = text.find("\n", i)
            end = n if end < 0 else end
            if (i > 0 and text[i - 1] in _SEP_CHARS) or any(c in _SEP_CHARS for c in text[i:end]):
                comment_shape = True
            out.append(" " * (end - i))
            i = end
            continue
        out.append(ch)
        i += 1
    return "".join(out), comment_shape


def unknown_shape(cmd: str, shell: str = "bash") -> str:
    """The names of the shapes in a command text (quoted strings and heredoc bodies blanked) that the folder and name
    tracker does not model, comma-joined, or "" (remainder item 10, R95 (1b); H1-H6, M4): a `#` comment that has a
    separator after it on its line or stands right after a separator; `case`, `function`, `trap`; a process
    substitution `<(` or `>(`; `CDPATH`; a nested keyword block (`then`, `do`, `else`, `elif`, `{` or `!` followed
    by `if`, `for`, `while`, `until`, `case`, `select`, `{` or `(`). The tracker then holds every folder and name as
    unknown and the command's writes as `everywhere`."""
    if not isinstance(cmd, str):
        return ""
    text, _bodies = _split_heredocs(cmd)
    blank, comment = _blank_text(text, shell)
    found = ["comment"] if comment else []
    found += [name for name, rx in _KEYWORD_SHAPES if rx.search(blank)]
    return ",".join(found)


def _tokens(text: str, shell: str) -> list:
    lex = shlex.shlex(text, posix=True, punctuation_chars="();<>|&\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    if shell == "powershell":
        lex.escape = "`"
    try:
        return list(lex)
    except ValueError as exc:  # no closing quotation, no escaped character
        raise ParseError(str(exc)) from None


def _is_punct(tok: str) -> bool:
    return bool(tok) and all(ch in "();<>|&\n" for ch in tok)


def _inner_subs(word: str) -> list:
    """The texts of `$(...)` and backtick substitutions inside a word."""
    out, i = [], 0
    while True:
        j = word.find("$(", i)
        if j < 0:
            break
        depth, k = 0, j + 1
        while k < len(word):
            if word[k] == "(":
                depth += 1
            elif word[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        out.append(word[j + 2:k])
        i = k + 1
    out += re.findall(r"`([^`]*)`", word)
    return out


def parse(cmd: str, shell: str = "bash") -> list:
    """The simple commands of a shell text. Raises ParseError when it cannot be read."""
    if not isinstance(cmd, str):
        raise ParseError("not a text")
    # PowerShell takes U+2013, U+2014 and U+2015 as `-` (remainder item 5, H10)
    text = cmd.replace("\\", "/").translate(_PS_DASHES) if shell == "powershell" else cmd
    text, bodies = _split_heredocs(text)
    toks = _tokens(text, shell)
    shape = unknown_shape(cmd, shell)
    if "CDPATH" not in shape and any(re.match(r"CDPATH(?:=|$)", t) for t in toks):  # `export "CDPATH=x"`
        shape = shape + ",CDPATH" if shape else "CDPATH"
    simples, cur, depth = [], Simple(), 0
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok in ("<(", ">("):  # a process substitution: its text is read as a `$(…)` is (remainder item 1, H8g)
            sub, i = _proc_sub(toks, i + 1)
            cur.words.append(tok + "sub)")
            cur.subs.append(sub)
            continue
        if _is_punct(tok):
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            if nxt in ("<(", ">(") and tok in ("<", ">", ">>"):  # `done < <(cmd)`, `> >(tee x)`
                sub, i = _proc_sub(toks, i + 2)
                cur.subs.append(sub)
                if tok != "<":
                    cur.redirects.append(nxt + "sub)")
                continue
            if ">" in tok:
                nxt = toks[i + 1] if i + 1 < len(toks) else None
                if cur.words and cur.words[-1].isdigit():
                    cur.words.pop()  # the fd number of `2>`
                if nxt is None or _is_punct(nxt):
                    raise ParseError("a redirect without a target")
                if not (tok.endswith("&") and (nxt.isdigit() or nxt == "-")):
                    cur.redirects.append(nxt)
                i += 2
                continue
            if "<" in tok:
                nxt = toks[i + 1] if i + 1 < len(toks) else None
                delim = nxt[1:] if (tok == "<<" and nxt and nxt.startswith("-")) else nxt
                if tok in ("<<", "<<-") and delim is not None and bodies.get(delim):
                    cur.heredocs.append(bodies[delim].popleft())
                i += 2
                continue
            before = tok
            if cur.words or cur.redirects:
                cur.after = tok
                simples.append(cur)
            else:
                before = cur.before + tok  # `a && (cd x)`: keep the `&&` in front of the subshell
            for ch in tok:  # remainder item 12: a `)` that closes no `(` is not a depth change
                if ch == "(":
                    depth += 1
                elif ch == ")" and depth:
                    depth -= 1
            cur = Simple(depth=depth, before=before)
            i += 1
            continue
        cur.words.append(tok)
        for sub in _inner_subs(tok):
            m = _CAT_SUB.match("$(" + sub + ")")
            if m and bodies.get(m.group(1)):
                continue  # `$(cat <<EOF ...)`: the body is text, read by commit_cmd
            cur.subs.append(sub)
        i += 1
    if cur.words or cur.redirects:
        simples.append(cur)
    for s in simples:  # keep the heredoc bodies of `$(cat <<EOF)` words, in order
        s.words = [_cat_body(w, bodies) for w in s.words]
        s.shape = shape
    return simples


def _proc_sub(toks: list, i: int):
    """(the text of a `<(…)`/`>(…)` whose tokens start at `i`, the index after its closing parenthesis). The rest of a
    glued closing token (`);`) is left in `toks` for the caller. Raises ParseError when it is not closed."""
    parts, depth = [], 1
    while i < len(toks):
        tok = toks[i]
        if not _is_punct(tok):
            parts.append(shlex.quote(tok))
            i += 1
            continue
        for k, ch in enumerate(tok):
            depth += (ch == "(") - (ch == ")")
            if depth == 0:
                parts.append(tok[:k])
                rest = tok[k + 1:]
                if rest:
                    toks[i] = rest
                    return " ".join(parts), i
                return " ".join(parts), i + 1
        parts.append(tok)
        i += 1
    raise ParseError("a process substitution without its closing parenthesis")


def _cat_body(word: str, bodies) -> str:
    m = _CAT_SUB.match(word)
    if m and bodies.get(m.group(1)):
        return bodies[m.group(1)].popleft().rstrip("\n")
    return word


_WRAPPER_VALUED = {  # list item 8 (R44 row 1): the options of a wrapper that take a separate value
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "nice": {"-n", "--adjustment"},
}


def _skip_options(words: list, i: int, valued: set) -> int:
    while i < len(words) and words[i].startswith("-"):
        i += 2 if words[i] in valued else 1
    return i


def _argv(words: list) -> list:
    """The words without leading env assignments and wrapper prefixes; `env`, `timeout` and `nice` are read through
    with their options (and `timeout`'s duration) to the command they wrap (list item 8)."""
    i = 0
    while i < len(words):
        w = words[i]
        name = w.replace("\\", "/").rsplit("/", 1)[-1].lower()
        name = name[:-4] if name.endswith(".exe") else name
        if name == "env":  # clusters, attached values and long prefixes (remainder item 8, H7)
            _opts, i = _env_read(words, i)
            continue
        if name in _WRAPPER_VALUED:
            i = _skip_options(words, i + 1, _WRAPPER_VALUED[name])
            if name == "timeout" and i < len(words):
                i += 1  # the duration
            continue
        if _ASSIGN.match(w) or w in _PREFIXES:
            i += 1
            continue
        break
    return words[i:]


def _prog(argv: list) -> str:
    if not argv:
        return ""
    name = argv[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


# ---- commit_cmd -------------------------------------------------------------------------------------------------------

@dataclass
class Commit:
    message: Optional[str]
    paths: list
    all: bool = False
    include: bool = False
    allow_empty: bool = False
    amend: bool = False
    cwd: Optional[str] = None
    message_file: Optional[str] = None
    folder_unreadable: bool = False  # list item 9: a `cd` or `-C` to a variable or unreadable target


_GIT_GLOBAL_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_COMMIT_VALUE_LONG = {"--message", "--file", "--author", "--date", "--template", "--fixup", "--squash", "--cleanup",
                      "--trailer", "--reuse-message", "--reedit-message", "--pathspec-from-file", "--gpg-sign"}
_COMMIT_VALUE_SHORT = set("mFCct")


def _git_sub(argv: list):
    """(subcommand, its arguments, the -C folder) of a git argv, or (None, [], None)."""
    i, cwd = 1, None
    while i < len(argv):
        a = argv[i]
        if a in _GIT_GLOBAL_VALUE:
            if a == "-C" and i + 1 < len(argv):  # two or more `-C`: an unreadable folder (close-fix 11, R83)
                cwd = argv[i + 1] if cwd is None else "$-C"
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a, argv[i + 1:], cwd
    return None, [], cwd


_VAR_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _expand_word(word: str, known: dict) -> str:
    return _VAR_REF.sub(lambda m: known.get(m.group(1) or m.group(2), m.group(0)), word)


_ALL_UNKNOWN = {"eval", "source", ".", "mapfile", "readarray", "select", "getopts"}
_DEFAULT_ASSIGN = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:?=")
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DECLARERS = {"declare", "local", "typeset", "readonly", "unset", "read"}
_SPACE = re.compile(r"\s")


def _progs(simples: list, shell: str):
    for s in simples:
        words = list(s.words)
        if words[:1] == ["select"]:
            yield "select"
        while words and words[0] in _COMPOUND_WORDS:
            words = words[1:]
        yield _prog(_argv(words))
        for sub in s.subs:
            try:
                yield from _progs(parse(sub, shell), shell)
            except ParseError:
                yield "eval"  # an unreadable substitution: every name unknown


def _bound_names(s: Simple) -> set:
    """The names a simple command binds other than by a plain assignment (close-fix 12, B-H2)."""
    words = list(s.words)
    out = set()
    if words[:1] in (["for"], ["select"]) and len(words) > 1:
        out.add(words[1])
    while words and words[0] in _COMPOUND_WORDS:
        words = words[1:]
    matches = [re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\+?=", w) for w in words]
    if words and all(matches):  # an assignment-only command that is not plain (a prefix `B=x cmd` binds nothing)
        out |= {m.group(1) for m in matches}
    argv = _argv(words)
    prog = _prog(argv)
    if prog in _DECLARERS or prog == "export":
        out |= {a.split("=", 1)[0] for a in argv[1:] if _NAME.match(a.split("=", 1)[0])}
    if prog == "printf":
        out |= {argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "-v"}
    return out


def expand_vars(simples: list, shell: str = "bash", root=None, start="") -> list:
    """The simples with `$NAME` and `${NAME}` replaced where NAME holds a literal: every binding of it so far is a
    plain assignment (an assignment-only command, or `export NAME=…`) that runs unconditionally at top level, the
    position rule of `folder_track`: after `&&` it counts when everything in front of it in the chain cannot fail (a
    plain assignment, a `cd` to a folder that exists, which is read from `root` and `start`; false blocks, E98).
    Any other binding (`for`, `read`, `declare`, `local`, `+=`, `printf -v`, `unset`, an assignment in a subshell, a
    pipeline, a compound or after `&&`/`||` that may not run) makes the name unknown for good; an assignment of an
    unreadable value forgets it, an empty value and a value that holds a space, a tab or a newline too (an unquoted
    `$NAME` is then no, or several, words, and the quotes are not kept). `eval`, `source`/`.`,
    `mapfile`/`readarray`, `select`, `getopts`, `${NAME:=…}` or `${NAME=…}` anywhere make every name unknown. A
    prefix assignment (`B=x cmd`) does not count, as in the shell. Bash only (list item 12, R44 row 5; close-fix 12,
    B-H2)."""
    if shell != "bash":
        return simples
    if any(s.shape for s in simples):  # remainder item 10: a shape the tracker does not model: every name unknown
        return simples
    if any(p in _ALL_UNKNOWN for p in _progs(simples, shell)) or any(
            _DEFAULT_ASSIGN.search(w) for s in simples for w in s.words + s.redirects):
        return simples
    runs = [r for _s, _folder, r in _track(simples, start, root)]
    known, unknown, out = {}, set(), []
    for s, plain in zip(simples, runs):
        out.append(replace(s, words=[_expand_word(w, known) for w in s.words],
                           redirects=[_expand_word(r, known) for r in s.redirects]))
        names = s.words[1:] if s.words[:1] == ["export"] else s.words
        if names and all(_ASSIGN.match(w) for w in names) and plain:
            for w in names:
                name, _, value = w.partition("=")
                value = _expand_word(value, known)
                if name in unknown or not value or _UNREADABLE.search(value) or _SPACE.search(value):
                    known.pop(name, None)
                else:
                    known[name] = value
            continue
        for name in _bound_names(s):
            unknown.add(name)
            known.pop(name, None)
    return out


def expanded_text(cmd: str, shell: str = "bash", root=None, start="") -> str:
    """The command's words and redirects after `expand_vars`, one simple per line; the text itself when it does not
    parse. The literal-reach check reads it too (list item 12)."""
    try:
        simples = expand_vars(parse(cmd, shell), shell, root=root, start=start)
    except ParseError:
        return cmd
    return "\n".join(" ".join(s.words + s.redirects) for s in simples)


def parse_ok(cmd: str, shell: str = "bash") -> bool:
    """True when the shell text parses (list item 7, R43 point 2; MW-004 uses it too)."""
    try:
        parse(cmd, shell)
    except ParseError:
        return False
    return True


_TOKEN_SPLIT = re.compile(r"[\s;&|()<>'\"`]+")


def names_git_commit(cmd: str) -> bool:
    """A cheap literal scan: a `git` token (or a path ending in `git` / `git.exe`) followed later by a `commit`
    token (list item 7)."""
    tokens = [t for t in _TOKEN_SPLIT.split(cmd or "") if t]
    for i, t in enumerate(tokens):
        name = t.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if name in ("git", "git.exe") and "commit" in tokens[i + 1:]:
            return True
    return False


_CARRIER_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "script"}
_INTERPRETER = re.compile(r"(?:python[\d.]*|py|perl|node)")
_CARRIED_SPLIT = re.compile(r"[\s;&|()<>\[\],{}]+")


def _after(rest: list, test) -> Optional[str]:
    for i, a in enumerate(rest):
        if test(a):
            return " ".join(rest[i + 1:])
    return None


def _gitish(word: str) -> bool:
    """A `git` word: its base name is `git` or `git.exe`, backticks around it ignored (`digit`, `legit` are not; O6)."""
    return _base(word.strip("`")) in ("git", "git.exe")


def _git_position(word: str) -> bool:
    """A word that may run git: a `git` word, or a `$` or backtick word (its value is not known; H8j)."""
    return _gitish(word) or word.startswith(("$", "`")) or word.endswith("`")


def _names_commit_at(words: list, k: int) -> bool:
    """True when the subcommand after the git-position word `words[k]`, past git's global options only, is the
    whole word `commit` (R95a: `commit.gpgsign`, `--no-commit` and `git log --grep commit` are not it)."""
    return _git_sub(["git"] + [w.strip("`") for w in words[k + 1:]])[0] == "commit"


def _text_names_commit(text: str) -> bool:
    """Quotes and backslashes removed, a `git` token (or a `$`/backtick word in its place) whose subcommand is
    `commit`, or one followed later by an `alias.` value or a `GIT_CONFIG_` word (close-fix 3, R83; remainder
    item 1, R95a, O6)."""
    toks = [t for t in _CARRIED_SPLIT.split(re.sub(r"[\"'\\]", "", text)) if t]
    for i, t in enumerate(toks):
        if _git_position(t):
            if _names_commit_at(toks, i) or any(x.lower().startswith(("alias.", "git_config_")) for x in toks[i + 1:]):
                return True
    return False


_PROCESS_START = re.compile(r"subprocess|os\.system|os\.exec|\bsystem\s*\(|\bexec\w*\s*\(|spawn|popen|child_process",
                            re.I)
_PS_CARRY = ("command", "commandwithargs")


def _code_flag(prog: str, rest: list):
    """(code text, found) of an interpreter's code option, read as a cluster or an attached form (`-c"…"`, `-Ic`,
    `perl -we`, `node -pe`, `--eval=…`; remainder item 1, H8c, H8d); (None, False) when there is none, and
    (None, True) when a script or a module runs instead."""
    code_chars = {"perl": "eE", "node": "ep"}.get(prog, "c")
    stop_chars = {"perl": "MmIix0l", "node": "r"}.get(prog, "WXm")
    separate = {"node": {"-r", "--require"}}.get(prog, {"-W", "-X"} if prog not in ("perl",) else set())
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in separate:
            i += 2
            continue
        if a.startswith("--"):
            name, eq, value = a.partition("=")
            if prog == "node" and name in ("--eval", "--print"):
                return (value if eq else (rest[i + 1] if i + 1 < len(rest) else "")), True
            i += 1
            continue
        if a == "-" or not a.startswith("-"):
            return None, True  # stdin (`-`) or a script file: no code option
        for k, ch in enumerate(a[1:], 1):
            if ch in code_chars:
                return (a[k + 1:] or (rest[i + 1] if i + 1 < len(rest) else "")), True
            if ch in stop_chars:
                if ch == "m" and prog not in ("perl", "node"):
                    return None, True  # `python -m module`
                break
        i += 1
    return None, False


def _reads_stdin(prog: str, rest: list) -> bool:
    """True when a shell or an interpreter takes its program from stdin: no code option and no script argument, or
    an explicit `-` / `-s`."""
    for a in rest:
        if a in ("-", "-s") or (prog in _CARRIER_SHELLS and re.fullmatch(r"-[A-Za-z]*s[A-Za-z]*", a)):
            return True
        if not a.startswith("-"):
            return False
    return True


def carriers(s: Simple, whole: str) -> list:
    """The texts a simple command runs that its own words do not show, as (program, text) pairs: a shell's `-c`
    text, a heredoc or piped stdin; `cmd /c`/`/k`/`/r`; `pwsh`/`powershell` with any prefix of `-Command` or
    `-CommandWithArgs`; `xargs`, `eval`, `find -exec`, `trap` text; an interpreter's code option. An interpreter fed
    by stdin counts only when its text holds a process-start call (R98). Each carrier word is read wherever it
    stands in the simple, so one behind `stdbuf` or `winpty` counts too (remainder item 1). `whole` is the text a
    pipe may feed. The text `\0encoded` marks a `-EncodedCommand` prefix, `-e` or `-ec`; `\0xargs-git` an
    `xargs git` with no subcommand of its own."""
    out, words = [], s.words
    piped = "|" in s.before.replace("||", "")
    stdin = "\n".join([h for h in s.heredocs if isinstance(h, str)] + ([whole] if piped else []))
    for j, w in enumerate(words):
        prog = _base(w)
        prog = prog[:-4] if prog.endswith(".exe") else prog
        rest = words[j + 1:]
        if prog in _CARRIER_SHELLS:
            text = _after(rest, lambda a: re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", a) is not None)
            if text is not None:
                out.append((prog, text))
            elif prog != "script" and _reads_stdin(prog, rest) and stdin:
                out.append((prog, stdin))
        elif prog == "cmd":
            text = _after(rest, lambda a: a.lower() in ("/c", "/k", "/r"))
            if text is not None:
                out.append((prog, text))
        elif prog in ("pwsh", "powershell"):
            for i, a in enumerate(rest):
                name = a.lower().lstrip("-/") if a[:1] in "-/" else ""
                if name and (any(full.startswith(name) for full in _PS_CARRY) or name == "cwa"):
                    out.append((prog, " ".join(rest[i + 1:])))
                    break
                if name and (name in ("e", "ec") or "encodedcommand".startswith(name)):
                    out.append((prog, "\0encoded"))
                    break
            else:
                if not rest and stdin:
                    out.append((prog, stdin))
        elif prog == "xargs":
            out.append((prog, " ".join(rest)))
            k = next((i for i, a in enumerate(rest) if _gitish(a)), None)
            if k is not None and _git_sub(["git"] + rest[k + 1:])[0] is None:
                out.append((prog, "\0xargs-git"))
        elif prog in ("eval", "trap"):
            out.append((prog, " ".join(rest)))
        elif prog == "find":
            text = _after(rest, lambda a: a in ("-exec", "-execdir", "-ok", "-okdir"))
            if text is not None:
                out.append((prog, text))
        elif _INTERPRETER.fullmatch(prog):
            code, found = _code_flag(re.sub(r"[\d.]+$", "", prog), rest)
            if code is not None:
                out.append((prog, code))
            elif _reads_stdin(prog, rest) and stdin and _PROCESS_START.search(stdin):
                out.append((prog, stdin))
    return out


def _all_simples(cmd: str, shell: str, root=None, start=""):
    """Yield (simple, its level's text) for every simple command, those inside substitutions included, after
    `expand_vars` (the top level read from `root` and `start`); a substitution that does not parse is yielded as
    (None, its text)."""
    try:
        simples = expand_vars(parse(cmd, shell), shell, root=root, start=start)
    except ParseError:
        yield None, cmd
        return
    for s in simples:
        yield s, cmd
        for sub in s.subs:
            yield from _all_simples(sub, shell)


def carried_commit(cmd: str, shell: str = "bash") -> Optional[str]:
    """What runs a git commit the gate cannot read, or None (R83 fail-closed; remainder item 1, R95 (2a)): a carrier
    whose text names one (close-fix 3), `xargs git` with no subcommand, a PowerShell encoded command, or a simple
    command whose `git` word (or `$`/backtick word) has the subcommand `commit` where `commit_cmd` does not read it
    (behind `stdbuf`, in a `function` body, `$G commit`). A top-level text that does not parse is item 7's."""
    try:
        parse(cmd, shell)
    except ParseError:
        return None
    for s, whole in _all_simples(cmd, shell):
        if s is None:
            if names_git_commit(whole):
                return "a substitution that cannot be parsed"
            continue
        for prog, text in carriers(s, whole):
            if text == "\0encoded":
                return f"`{prog}` with an encoded command"
            if text == "\0xargs-git":
                return "`xargs git` with its subcommand from stdin"
            if _text_names_commit(text):
                return f"`{prog}`"
        argv = _argv(s.words)
        read_at = len(s.words) - len(argv) if _prog(argv) == "git" and _git_sub(argv)[0] == "commit" else None
        for k, w in enumerate(s.words):
            if k and s.words[k - 1] in _GIT_GLOBAL_VALUE:
                continue  # the value of `git -C "$D"`, not a program
            if k != read_at and _git_position(w) and _names_commit_at(s.words, k):
                return f"`{' '.join(s.words[:k + 2])}`"
    return None


_COMMIT_LONG = {  # close-fix 8 (A-M2, R83): the exact long options of `git commit`; any other refuses
    "--all", "--patch", "--interactive", "--reuse-message", "--reedit-message", "--fixup", "--squash",
    "--reset-author", "--short", "--branch", "--porcelain", "--long", "--null", "--file", "--author", "--date",
    "--message", "--template", "--signoff", "--no-signoff", "--trailer", "--no-verify", "--verify", "--allow-empty",
    "--allow-empty-message", "--cleanup", "--edit", "--no-edit", "--amend", "--no-post-rewrite", "--include",
    "--only", "--pathspec-file-nul", "--untracked-files", "--verbose", "--quiet", "--dry-run", "--status",
    "--no-status", "--gpg-sign", "--no-gpg-sign", "--ahead-behind", "--no-ahead-behind"}
_GIT_CONFIG_ENV = re.compile(r"^GIT_CONFIG_(?:COUNT|KEY_\d+|VALUE_\d+|PARAMETERS)=")
_GIT_BUILTINS = None


def git_builtins() -> set:
    """git's built-in commands: the static engine key `lock_gate.git_builtins` in defaults.json (R90), the union of the
    first list and a git's own `--list-cmds=builtins` (MW-031); `mkway check` compares it with git's list in the
    owner's terminal, and a profile adds names with `lock_gate.git_builtins_extra`. The hook runs no git process."""
    global _GIT_BUILTINS
    if _GIT_BUILTINS is None:
        data = json.loads((Path(__file__).resolve().parent / "defaults.json").read_text(encoding="utf-8"))
        _GIT_BUILTINS = set(data["lock_gate"]["git_builtins"])
    return _GIT_BUILTINS


def git_form_problem(cmd: str, shell: str = "bash", extra=frozenset()):
    """(reason id, what) for a git call the reader cannot check, or None (close-fix 8, A-M2, R83 «refused outright»):
    `--pathspec-from-file` (`pathspec-unparsed`); a `GIT_CONFIG_` assignment anywhere in a command that runs git, a
    git subcommand not in the built-in list (`-c alias.*`, a configured alias), or a `git commit` long option that is
    not an exact name the reader knows (`--inc`) (`command-unparsed`). A text that does not parse is item 7's."""
    try:
        simples = parse(cmd, shell)
    except ParseError:
        return None
    config_env = any(_GIT_CONFIG_ENV.match(w) for s in simples for w in s.words)
    for s in simples:
        argv = _argv(s.words)
        if _prog(argv) == "git":
            if config_env:
                return "command-unparsed", "a `GIT_CONFIG_` variable can turn a git command into another one"
            sub, args, _cwd = _git_sub(argv)
            if sub is not None and sub not in git_builtins() and sub not in extra:
                return "command-unparsed", f"`git {sub}` is not a built-in git command (an alias or an external one)"
            if sub == "commit":
                i = 0
                while i < len(args):
                    a = args[i]
                    if a == "--":
                        break
                    name, eq, _value = a.partition("=")
                    if name == "--pathspec-from-file":
                        return "pathspec-unparsed", "`--pathspec-from-file` names paths the gate does not read"
                    if a.startswith("--") and name not in _COMMIT_LONG:
                        return "command-unparsed", f"`{name}` is not an exact `git commit` option the gate knows"
                    takes_value = (a.startswith("--") and name in _COMMIT_VALUE_LONG and not eq) or (
                        not a.startswith("--") and len(a) == 2 and a[0] == "-" and a[1] in _COMMIT_VALUE_SHORT)
                    i += 2 if takes_value else 1
        for sub in s.subs:
            found = git_form_problem(sub, shell, extra)
            if found:
                return found
    return None


def commit_cmd(cmd: str, *, root=None, shell: str = "bash", start="") -> list:
    """Each `git commit` of the command, in order (an empty list when there is none or it cannot be read). Each
    commit's folder follows `cd`, `pushd`/`popd`, `Set-Location` and `git -C` from `start` (`""` the root, a repo
    path, None unreadable), through the one folder helper shared with `shell_writes` (list item 9, R44 row 2)."""
    try:
        simples = expand_vars(parse(cmd, shell), shell, root=root, start=start)
    except ParseError:
        return []
    out = []
    for s, base in folder_track(simples, start, root=root):
        found = _commit_of(s, root, base)
        if found:
            out.append(found)
        for sub in s.subs:
            out += commit_cmd(sub, root=root, shell=shell, start=base)
    return out


def _commit_of(s: Simple, root, base="") -> Optional[Commit]:
    argv = _argv(s.words)
    if _prog(argv) != "git":
        return None
    sub, args, gcwd = _git_sub(argv)
    if sub != "commit":
        return None
    folder = base
    if gcwd is not None:
        target = _clean(gcwd)
        folder = None if (not target or _UNREADABLE.search(target)) else join_folder(base, target)
    c = Commit(message=None, paths=[], cwd=folder or None, folder_unreadable=folder is None)
    cwd = c.cwd
    messages, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            c.paths += args[i + 1:]
            break
        if a.startswith("--"):
            name, eq, value = a.partition("=")
            if name in _COMMIT_VALUE_LONG and not eq:
                value = args[i + 1] if i + 1 < len(args) else ""
                i += 1
            if name == "--message":
                messages.append(value)
            elif name == "--file":
                c.message_file = value
            elif name == "--all":
                c.all = True
            elif name == "--include":
                c.include = True
            elif name == "--allow-empty":
                c.allow_empty = True
            elif name == "--amend":
                c.amend = True
            i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            j = 1
            while j < len(a):
                ch = a[j]
                if ch in _COMMIT_VALUE_SHORT:
                    value = a[j + 1:]
                    if not value:
                        value = args[i + 1] if i + 1 < len(args) else ""
                        i += 1
                    if ch == "m":
                        messages.append(value)
                    elif ch == "F":
                        c.message_file = value
                    break
                if ch == "a":
                    c.all = True
                elif ch == "i":
                    c.include = True
                j += 1
            i += 1
            continue
        c.paths.append(a)
        i += 1
    if messages:
        c.message = "\n\n".join(messages)
    elif c.message_file == "-":
        c.message = s.heredocs[0].rstrip("\n") if s.heredocs else None
    elif c.message_file and root is not None:
        base = Path(root) / (cwd or "")
        try:
            c.message = (base / c.message_file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            c.message = None
    return c


# ---- shell_writes ---------------------------------------------------------------------------------------------------

UNPARSED, CAPABLE = "unparsed", "capable"


@dataclass
class Writes:
    """`everywhere` carries a reason (list item 5, R43): `unparsed` when the shell text or a Python body does not
    parse, else `capable` (a risky module, a computed path, a program with no readable targets)."""
    everywhere: bool = False
    paths: list = field(default_factory=list)
    unparsed: bool = False

    @property
    def reason(self) -> Optional[str]:
        if not self.everywhere:
            return None
        return UNPARSED if self.unparsed else CAPABLE

    def add(self, other: "Writes") -> None:
        self.everywhere = self.everywhere or other.everywhere
        self.unparsed = self.unparsed or (other.everywhere and other.unparsed)
        self.paths += [p for p in other.paths if p not in self.paths]


_NULLS = {"/dev/null", "nul", "$null", "/dev/stdout", "/dev/stderr"}
_TOUCHERS = {"rm", "rmdir", "touch", "mkdir", "unlink", "shred", "truncate"}
_GIT_EVERYWHERE = {"reset", "clean", "stash", "switch", "merge", "rebase", "pull", "cherry-pick", "revert", "am",
                   "apply", "checkout-index", "read-tree", "update-index", "filter-branch"}
_PS_WRITERS = {"set-content", "add-content", "out-file", "new-item", "remove-item", "copy-item", "move-item",
               "rename-item", "clear-content", "export-csv", "tee-object", "sc", "ac", "ni", "ri", "rm", "del",
               "copy", "cp", "move", "mv", "erase", "rd", "rmdir", "md", "mkdir", "mi", "cpi", "rni", "clc"}
_PS_ALIAS = {"cpi": "copy-item", "copy": "copy-item", "cp": "copy-item", "mi": "move-item", "move": "move-item",
             "mv": "move-item", "rni": "rename-item"}
_PS_PATH_PARAMS = {"-path", "-literalpath", "-filepath", "-destination"}
_PS_PARAM_ALIAS = {"-lp": "-literalpath", "-pspath": "-literalpath", "-ea": "-erroraction",
                   "-ev": "-errorvariable", "-wa": "-warningaction", "-wv": "-warningvariable",
                   "-ia": "-informationaction", "-iv": "-informationvariable", "-ov": "-outvariable",
                   "-ob": "-outbuffer", "-pv": "-pipelinevariable", "-vb": "-verbose", "-db": "-debug",
                   "-cf": "-confirm", "-wi": "-whatif"}
_PS_SWITCHES = {"-force", "-append", "-nonewline", "-recurse", "-noclobber", "-passthru", "-whatif", "-confirm",
                "-container", "-verbose", "-debug", "-notypeinformation", "-useculture", "-asbytestream",
                "-includetypeinformation"}
_PS_VALUED = {"-value", "-encoding", "-inputobject", "-itemtype", "-name", "-newname", "-width", "-delimiter",
              "-filter", "-include", "-exclude", "-credential", "-stream", "-erroraction", "-warningaction",
              "-informationaction", "-errorvariable", "-warningvariable", "-informationvariable", "-outvariable",
              "-outbuffer", "-pipelinevariable", "-target", "-quotefields", "-usequotes", "-header",
              "-progressaction"}
_PS_KNOWN = _PS_PATH_PARAMS | _PS_SWITCHES | _PS_VALUED


def _ps_param(low: str) -> str:
    """A PowerShell parameter name in full: its alias (`-LP`, `-ea`), or the one known name it is a prefix of, two
    characters included (`-L` is `-literalpath`; close-fix 6, A-H3). An unknown name or an ambiguous prefix (`-P`)
    stays as written, so `_ps_unknown` sees it."""
    if low in _PS_PARAM_ALIAS:
        return _PS_PARAM_ALIAS[low]
    if low in _PS_KNOWN or len(low) < 2:
        return low
    hits = [full for full in _PS_KNOWN if full.startswith(low)]
    return hits[0] if len(hits) == 1 else low


def _ps_unknown(args: list) -> bool:
    """True when a parameter of a writer cmdlet is not one the reader knows, or is an ambiguous prefix: its write
    targets cannot be read, so the write is `everywhere` (close-fix 6)."""
    for a in args:
        if a.startswith("-") and len(a) > 1 and _ps_param(a.lower().partition(":")[0]) not in _PS_KNOWN:
            return True
    return False
_EVERYWHERE_WORDS = re.compile(r"::(write|delete|move|copy|create|append|replace)|^(invoke-expression|iex)$", re.I)


_CD = {"cd", "chdir", "pushd", "sl", "set-location", "push-location"}
_POPD = {"popd", "pop-location"}
_PUSH = {"pushd", "push-location"}
_UNREADABLE = re.compile(r"[$`*?{}()\[\]%]")


def _is_abs(p: str) -> bool:
    return (bool(_DRIVE.match(p)) or p.startswith("/") or p == "~" or p.startswith("~/")
            or any(p == v or p.startswith(v + "/") for v in _ROOT_VARS))


def join_folder(base, path: str):
    """`path` read from the folder `base`: `""` is the root (paths stay root-relative), None is a folder that cannot
    be read (a relative path then gives None); an absolute path is kept."""
    p = _clean(path).replace("\\", "/")
    if _is_abs(p):
        return p
    if base is None:
        return None
    return p if not base else base.rstrip("/") + "/" + p


def _cd_target(prog: str, args: list):
    """The folder a `cd`-like command names, or None when it names none it can read (no argument, `-`, `~`, a
    variable, a substitution or a glob)."""
    if prog in ("set-location", "sl", "push-location") or prog in ("cd", "chdir", "pushd"):
        named = _ps_named(args, "-path") + _ps_named(args, "-literalpath")
        rest = named or [a for a in args if not a.startswith("-") or a == "-"]
        if len(rest) != 1:
            return None
        target = _clean(rest[0])
        if not target or target in ("-", "~") or _UNREADABLE.search(target):
            return None
        return target
    return None


def _stack_option(args: list) -> bool:
    """True when the arguments of `pushd`, `popd`, `Push-Location` or `Pop-Location` hold an option other than a path
    (remainder item 14, M3): `-n`, `±N`, `-q`, `-StackName:s`, `-PassThru`, … The path parameters (`-Path`,
    `-LiteralPath`, with their value) and `--` are not options, and `-` alone is a word."""
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("+") and a[1:].isdigit():
            return True
        if a.startswith("-") and len(a) > 1 and a != "--":
            name, colon, _value = a.lower().partition(":")
            if _ps_param(name) not in ("-path", "-literalpath"):
                return True
            i += 1 if colon else 2  # `-Path:x` carries its value; `-Path x` takes the next word
            continue
        i += 1
    return False


_ENV_LONG = {"--ignore-environment": "-i", "--null": "-0", "--unset": "-u", "--chdir": "-C", "--split-string": "-S",
             "--block-signal": "--block-signal", "--default-signal": "--default-signal",
             "--ignore-signal": "--ignore-signal", "--list-signal-handling": "--list-signal-handling",
             "--debug": "-v", "--help": "--help", "--version": "--version", "--argv0": "-a"}
_ENV_SHORT_VALUED = "uCSa"


def _env_read(words: list, i: int):
    """(options, the index after them) of the `env` at `words[i]`. Each option is (`-x` or a long name, its value);
    long names are resolved by getopt's unique-prefix rule; a strict prefix of `--chdir` or `--split-string` gives
    (`?prefix`, it) and an unknown long option (`?unknown`, it), which refuse; a short cluster holding a valued
    letter (`-vC dir`, `-iS…`) takes its value (remainder item 8, H7)."""
    out, j = [], i + 1
    while j < len(words) and words[j].startswith("-") and words[j] != "-":
        a = words[j]
        if a == "--":
            return out, j + 1
        if a.startswith("--"):
            name, eq, value = a.partition("=")
            hits = [full for full in _ENV_LONG if full.startswith(name)]
            full = name if name in _ENV_LONG else (hits[0] if len(hits) == 1 else None)
            if full is None:
                out.append(("?unknown", name))
                j += 1
                continue
            if full != name and full in ("--chdir", "--split-string"):
                out.append(("?prefix", name))
            short = _ENV_LONG[full]
            if short[1:] in _ENV_SHORT_VALUED and not eq:
                value = words[j + 1] if j + 1 < len(words) else ""
                j += 1
            out.append((short, value if short[1:] in _ENV_SHORT_VALUED else None))
            j += 1
            continue
        for k, ch in enumerate(a[1:], 1):
            if ch in _ENV_SHORT_VALUED:
                value = a[k + 1:]
                if not value:
                    value = words[j + 1] if j + 1 < len(words) else ""
                    j += 1
                out.append(("-" + ch, value))
                break
            out.append(("-" + ch, None))
        j += 1
    return out, j


def _env_options(words: list):
    """The options of every `env` in a simple's wrapper chain, after any wrapper (`timeout 9 env …`, `env env …`;
    remainder item 8, H7)."""
    out, i = [], 0
    while i < len(words):
        w = words[i]
        name = _base(w)
        name = name[:-4] if name.endswith(".exe") else name
        if name == "env":
            opts, i = _env_read(words, i)
            out += opts
            continue
        if name in _WRAPPER_VALUED:
            i = _skip_options(words, i + 1, _WRAPPER_VALUED[name])
            if name == "timeout" and i < len(words):
                i += 1
            continue
        if _ASSIGN.match(w) or w in _PREFIXES:
            i += 1
            continue
        break
    return out


def _env_chdir(words: list):
    """The folder the `env -C`/`--chdir` options of the chain give the wrapped command, a later one read from an
    earlier one, or None (close-fix 7, A-H2; remainder item 8)."""
    folder = None
    for a, value in _env_options(words):
        if a == "-C":
            folder = value if folder is None else join_folder(folder, value)
    return folder


def env_problem(cmd: str, shell: str = "bash") -> Optional[str]:
    """What makes an `env` of the command unreadable, or None: `-S`/`--split-string` (its command text is not read;
    close-fix 7, B-H4), a strict prefix of `--chdir` or `--split-string`, or an unknown long option (remainder item
    8, H7)."""
    try:
        simples = parse(cmd, shell)
    except ParseError:
        return None
    for s in simples:
        for a, value in _env_options(s.words):
            if a == "-S":
                return "`env -S` runs a command text the gate cannot read"
            if a == "?prefix":
                return f"`env {value}` is a shortened `--chdir` or `--split-string`"
            if a == "?unknown":
                return f"`env {value}` is not an `env` option the gate knows"
        for sub in s.subs:
            found = env_problem(sub, shell)
            if found:
                return found
    return None


def cdpath_cd(cmd: str, shell: str = "bash") -> bool:
    """True when the command text holds `CDPATH` and a simple command (at any level) runs `cd` or another folder
    change: the folder it lands in is not the one the text names, and the write it then makes may name a bare file
    that literal reach cannot see (remainder item 10, H5b)."""
    try:
        simples = parse(cmd, shell)
    except ParseError:
        return False
    if not any("CDPATH" in s.shape.split(",") for s in simples):
        return False
    for s, _whole in _all_simples(cmd, shell):
        if s is None:
            continue
        words = list(s.words)
        while words and words[0] in _COMPOUND_WORDS:
            words = words[1:]
        if _prog(_argv(words)) in _CD:
            return True
    return False


def env_split(cmd: str, shell: str = "bash") -> bool:
    """True when an `env` of the command cannot be read (`env_problem`)."""
    return env_problem(cmd, shell) is not None


_COMPOUND_OPEN = {"if", "while", "until", "for", "select", "case", "{"}
_COMPOUND_CLOSE = {"fi", "done", "esac", "}"}
_COMPOUND_WORDS = _COMPOUND_OPEN | _COMPOUND_CLOSE | {"then", "else", "elif", "do", "!", "function"}


def _plain_position(s: Simple, compound: int, after_ok: bool = False):
    """"plain" when a folder change in `s` runs for sure and stays (close-fix 11, B-H3): the first command of its
    and-or list, at top level, not in a pipeline or the background, not in a compound. "chain" when the one
    difference is that it follows `&&`: it holds for the rest of that `&&` chain only (a later command of the chain
    runs only if it ran), and the folder is unknown once the chain ends. False otherwise. `after_ok` (false blocks,
    E97, E98): the command in front of the `&&` ran for sure and cannot fail (an assignment of a value that runs no
    command, a `cd` to a folder that exists), so `s` runs for sure too: "plain"."""
    if s.depth or compound or (s.words and s.words[0] in _COMPOUND_WORDS):
        return False
    after = s.after.replace("&&", "").replace("||", "")
    if any(ch in after for ch in "&|"):
        return False
    if not any(ch in s.before for ch in "&|"):
        return "plain"
    if s.before.strip() != "&&":
        return False
    return "plain" if after_ok else "chain"


_RUNS_A_COMMAND = re.compile(r"`|\$[({]")


def _assigns_only(s: Simple) -> bool:
    """True for an assignment-only command (`A=x B=y`, `export A=x`) that cannot fail: no value runs a command
    (`$(…)`, a backtick, `$((…))`) or uses a `${…}` form (`${x:?}` fails), and it has no redirect."""
    words = s.words[1:] if s.words[:1] == ["export"] else s.words
    return bool(words) and not s.redirects and not s.subs and all(
        _ASSIGN.match(w) and not _RUNS_A_COMMAND.search(w) for w in words)


def _exists(root, folder) -> bool:
    if root is None or folder is None:
        return root is None
    if _is_abs(folder):  # a Git-Bash folder (`/c/...`) on a drive root is that drive's folder (close-fix 14)
        p = Path(_posix_abs(folder, bool(_DRIVE.match(str(Path(root)).replace("\\", "/")))))
    else:
        p = Path(root) / folder
    try:
        return p.is_dir()
    except OSError:
        return False


def folder_track(simples: list, start, root=None):
    """Yield (simple, folder) with the folder each simple command runs in: from `start` (`""` the root, a repo path,
    or None when it cannot be read), following `cd`, `chdir`, `pushd`/`popd`, `Set-Location`/`sl`,
    `Push-Location`/`Pop-Location`; a subshell's change ends with it. `env -C <dir>` changes the folder of its own
    command only; `pushd`/`popd` with `-n` or `±N` make the folder unknown (close-fix 7). A change counts only in a
    plain position (`_plain_position`) and, when `root` is given, to a folder that exists; any other makes the
    folder unknown (close-fix 11, B-H3). One helper for writes and commits (H5, R44)."""
    for s, folder, _runs in _track(simples, start, root):
        yield s, folder


def _track(simples: list, start, root=None):
    """`folder_track`'s walk: yield (simple, folder, runs), `runs` true when the simple is in a plain position, that
    is, it runs for sure (`_plain_position`; after `&&` only when everything in front of it in the chain cannot fail:
    a `cd` to a folder that exists, an assignment that runs no command; false blocks, E97, E98). `expand_vars` takes
    the flags to read an assignment that stands after such a `cd`."""
    if any(s.shape for s in simples):  # remainder item 10: a shape the tracker does not model: every folder unknown
        for s in simples:
            yield s, None, False
        return
    bases, stacks, cur, compound, chain_depth = {0: start}, {0: []}, 0, 0, None
    sure_depth = None  # the depth of a `cd` to an existing folder whose `&&` chain is still running (E96)
    after_ok = False  # the simple in front ran for sure and cannot fail (E97, E98)
    for s in simples:
        was_ok, after_ok = after_ok, False
        if sure_depth is not None:
            if "||" in s.before:  # a `||` may run after a failed command in the old folder: the owner's X11 addendum
                for k in bases:
                    if k >= sure_depth:
                        bases[k] = None
                sure_depth = None
            elif s.before.strip() != "&&":  # the and-or list ended with `;`: the folder stays
                sure_depth = None
        if chain_depth is not None and s.before.strip() != "&&":  # the `&&` chain that carried a folder change ended
            for k in bases:  # remainder item 12 (H4b): the depth where the chain's `cd` ran, and below
                if k >= chain_depth:
                    bases[k] = None
            chain_depth = None
        d = s.depth
        if d > cur:
            for k in range(cur + 1, d + 1):
                bases[k], stacks[k] = bases[k - 1], list(stacks[k - 1])
        cur = d
        words = list(s.words)
        while words and words[0] in _COMPOUND_WORDS:  # `{ cd x`, `do cd x`: the command after the keyword
            words = words[1:]
        argv = _argv(words)
        prog = _prog(argv)
        plain = _plain_position(s, compound, was_ok)
        if any(not _ASSIGN.match(w) and w not in ("builtin", "command", "time") for w in words[:len(words) - len(argv)]):
            plain = False  # remainder item 13 (H5a): a wrapper (`timeout`, `env`, `nice`, `nohup`, …) runs no shell `cd`
        chdir = _env_chdir(s.words)
        if chdir is None:
            yield s, bases[d], plain == "plain"
        else:
            target = _clean(chdir)
            yield s, (None if not target or _UNREADABLE.search(target) else join_folder(bases[d], target)), False
        first = s.words[0] if s.words else ""
        if first in _COMPOUND_OPEN:
            compound += 1
        elif first in _COMPOUND_CLOSE and compound:
            compound -= 1
        if (prog in _PUSH or prog in _POPD) and _stack_option(argv[1:]):
            bases[d], stacks[d] = None, []
            continue
        if (prog in _CD or prog in _POPD) and not plain:
            bases[d], stacks[d] = None, []
            continue
        if prog in _CD:
            if prog in _PUSH:
                stacks[d].append(bases[d])
            target = _cd_target(prog, argv[1:])
            folder = None if target is None else join_folder(bases[d], target)
            bases[d] = folder if _exists(root, folder) else None
            # X11 addendum: a change followed by `&&` or `||` (or one after `&&`) holds only through the pure `&&`
            # chain; `cd x && b || c` runs c after a failed cd, in the old folder. False blocks (E96, E97): a change
            # in a plain position to a folder the gate read as existing cannot fail, so a `;` after its `&&` chain no
            # longer ends it (`sure_depth`: only a `||` does) and the next command of the chain runs for sure too
            # (`after_ok`); one that may not run (`plain == "chain"`) or whose folder was not read ends the chain at
            # the first separator that is not `&&`, as before
            sure = root is not None and bases[d] is not None and plain == "plain"
            if plain == "chain" or (("&&" in s.after or "||" in s.after) and not sure):
                chain_depth = d if chain_depth is None else min(chain_depth, d)
            elif sure and ("&&" in s.after or "||" in s.after):
                sure_depth = d if sure_depth is None else min(sure_depth, d)
            after_ok = sure
        elif prog in _POPD:
            bases[d] = stacks[d].pop() if stacks[d] else None
        elif plain == "plain" and _assigns_only(s):
            after_ok = True


def _based(w: Writes, base) -> Writes:
    out = Writes(everywhere=w.everywhere, unparsed=w.unparsed)
    for p in w.paths:
        joined = join_folder(base, p)
        if joined is None:
            out.everywhere = True
        elif joined not in out.paths:
            out.paths.append(joined)
    return out


def shell_writes(cmd: str, shell: str = "bash", cwd="", root=None) -> Writes:
    """The paths a shell command may write, each read from the folder it runs in (`cwd`: `""` the root, a repo path,
    or None when the start folder cannot be read; batch 3 H5 and item 15). With `root`, a `cd` to a folder that does
    not exist makes the folder unknown (close-fix 11)."""
    try:
        simples = expand_vars(parse(cmd, shell), shell, root=root, start=cwd)
    except ParseError:
        return Writes(everywhere=True, unparsed=True)
    out = Writes(everywhere=any(s.shape for s in simples))  # remainder item 10: a shape: writes everywhere
    for s, base in folder_track(simples, cwd, root=root):
        w = _writes_of(s, shell)
        for sub in s.subs:
            w.add(shell_writes(sub, shell))
        out.add(_based(w, base))
    return out


def _non_options(args: list) -> list:
    return [a for a in args if not a.startswith("-") or a == "-"]


_WRITER_NAMES = ({"tee", "tee-object", "cp", "mv", "install", "ln", "chmod", "chown", "dd", "sed", "perl", "find",
                  "xargs", "git", "eval", "cmd"} | _TOUCHERS | _SHELLS | _PWSH)
_READ_ONLY = {"echo", "printf", "cat", "grep", "egrep", "fgrep", "rg", "ls", "dir", "head", "tail", "wc", "diff",
              "cmp", "sort", "uniq", "cut", "tr", "which", "type", "whereis", "man", "help", "file", "stat", "test",
              "[", "[[", "true", "false", ":", "cd", "pwd", "export", "set", "unset", "read", "sleep", "date",
              "basename", "dirname", "realpath", "readlink", "less", "more", "jq", "id", "whoami", "hostname"}


def _writer_word(word: str) -> bool:
    name = _base(word)
    name = name[:-4] if name.endswith(".exe") else name
    return name in _WRITER_NAMES or bool(_INTERPRETERS.match(name))


def _behind_unknown(prog: str, argv: list) -> bool:
    """True when the program is one the reader does not know (not a writer it reads, not a read-only program) and a
    later word of the command is a known writer: `stdbuf -o0 cp …`, `winpty tee …` (remainder item 11, H13). The
    reader does not enter such a program, so the write is `capable`."""
    if not prog or prog in _WRITER_NAMES or prog in _READ_ONLY or _INTERPRETERS.match(prog) or prog in _PS_WRITERS:
        return False
    return any(_writer_word(a) for a in argv[1:])


def _writes_of(s: Simple, shell: str) -> Writes:
    w = Writes(paths=[r for r in s.redirects if r.lower() not in _NULLS])
    argv = _argv(s.words)
    prog = _prog(argv)
    args = argv[1:]
    if any(_EVERYWHERE_WORDS.search(word) for word in argv):
        w.everywhere = True
    if _behind_unknown(prog, argv) or any(x in ("<(sub)", ">(sub)") for x in s.words + s.redirects):
        w.everywhere = True  # remainder item 11 (H13): an unknown program in front of a writer, a process substitution
    if prog == "eval":
        w.everywhere = True
    elif prog == "tee" or prog == "tee-object":
        w.paths += _non_options(args) if prog == "tee" else _ps_paths(args, positional=0)
    elif prog in ("cp", "mv", "install", "ln"):
        w.add(_copy_like(prog, args))
    elif prog in _TOUCHERS:
        w.paths += _values_skipped(args, {"-s", "--size", "-m", "--mode"})
    elif prog in ("chmod", "chown"):
        w.paths += _non_options(args)[1:]
    elif prog == "dd":
        w.paths += [a[3:] for a in args if a.startswith("of=")]
    elif prog == "sed":
        w.add(_sed(args))
    elif prog == "perl" and any(a.startswith("-i") or (a.startswith("-") and "i" in a[1:]) for a in args):
        w.everywhere = True
    elif prog in ("find",):
        if "-delete" in args or "-exec" in args or "-execdir" in args or "-ok" in args:
            w.everywhere = True
    elif prog == "xargs":
        w.everywhere = True
    elif _INTERPRETERS.match(prog or ""):
        w.add(_python_writes(args, s.heredocs))
    elif prog in _SHELLS:
        for i, a in enumerate(args):
            if a == "-c" and i + 1 < len(args):
                w.add(shell_writes(args[i + 1], "bash"))
                break
        else:
            if _reads_stdin(prog, args):  # remainder item 11 (H13c): a shell fed by a heredoc or stdin
                w.everywhere = True
    elif prog in _PWSH:
        for i, a in enumerate(args):
            if a.lower() in ("-command", "-c") and i + 1 < len(args):
                w.add(shell_writes(" ".join(args[i + 1:]), "powershell"))
                break
    elif prog == "cmd":
        for i, a in enumerate(args):
            if a.lower() == "/c" and i + 1 < len(args):
                w.add(shell_writes(" ".join(args[i + 1:]), "bash"))
                break
    elif prog == "git":
        w.add(_git_writes(argv))
    elif shell == "powershell" and prog in _PS_WRITERS:
        w.add(_ps_writes(prog, args))
    return w


def _values_skipped(args: list, valued: set) -> list:
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a in valued:
            i += 2
            continue
        if not a.startswith("-"):
            out.append(a)
        i += 1
    return out


def _into(dest: str, sources: list, folder: bool = False) -> list:
    """The paths a copy, move or link writes at `dest` (close-fix 15, A-L1): into a folder destination (`.`, `..`, a
    trailing `/`, or `folder` for `-t`) each source's base name, `<dest>/<basename>`; else `dest` itself. With no
    source the folder itself stays, so a folder that holds a target is still checked."""
    d = dest.replace("\\", "/")
    if not (folder or d in (".", "..") or d.endswith("/")) or not sources:
        return [dest]
    head = d if d.endswith("/") else d + "/"
    return [head + s.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] for s in sources]


_COPY_COMMON = {"--backup", "--suffix", "--target-directory", "--no-target-directory", "--verbose", "--help",
                "--version", "--debug", "--context"}
_COPY_LONG = {  # GNU long options (remainder item 6, H11): any other, or an ambiguous prefix, writes everywhere
    "cp": _COPY_COMMON | {"--archive", "--attributes-only", "--copy-contents", "--dereference", "--force",
                          "--interactive", "--link", "--no-dereference", "--no-clobber", "--no-preserve", "--parents",
                          "--preserve", "--recursive", "--reflink", "--remove-destination", "--sparse",
                          "--strip-trailing-slashes", "--symbolic-link", "--update", "--one-file-system",
                          "--keep-directory-symlink"},
    "mv": _COPY_COMMON | {"--force", "--interactive", "--no-clobber", "--no-copy", "--strip-trailing-slashes",
                          "--update", "--exchange"},
    "install": _COPY_COMMON | {"--compare", "--directory", "--group", "--mode", "--owner", "--preserve-timestamps",
                               "--strip", "--strip-program", "--preserve-context"},
    "ln": _COPY_COMMON | {"--directory", "--force", "--interactive", "--logical", "--no-dereference", "--physical",
                          "--relative", "--symbolic"},
}
_COPY_LONG_VALUED = {"--suffix", "--target-directory", "--mode", "--owner", "--group", "--strip-program", "--sparse",
                     "--no-preserve"}
_COPY_SHORT_VALUED = {"cp": "tS", "mv": "tS", "install": "tSmog", "ln": "tS"}


def _copy_args(prog: str, args: list):
    """(operands, the `-t` folder or None, an unknown option) of `cp`, `mv`, `install` or `ln`: `-t`, `-t<dir>`, a
    `-t` in a cluster, `--target-directory` and any unique prefix of a long option, attached or separate
    (remainder item 6, H11)."""
    longs, short_valued = _COPY_LONG[prog], _COPY_SHORT_VALUED[prog]
    rest, target, unknown, i = [], None, False, 0
    while i < len(args):
        a = args[i]
        if a == "--":
            rest += args[i + 1:]
            break
        if a.startswith("--"):
            name, eq, value = a.partition("=")
            hits = [full for full in longs if full.startswith(name)]
            full = name if name in longs else (hits[0] if len(hits) == 1 else None)
            if full is None:
                unknown = True
            elif full in _COPY_LONG_VALUED and not eq:
                value = args[i + 1] if i + 1 < len(args) else ""
                i += 1
            if full == "--target-directory":
                target = value
            i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            for k, ch in enumerate(a[1:], 1):
                if ch in short_valued:
                    value = a[k + 1:]
                    if not value:
                        value = args[i + 1] if i + 1 < len(args) else ""
                        i += 1
                    if ch == "t":
                        target = value
                    break
            i += 1
            continue
        rest.append(a)
        i += 1
    return rest, target, unknown


def _copy_like(prog: str, args: list) -> Writes:
    rest, target, unknown = _copy_args(prog, args)
    w = Writes(everywhere=unknown)
    if target:
        w.paths += _into(target, rest, folder=True)
        if prog == "mv":
            w.paths += rest
    elif prog == "mv":
        w.paths += rest[:-1] + _into(rest[-1], rest[:-1]) if rest else []
    elif rest:
        w.paths += _into(rest[-1], rest[:-1])
    return w


def _sed(args: list) -> Writes:
    in_place = any(a == "-i" or a.startswith("-i") or a.startswith("--in-place") for a in args)
    if not in_place:
        return Writes()
    has_script_opt = any(a in ("-e", "-f", "--expression", "--file") for a in args)
    rest, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("-e", "-f", "--expression", "--file"):
            i += 2
            continue
        if not a.startswith("-"):
            rest.append(a)
        i += 1
    return Writes(paths=rest if has_script_opt else rest[1:])


def _git_writes(argv: list) -> Writes:
    sub, args, gcwd = _git_sub(argv)
    w = _git_writes_in(sub, args)
    if gcwd is None:
        return w
    target = _clean(gcwd)  # `-C <folder>`: the paths are read from it (H5)
    return _based(w, None if (not target or _UNREADABLE.search(target)) else target)


def _git_writes_in(sub, args: list) -> Writes:
    if sub in _GIT_EVERYWHERE:
        if sub == "reset" and "--hard" not in args and "--merge" not in args and "--keep" not in args:
            return Writes()
        return Writes(everywhere=True)
    if sub == "checkout":
        if "--" in args:
            return Writes(paths=args[args.index("--") + 1:])
        return Writes(everywhere=bool(_non_options(args)) or any(a in ("-b", "-B", "--orphan") for a in args))
    if sub == "restore":
        return _restore_writes(args)
    if sub in ("rm", "mv"):
        rest = [a for a in args if a != "--"]
        return Writes(paths=_non_options(rest))
    return Writes()


_RESTORE_LONG = {"--source", "--patch", "--quiet", "--progress", "--no-progress", "--ours", "--theirs", "--merge",
                 "--conflict", "--ignore-unmerged", "--ignore-skip-worktree-bits", "--recurse-submodules",
                 "--no-recurse-submodules", "--overlay", "--no-overlay", "--pathspec-file-nul"}


def _restore_writes(args: list) -> Writes:
    """`git restore`: nothing in the working tree only when it is «staged» and not «worktree» (close-fix 13, A-M3).
    Only an exact `--staged` or a `-S` with no attached value is staged; any `--` prefix of `--worktree` is worktree;
    `-s` takes a value (`-sS` is the source `S`); an unknown option, or `--pathspec-from-file`, is a write whose paths
    are not read (remainder item 7, H12)."""
    staged = worktree = unknown = False
    paths, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            paths += args[i + 1:]
            break
        if a.startswith("--"):
            name, eq, _value = a.partition("=")
            if name == "--staged":
                staged = True
            elif len(name) > 2 and "--worktree".startswith(name):
                worktree = True
            elif name == "--source":
                i += 0 if eq else 1
            elif name not in _RESTORE_LONG:
                unknown = True
            i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            for k, ch in enumerate(a[1:], 1):
                if ch == "s":
                    i += 0 if a[k + 1:] else 1
                    break
                if ch == "S":
                    staged = True
                elif ch == "W":
                    worktree = True
                elif ch not in "pqm23":
                    unknown = True
            i += 1
            continue
        paths.append(a)
        i += 1
    if staged and not worktree and not unknown:
        return Writes()
    return Writes(paths=paths, everywhere=unknown)


def _ps_paths(args: list, positional: int) -> list:
    """The values of the path parameters, else the positional argument at that index."""
    named, pos, i = [], [], 0
    while i < len(args):
        a = args[i]
        low = a.lower()
        if low.startswith("-") and len(a) > 1:
            name, colon, value = low.partition(":")
            name = _ps_param(name)
            if name in _PS_SWITCHES:
                i += 1
                continue
            if not colon:
                value = args[i + 1] if i + 1 < len(args) else ""
                i += 1
            else:
                value = a.split(":", 1)[1]
            if name in _PS_PATH_PARAMS:
                named.append(value)
            i += 1
            continue
        pos.append(a)
        i += 1
    if named:
        return named
    return pos[positional:positional + 1]


def _ps_writes(prog: str, args: list) -> Writes:
    w = _ps_writes_read(prog, args)
    if _ps_unknown(args) or any(re.match(r"@[A-Za-z_]", a) for a in args):  # a splat hides its parameters (H10)
        w.everywhere = True
    return w


def _ps_writes_read(prog: str, args: list) -> Writes:
    prog = _PS_ALIAS.get(prog, prog)
    if prog in ("copy-item", "copy", "cp"):
        dest = [a for a in _ps_named(args, "-destination")] or _ps_positional(args)[1:2]
        return Writes(paths=dest)
    if prog in ("move-item", "move", "mv"):
        return Writes(paths=_ps_positional(args)[:2] + _ps_named(args, "-destination") + _ps_named(args, "-path"))
    if prog == "rename-item":
        return Writes(paths=(_ps_named(args, "-path") + _ps_named(args, "-literalpath")) or _ps_positional(args)[:1])
    return Writes(paths=_ps_paths(args, positional=0))


def _ps_named(args: list, name: str) -> list:
    out = []
    for i, a in enumerate(args):
        low = a.lower()
        if not low.startswith("-"):
            continue
        head, colon, _ = low.partition(":")
        if _ps_param(head) != name:
            continue
        if colon:
            out.append(a.split(":", 1)[1])
        elif i + 1 < len(args):
            out.append(args[i + 1])
    return out


def _ps_positional(args: list) -> list:
    pos, i = [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and len(a) > 1:
            i += 1 if (_ps_param(a.lower()) in _PS_SWITCHES or ":" in a) else 2
            continue
        pos.append(a)
        i += 1
    return pos


# ---- python code ----------------------------------------------------------------------------------------------------

_PY_VALUE_OPTS = {"-X", "-W", "--check-hash-based-pycs"}
_RISKY_MODULES = {"subprocess", "runpy", "importlib", "ctypes", "pty", "multiprocessing", "socket", "tempfile"}
_PATH_WRITE_ATTRS = {"write_text", "write_bytes", "unlink", "rename", "replace", "rmdir", "mkdir", "touch",
                     "symlink_to", "hardlink_to", "chmod", "link_to"}
_OS_FUNCS_ARG0 = {"remove", "unlink", "rmdir", "removedirs", "makedirs", "mkdir", "truncate", "chmod", "rmtree",
                  "utime"}
_OS_FUNCS_BOTH = {"rename", "replace", "renames", "move"}
_OS_FUNCS_ARG1 = {"copy", "copy2", "copyfile", "copytree", "symlink", "link", "copymode", "copystat"}
_OS_FUNCS_ANY = {"system", "popen", "startfile", "execv", "execve", "execl", "execlp", "execvp", "spawnl", "spawnv",
                 "fork", "kill", "posix_spawn", "write", "open"}
_DANGER_NAMES = {"exec", "eval", "compile", "__import__"}


def _python_writes(args: list, heredocs: list) -> Writes:
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-c":
            return python_code_writes(args[i + 1] if i + 1 < len(args) else "")
        if a.startswith("-c") and len(a) > 2:
            return python_code_writes(a[2:])
        if a == "-m":
            return Writes()  # a module run (pytest, ...): no write shape
        if a == "-":
            return python_code_writes(heredocs[0]) if heredocs else Writes(everywhere=True)
        if a in _PY_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return Writes()  # `python script.py`: a known program with no write shape
    if heredocs:
        return python_code_writes(heredocs[0])
    return Writes()


def _literal_path(node) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call):
        f = node.func
        name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
        if name in ("Path", "PurePath", "PosixPath", "WindowsPath") and node.args and not node.keywords:
            parts = [_literal_path(a) for a in node.args]
            return "/".join(parts) if all(parts) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left, right = _literal_path(node.left), _literal_path(node.right)
        return f"{left}/{right}" if left and right else None
    return None


def _mode_of(call: ast.Call, index: int):
    if len(call.args) > index:
        m = call.args[index]
        return m.value if isinstance(m, ast.Constant) and isinstance(m.value, str) else None
    for kw in call.keywords:
        if kw.arg == "mode":
            return kw.value.value if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str) else None
    return "r"


def python_code_writes(code: str) -> Writes:
    """Best effort over a Python text: the literal paths of write calls; everywhere for a write call whose path is
    not a literal, a risky module, `exec`/`eval`, a `sys.path` change, or code that does not parse."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return Writes(everywhere=True, unparsed=True)
    w = Writes()

    def path_or_all(node):
        p = _literal_path(node) if node is not None else None
        if p is None:
            w.everywhere = True
        elif p not in w.paths:
            w.paths.append(p)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(n.split(".")[0] in _RISKY_MODULES for n in names):
                w.everywhere = True
        elif isinstance(node, ast.Attribute) and node.attr == "path" and isinstance(node.value, ast.Name) \
                and node.value.id == "sys":
            w.everywhere = True  # sys.path: an import of other code
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                if f.id in _DANGER_NAMES:
                    w.everywhere = True
                elif f.id == "open":
                    mode = _mode_of(node, 1)
                    if mode is None:
                        w.everywhere = True
                    elif any(ch in mode for ch in "wax+"):
                        path_or_all(node.args[0] if node.args else None)
            elif isinstance(f, ast.Attribute):
                owner = f.value.id if isinstance(f.value, ast.Name) else None
                if owner in ("os", "shutil", "io", "codecs", "pathlib"):
                    if f.attr in _OS_FUNCS_ANY and not (owner in ("io", "codecs") and f.attr == "open"):
                        w.everywhere = True
                    elif f.attr == "open":
                        mode = _mode_of(node, 1)
                        if mode is None or any(ch in mode for ch in "wax+"):
                            path_or_all(node.args[0] if node.args else None)
                    elif f.attr in _OS_FUNCS_ARG0:
                        path_or_all(node.args[0] if node.args else None)
                    elif f.attr in _OS_FUNCS_BOTH:
                        for k in (0, 1):
                            path_or_all(node.args[k] if len(node.args) > k else None)
                    elif f.attr in _OS_FUNCS_ARG1:
                        path_or_all(node.args[1] if len(node.args) > 1 else None)
                elif f.attr in _PATH_WRITE_ATTRS:
                    if isinstance(f.value, ast.Constant):
                        continue  # a string method (`"a".replace(...)`)
                    base = _literal_path(f.value)
                    if base is not None:
                        path_or_all(f.value)
                        if f.attr in ("rename", "replace") and node.args:
                            path_or_all(node.args[0])
                    elif f.attr != "replace":
                        w.everywhere = True
                elif f.attr == "open" and _literal_path(f.value) is not None:
                    mode = _mode_of(node, 0)
                    if mode is None or any(ch in mode for ch in "wax+"):
                        path_or_all(f.value)
    return w


# ---- mkway_calls ----------------------------------------------------------------------------------------------------

_ENGINE_NAMES = ("mkway.py",)


def _script_index(argv: list) -> Optional[int]:
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-c", "-m") or (a.startswith("-c") and len(a) > 2) or re.match(r"-[A-VYZa-z]*[cm]", a):
            return None  # code or a module, also in a cluster (`-Ic`, `-Bm`; remainder item 3)
        if a in _PY_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return i
    return None


def _base(word: str) -> str:
    return word.replace("\\", "/").rsplit("/", 1)[-1].lower()


def mkway_calls(cmd: str, shell: str = "bash") -> list:
    """For each call of the engine's command line (`mkway.py`, run by a Python or `py` interpreter, or directly),
    the list of its arguments. A command that cannot be read gives []; the lock gate then treats it as writing
    everywhere."""
    try:
        simples = parse(cmd, shell)
    except ParseError:
        return []
    out = []
    for s in simples:
        argv = _argv(s.words)
        prog = _prog(argv)
        if _INTERPRETERS.match(prog or ""):
            k = _script_index(argv)
            if k is not None and _base(argv[k]) in _ENGINE_NAMES:
                out.append(argv[k + 1:])
        elif prog in _ENGINE_NAMES or prog == "mkway":
            out.append(argv[1:])
        elif prog in _SHELLS:
            for i, a in enumerate(argv[1:], 1):
                if a == "-c" and i + 1 < len(argv):
                    out += mkway_calls(argv[i + 1], "bash")
                    break
        elif prog in _PWSH:
            for i, a in enumerate(argv[1:], 1):
                if a.lower() in ("-command", "-c") and i + 1 < len(argv):
                    out += mkway_calls(" ".join(argv[i + 1:]), "powershell")
                    break
        for sub in s.subs:
            out += mkway_calls(sub, shell)
    return out


# --- the exact form of an engine call (card MW-003 batch 3, H4; R54, R55) ---------------------------------------------

_ENGINE_TEXT = re.compile(r"(?<![\w-])mkway(?:\.py)?['\"]?\s+\S*?(?:card|lock|gate|install|upgrade|check|hook|search"
                          r"|decision|give|sessions)\b", re.I)
_PLAIN_WORD = r"""(?:[A-Za-z0-9_./:=@%+,-]+|"[^"$`{}\[\]()*?\\]*"|'[^'$`{}\[\]()*?\\]*')"""
# the `cd` folder of a plain call: a plain word, or a quoted one that may hold a backslash (`"C:\x\y"`: inside double
# quotes a backslash before `\`, `"`, `$` or a backtick is an escape and is not read; inside single quotes it is text)
_CD_WORD = (r"""(?:[A-Za-z0-9_./:=@%+,-]+|"(?:[^"$`{}\[\]()*?\\]|\\(?![\\"$`]))*"|'[^'$`{}\[\]()*?]*')""")
_PLAIN_CALL = re.compile(rf"^\s*(?:cd[ \t]+(?P<cd>{_CD_WORD})[ \t]*(?:&&|;)[ \t]*)?"
                         rf"(?P<call>{_PLAIN_WORD}(?:[ \t]+{_PLAIN_WORD})*)\s*$")
_PY_VERSION = re.compile(r"^-[0-9](?:\.[0-9]+)?$")


_QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", re.S)


def unquoted_text(cmd: str) -> str:
    """The command text with every heredoc body and every quoted string removed (remainder item 2, R95 (3a)): what
    the shell itself reads as words. Shell and interpreter heredocs come back as carrier texts (`carriers`)."""
    text, _bodies = _split_heredocs(cmd or "")
    return _QUOTED.sub("''", text)


def holds_engine_call(cmd: str, shell: str = "bash", root=None, start="") -> bool:
    """True when the command holds a call of the engine's command line. A command that parses: the `mkway_calls`
    detector; the free-text scan (the engine's name followed by one of its commands) over the text with quoted strings
    and heredoc bodies removed, so no form the parser does not enter (`stdbuf`, `winpty`, a function body) hides a
    call (remainder item 2, R95 (3a): never less caught than the whole-text scan of the earlier round); and the same
    scan over every carrier text `carriers` reads (a shell's `-c`, heredoc or stdin, `trap`, `eval`, `xargs`, `cmd`,
    `pwsh`, an interpreter's code option; an interpreter fed by stdin only with a process-start call). A command
    that does not parse: the scan over the whole text. Quoted messages and notes are not read as calls (close-fix 4,
    A-M4)."""
    try:
        parse(cmd, shell)
    except ParseError:
        return bool(_ENGINE_TEXT.search(cmd or ""))
    if mkway_calls(cmd, shell) or _ENGINE_TEXT.search(unquoted_text(cmd)):
        return True
    for s, whole in _all_simples(cmd, shell, root=root, start=start):
        if s is None:
            if _ENGINE_TEXT.search(whole):
                return True
            continue
        if any(not text.startswith("\0") and _ENGINE_TEXT.search(text) for _prog_name, text in carriers(s, whole)):
            return True
        if _disguised_script(s):
            return True
    return False


_DISGUISE = re.compile(r"[$`*?\[{]")


def _disguised_script(s: Simple) -> bool:
    """True when an interpreter's script word (after same-command expansion) matches `mkway.py` as a glob, or still
    holds `$`, a backtick, `*`, `?`, `[` or `{` (remainder item 3, close-fix item 17, A-H1): `mkwa?.py`,
    `S=…/mkway.py; python $S`, `eng$(echo ine)`. The exact form then refuses it."""
    argv = _argv(s.words)
    if not _INTERPRETERS.match(_prog(argv) or ""):
        return False
    k = _script_index(argv)
    if k is None:
        return False
    word = argv[k]
    return bool(_DISGUISE.search(word)) or fnmatch.fnmatchcase("mkway.py", _base(word))


def engine_call_problem(cmd: str, bundle_root: str, norm) -> Optional[str]:
    """None when the command is exactly one plain engine call, optionally after `cd <literal folder inside the root>`
    joined by `&&` or `;` (the folder in any spelling `norm` reads: `C:/…`, `C:\\…`, `/c/…`; false blocks, part 1,
    E96; `bundle_root` is no longer the limit); else what is wrong. Plain: words of letters, digits and `_./:=@%+,-`,
    or one quote pair around a whole word with no `$`, backtick, brace, bracket, parenthesis, `*`, `?` or backslash;
    no other segment, pipe, redirect, `VAR=` prefix or wrapper; no `--profile` or `--root` (R54)."""
    m = _PLAIN_CALL.match(cmd or "")
    if not m:
        return "it is not one plain engine call (a chain, pipe, redirect, variable, quote form or wrapper)"
    if m.group("cd") is not None:  # false blocks, part 1 (E96): a literal folder inside the root, any spelling
        if norm(m.group("cd").strip("'\"")) is None:
            return "its `cd` leaves the root"
    words = [w.strip("'\"") for w in re.findall(_PLAIN_WORD, m.group("call"))]
    if not words or not _INTERPRETERS.match(_base(words[0])):
        return "it does not start with the Python interpreter"
    k = 1
    if _base(words[0]).lower().startswith("py") and not _base(words[0]).lower().startswith("python") \
            and len(words) > 1 and _PY_VERSION.match(words[1]):
        k = 2
    if len(words) <= k or _base(words[k]) not in _ENGINE_NAMES:
        return "its script is not the engine's mkway.py"
    for w in words[k + 1:]:
        name = w.split("=", 1)[0]
        if len(name) > 2 and any(full.startswith(name) for full in ("--profile", "--root")):  # close-fix 8, A-M1
            return f"`{name}` is the owner's option: the root and the profile are found, never named"
    return None
