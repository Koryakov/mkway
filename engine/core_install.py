"""The pure core of install and check (card MW-067): what install copies, writes, refuses and prints is decided here,
from facts the shell (`install.py`) read; this module reads nothing: no file, no process, no environment, no clock.

The shell reads the disk and git, calls these functions, and writes what they return. A fact the shell has not read yet
is `None`, and `decide_install` skips the check that needs it, so the shell can ask after each cheap read and keep the
order of the refusals (profile, root, python, source, copy). The verdict is data: `allow`, or `refuse(reason, text)`;
a text transform (settings file, ignore file) returns the new text in `out`.

`profiles` and `schema_check` are the engine modules imported: the functions used here (`gate_on`, `budget_seconds`,
`bundle_root`, `_format_error`) work on values and read no file. No task name and no natural-language word is in this
file.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Optional

import profiles
import schema_check

SET_FILES = ("mkway.py", "VERSION", "cards/_TEMPLATE/CARD.md",  # MW-016: the version travels with the copy
             "cards/_TEMPLATE/ORDER.md")  # MW-017: the order file of a lead's card
SET_DIRS = ("engine/", "tools/", "tests/", "fixtures/synthetic/")
SKIP_PARTS = {".git", "__pycache__", ".pytest_tmp", ".pytest_cache"}
BUNDLE_FOLDERS = ("cards", "ledger", "locks", "state")  # created by install
IGNORED_FOLDERS = ("locks", "state")  # R18: cards/ and ledger/ are tracked; MW-027: so is the engine copy
RUNTIME_IGNORES = ("__pycache__/", "*.pyc", ".pytest_tmp/", ".pytest_cache/")  # written when the copy runs or is checked
IGNORE_HEAD = ("# mkway install: locks, state and what the copy writes at run time are not tracked; the engine copy, "
               "profile.json, mkway.lock, cards and ledger are")
SETTINGS_FILE = ".claude/settings.json"  # MW-027: the committed hook entries
EVENT_ORDER = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop",
               "Stop")  # MW-004: the two agent events, no matcher (every agent), so not in MATCHER_EVENTS
MATCHER_EVENTS = ("PreToolUse", "PostToolUse")
FLOOR_SECONDS = 10   # the least timeout of an entry
MARGIN_SECONDS = 15  # added to every entry's timeout (R13c)
WAKE_MARGIN_SECONDS = 60  # MW-078: the inbox waiter's hook timeout is its deadline plus this
PY_FLAGS = "-I -X utf8"  # R111 (a): no per-user Python folder, no PYTHONPATH; UTF-8 text
STALE_ENGINE_IGNORES = ("engine/", "/engine/", "engine")  # MW-035, MW-041: the spellings an earlier install left
ATTRIBUTES_HEAD = ("# mkway install: the register is written with \\n line ends, and the engine copy keeps its bytes; "
                   "git must not convert either")
REGISTER_ATTRIBUTE = "cards/REGISTER.md -text"
ENGINE_ATTRIBUTE = "engine/** -text"  # MW-027: the copy's hash must survive a checkout with autocrlf
OWN_NAMES = (".gitignore", ".gitattributes", "mkway.lock", "engine")  # MW-036: what install writes in the bundle
FAILED_NAMES_MAX = 10  # MW-025: the check line names at most this many failing tests

UNQUOTED_EXE = re.compile(r"[A-Za-z0-9_./:-]+")  # no space, no backslash, no shell character
QUOTED_EXE = re.compile(r'"([^"$`%!\n\r]*[^"$`%!\n\r\\])"')  # inside double quotes: no `"`, `$`, backtick, `%`, `!`
VERSION_FLAG = re.compile(r"-[0-9]+(\.[0-9]+)?")
LAUNCHER_NAMES = ("py", "py.exe")  # the Windows launcher: the only program that takes the version flag (C34)
MIN_PYTHON = (3, 9)

ALLOW, REFUSE = "allow", "refuse"
NOT_FOUND = ["(profile): not found"]


@dataclass(frozen=True)
class Verdict:
    """allow | refuse(reason, text). `out` carries the text a transform produced (the new settings or ignore file)."""
    kind: str = ALLOW
    reason: Optional[str] = None
    text: str = ""
    out: Optional[str] = None

    def __post_init__(self):
        if self.kind not in (ALLOW, REFUSE):
            raise ValueError(f"unknown verdict kind: {self.kind!r}")
        if self.kind == REFUSE and not (self.reason and self.text):
            raise ValueError("a refuse needs a reason and a text")


def allow(out: Optional[str] = None) -> Verdict:
    return Verdict(ALLOW, out=out)


def refuse(reason: str, text: str) -> Verdict:
    return Verdict(REFUSE, reason, text)


# ---- the file set and the hash ----------------------------------------------------------------------------------

def skipped(rel: str) -> bool:
    return rel.endswith(".pyc") or any(part in SKIP_PARTS for part in rel.split("/"))


def in_set(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return not skipped(rel) and (rel in SET_FILES or rel.startswith(SET_DIRS))


def hash_entries(entries) -> str:
    """The one hash routine: sha256 over (relative path, length, bytes) of `entries`, an iterable of (rel, bytes) in
    sorted path order."""
    digest = hashlib.sha256()
    for rel, data in entries:
        digest.update(rel.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0")
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def files_hash(files: dict) -> str:
    """MW-051: the hash of a copy written from `files` (relative posix path -> bytes), computed from those bytes."""
    return hash_entries(sorted((rel, data) for rel, data in files.items() if not skipped(rel)))


def lock_record(files: dict, version: str, sha, date: str) -> dict:
    """The lock install writes: version (the tag, or `unversioned`), `semver` (the copy's `VERSION` text, MW-016),
    source sha, date and the hash of `files`; no path."""
    semver = files.get("VERSION", b"").decode("utf-8", "replace").strip() or None
    return {"version": version, "semver": semver, "source_sha": sha, "date": date, "hash": files_hash(files)}


# ---- hook entries -----------------------------------------------------------------------------------------------

def owned_marker(bundle_root: str) -> str:
    return f'"${{CLAUDE_PROJECT_DIR}}/{bundle_root}/engine/mkway.py" hook'


def loadable_on(profile, e) -> bool:
    if e.get("waiter"):  # MW-078: the inbox waiter is no gate: no function, no reason id; `wake.mode` switches it
        return e.get("event") in EVENT_ORDER and profiles.wake_settings(profile)["mode"] == "on"
    return bool(e.get("function")) and bool(e.get("reason_ids")) and e.get("event") in EVENT_ORDER and \
        profiles.gate_on(profile, e.get("gate", e.get("name", "")), e.get("default_on", False))


AGENT_FILE = ".claude/agents/fresh-reader.md"  # MW-116: the reader agent the install writes (K1: an install file)
AGENT_TEMPLATE = "engine/templates/fresh-reader.md"  # inside the engine copy


def render_reader_agent(template: str, python: str, bundle: str) -> str:
    """MW-116: the reader agent file from the shipped template: the interpreter, the flags of the settings hooks and the
    bundle folder put in place of `{{PYTHON}}`, `{{FLAGS}}` and `{{BUNDLE}}`."""
    return template.replace("{{PYTHON}}", python).replace("{{FLAGS}}", PY_FLAGS).replace("{{BUNDLE}}", bundle)


def reader_agent_action(existing, rendered: str) -> str:
    """MW-116: `write` when the file is missing, else `keep`: a file that exists is the owner's, whether it equals the
    rendering or not (a reinstall never overwrites an edit)."""
    return "write" if existing is None else "keep"


def generate_entries(profile, manifest, groups_table, *, profile_rel=None, python=None) -> list:
    """One entry per event and group with a gate on, plus the start entry (C23): event, group, matcher (the union
    of the group's gate matchers; None = every tool), command, timeout and on_failure (the group table's).
    Timeout (C23, R13c): the sum over the group's gates of (the profile's budget_seconds, else the manifest timeout)
    + 15 s, at least 10 s, so the dispatcher's own stop comes before the platform's."""
    python = python or ((profile.get("python") or {}).get("command") if isinstance(profile, dict) else None) \
        or "python"
    bundle = profiles.bundle_root(profile)
    groups = {("SessionStart", "start"): []}
    waiters = []
    for e in manifest:
        if e.get("frontmatter"):  # MW-116: a hook of an agent file's own frontmatter; it is never a settings entry
            continue
        if loadable_on(profile, e) and e.get("waiter"):
            waiters.append(e)
        elif loadable_on(profile, e):
            groups.setdefault((e["event"], e.get("group")), []).append(e)
    keys = sorted(groups, key=lambda k: EVENT_ORDER.index(k[0]))
    out = []
    for event, group in keys:
        gates = groups[(event, group)]
        matcher = None
        if event in MATCHER_EVENTS and gates and all(g.get("matcher") not in (None, "", "*") for g in gates):
            parts = []
            for g in gates:
                parts += [p for p in g["matcher"].split("|") if p not in parts]
            matcher = "|".join(parts)
        seconds = 0
        for g in gates:
            budget = profiles.budget_seconds(profile, g.get("gate", g.get("name", "")))
            if budget is not None:
                seconds += budget
            elif isinstance(g.get("timeout"), (int, float)) and not isinstance(g.get("timeout"), bool):
                seconds += g["timeout"]
        timeout = max(FLOOR_SECONDS, math.ceil(seconds + MARGIN_SECONDS))
        command = f'{python} {PY_FLAGS} "${{CLAUDE_PROJECT_DIR}}/{bundle}/engine/mkway.py" hook {event} --group {group}'
        if profile_rel:
            command += f' --profile "${{CLAUDE_PROJECT_DIR}}/{profile_rel}"'
        on_failure = (groups_table.get(group) or {}).get("onFailure")
        out.append({"event": event, "group": group, "matcher": matcher, "command": command, "timeout": timeout,
                    "on_failure": on_failure})
    for e in waiters:  # MW-078: its own Stop handler, never inside dispatch: asyncRewake, timeout = deadline + 60
        command = f'{python} {PY_FLAGS} "${{CLAUDE_PROJECT_DIR}}/{bundle}/engine/mkway.py" hook-wait'
        if profile_rel:
            command += f' --profile "${{CLAUDE_PROJECT_DIR}}/{profile_rel}"'
        seconds = profiles.wake_settings(profile)["deadline_seconds"] + WAKE_MARGIN_SECONDS
        out.append({"event": e["event"], "group": e.get("group"), "matcher": None, "command": command,
                    "timeout": seconds, "on_failure": None, "async_rewake": True})
    return out


def _value_span(text: str, key: str):
    """(start, end) of a top-level key's value in a JSON object text, or None."""
    decoder = json.JSONDecoder()
    ws = re.compile(r"\s*")
    i = ws.match(text, 0).end()
    if text[i:i + 1] != "{":
        return None
    i = ws.match(text, i + 1).end()
    while i < len(text) and text[i] != "}":
        name, i = json.decoder.scanstring(text, i + 1)
        i = ws.match(text, i).end() + 1  # the colon
        i = ws.match(text, i).end()
        _value, end = decoder.raw_decode(text, i)
        if name == key:
            return i, end
        i = ws.match(text, end).end()
        if text[i:i + 1] == ",":
            i = ws.match(text, i + 1).end()
    return None


def is_owned(handler, marker) -> bool:
    return isinstance(handler, dict) and isinstance(handler.get("command"), str) and marker in handler["command"]


def settings_text(text: Optional[str], entries: list, bundle_root: str, name: str = "settings.json") -> Verdict:
    """The settings file install writes (C24), as text: `text` is the file now (None when there is none). Replaces the
    owned entries; keeps every other top-level key byte for byte and every handler mkway does not own. Only documented
    fields: matcher, hooks, type, command, timeout, onFailure (R13c). Refuses (`settings-not-json`,
    `settings-hooks-not-object`) with the file untouched; else `out` is the new text."""
    marker = owned_marker(bundle_root)
    try:
        data = json.loads(text) if text is not None else {}
    except json.JSONDecodeError as exc:
        return refuse("settings-not-json", f"{name} is not valid JSON (line {exc.lineno}); it was not changed")
    hooks = data.get("hooks", {}) if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return refuse("settings-hooks-not-object", f"{name}: `hooks` is not an object; it was not changed")
    new: dict = {}
    for event, groups in hooks.items():
        kept = []
        for group in groups if isinstance(groups, list) else []:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list):
                kept.append(group)
                continue
            rest = [h for h in handlers if not is_owned(h, marker)]
            if rest:
                kept.append(dict(group, hooks=rest) if len(rest) != len(handlers) else group)
        if kept:
            new[event] = kept
    for e in entries:
        group = {"matcher": e["matcher"]} if e["matcher"] else {}
        handler = {"type": "command", "command": e["command"], "timeout": e["timeout"]}
        if e.get("on_failure"):
            handler["onFailure"] = e["on_failure"]  # R13c: a documented handler key
        if e.get("async_rewake"):
            handler["asyncRewake"] = True  # MW-078: runs in the background; exit 2 wakes an idle session
        group["hooks"] = [handler]
        new.setdefault(e["event"], []).append(group)
    value = json.dumps(new, indent=2).replace("\n", "\n  ")
    if text is None:
        return allow('{\n  "hooks": ' + value + "\n}\n")
    span = _value_span(text, "hooks")
    if span:
        return allow(text[:span[0]] + value + text[span[1]:])
    close = text.rstrip().rindex("}")
    head = text[:close].rstrip()
    sep = "" if head.endswith("{") else ","
    return allow(head + sep + '\n  "hooks": ' + value + "\n" + text[close:])


def owned_entries(text: Optional[str], bundle_root: str) -> list:
    """The owned entries in a settings file's text, as whole entries: event, matcher, command, timeout, onFailure."""
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return []
    marker = owned_marker(bundle_root)
    out = []
    hooks = data.get("hooks") if isinstance(data, dict) else None
    for event, groups in (hooks or {}).items():
        for group in groups if isinstance(groups, list) else []:
            for h in (group.get("hooks") or []) if isinstance(group, dict) else []:
                if is_owned(h, marker):
                    entry = {"event": event, "matcher": group.get("matcher"), "command": h["command"],
                             "timeout": h.get("timeout"), "on_failure": h.get("onFailure")}
                    if "asyncRewake" in h:
                        entry["async_rewake"] = h["asyncRewake"]  # MW-078: only a handler that carries the field
                    out.append(entry)
    return out


# ---- the profile and the refusals -------------------------------------------------------------------------------

DEFAULT_CHECKER = "fresh-reader"  # MW-068 R179 condition 2, MW-071 R180: the read-only blind reader (Sonnet, medium, Read, Grep)


def starter_profile(vcs: str) -> dict:
    return {
        "vcs": vcs,
        "bundle": {"root": profiles.DEFAULT_BUNDLE_ROOT},
        "ids": {"card_prefix": "CARD"},
        "gates": {},
        "state": {"dir": profiles.DEFAULT_STATE_DIR},
        "python": {"command": "python"},
        "outbox": {"checkers": [DEFAULT_CHECKER]},  # R179: a new root enforces the blind verdict (default on, R173 item 3)
    }


@dataclass(frozen=True)
class ProfilePlan:
    """`kind`: `starter` (no profile yet: write `profile`), `shared` (write `profile`, which has `state.shared_dir`),
    `invalid` (the profile is kept as it is), `keep` (the profile stands). `profile` is what install would write, or
    the loaded profile."""
    kind: str
    profile: Optional[dict]


def plan_profile(loaded, errors, shared, vcs_arg, detected_vcs) -> ProfilePlan:
    """Which profile install works with. `loaded`/`errors` as `profiles.load` answered; `detected_vcs` the answer of the
    folder's own check (`git` or `none`), used only when the starter has no `--vcs`."""
    if loaded is None and list(errors) == NOT_FOUND:
        profile = starter_profile(vcs_arg or detected_vcs)
        if shared is not None:
            profile["state"]["shared_dir"] = shared  # MW-026: the owner's opt-in
        return ProfilePlan("starter", profile)
    if errors:
        return ProfilePlan("invalid", loaded)
    if shared is not None and (loaded.get("state") or {}).get("shared_dir") != shared:
        profile = json.loads(json.dumps(loaded))
        profile.setdefault("state", {})["shared_dir"] = shared
        return ProfilePlan("shared", profile)
    return ProfilePlan("keep", loaded)


def choose_vcs(profile, vcs_arg, detected_vcs) -> str:
    """The profile's own `vcs` when it says `git` or `none`, else the argument, else what the folder is."""
    return profile.get("vcs") if profile.get("vcs") in ("git", "none") else (vcs_arg or detected_vcs)


@dataclass(frozen=True)
class InstallFacts:
    """What `decide_install` reads. A fact left `None` has not been read yet and its check is skipped."""
    shared: Optional[str] = None
    profile_inside_root: Optional[bool] = None
    kind: str = "keep"                 # the ProfilePlan kind
    load_errors: tuple = ()            # the errors of the loaded profile (not `not found`)
    candidate_errors: Optional[tuple] = None  # the errors of the profile install would write (starter, shared)
    commit: bool = False
    vcs_now: Optional[str] = None
    bundle: str = "mkway"
    bundle_inside_root: Optional[bool] = None  # bundle, state and the copy lie inside the root, no link out
    python_ok: Optional[bool] = None
    source_files: Optional[int] = None
    copy_exists: Optional[bool] = None
    lock_exists: Optional[bool] = None


def _five(errors) -> str:
    return "; ".join(list(errors)[:5])


def decide_install(f: InstallFacts) -> Verdict:
    """The refusals of `install`, in the order the shell can read their facts. Everything else is allowed."""
    if f.shared is not None and schema_check._format_error("absolute-path", f.shared) is not None:
        return refuse("shared-not-absolute",
                      "--shared must be an absolute path (for example C:/work/shared-state); nothing was written")
    if f.profile_inside_root is False:
        return refuse("profile-outside-root", "the profile path leads outside the root; nothing was written")
    if f.kind == "starter" and f.candidate_errors:
        return refuse("starter-invalid", "the starter profile would be invalid: " + _five(f.candidate_errors)
                      + "; nothing was written")
    if f.kind == "invalid" and f.shared is not None:
        return refuse("profile-invalid-shared", "the profile is invalid, so --shared cannot be written into it: "
                      + _five(f.load_errors) + "; nothing was written")
    if f.kind == "shared" and f.candidate_errors:
        return refuse("shared-profile-invalid", "the profile with --shared would be invalid: "
                      + _five(f.candidate_errors) + "; nothing was written")
    if f.commit and f.vcs_now is not None and f.vcs_now != "git":
        return refuse("commit-needs-git", "--commit needs vcs git (the profile says none); nothing was written")
    if f.bundle_inside_root is False:
        return refuse("bundle-outside-root", f"{f.bundle} leads outside the root (a link or a junction); nothing was "
                                             "written")
    if f.python_ok is False:
        return refuse("python-not-interpreter",
                      "--python must name an existing Python 3.9 or later: a name found on PATH or a path (quoted if "
                      "it holds a space), no shell characters, and a version flag like -3 only after the py "
                      "launcher; nothing was written")
    if f.source_files == 0:
        return refuse("source-empty", "the source holds none of the engine's files")
    if f.copy_exists and f.lock_exists is False:
        return refuse("copy-without-lock", f"{f.bundle}/engine exists and has no mkway.lock beside it; it was not "
                                           "changed")
    return allow()


def profile_report(plan: ProfilePlan, errors, shared, profile_rel: str) -> Optional[str]:
    """The report line of the profile step: the profile written, or the invalid one kept; None when it stands."""
    if plan.kind == "starter":
        return f"profile: starter written ({profile_rel})"
    if plan.kind == "shared":
        return f"profile: state.shared_dir set to {shared} ({profile_rel})"
    if plan.kind == "invalid":
        return "profile: invalid, kept as it is: " + _five(errors)
    return None


# ---- the interpreter --------------------------------------------------------------------------------------------

def interpreter_syntax(text):
    """(program, version flag or None) when `text` is one program and at most one version flag, with no shell
    character and the flag only after the `py` launcher (C34); else None. The program still has to exist and run."""
    if not isinstance(text, str):
        return None
    m = re.fullmatch(r'("[^"]*"|\S+)(?: (\S+))?', text)
    if not m:
        return None
    exe, flag = m.group(1), m.group(2)
    q = QUOTED_EXE.fullmatch(exe)
    if q:
        path = q.group(1)
    elif UNQUOTED_EXE.fullmatch(exe):
        path = exe
    else:
        return None
    if flag is not None and (not VERSION_FLAG.fullmatch(flag)
                             or re.split(r"[\\/]", path)[-1].lower() not in LAUNCHER_NAMES):
        return None
    return path, flag


def version_answer_ok(returncode: int, out: str) -> bool:
    """True when the probe exited 0 and printed a version tuple of Python 3.9 or later."""
    version = re.fullmatch(r"\((\d+), (\d+)\)", (out or "").strip())
    return returncode == 0 and version is not None and (int(version[1]), int(version[2])) >= MIN_PYTHON


# ---- the files install writes ------------------------------------------------------------------------------------

def eol_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def ensure_lines(text: str, head: str, lines) -> str:
    """The file's text with `lines` added when missing (and `head` above the added ones); the line ending of the text
    stays. Unchanged text when nothing is missing."""
    eol = eol_of(text)
    have = set(text.splitlines())
    missing = [line for line in lines if line not in have]
    if not missing:
        return text
    if text and not text.endswith("\n"):
        text += eol
    if head not in have:
        missing.insert(0, head)
    return text + eol.join(missing) + eol


def ignore_plan(text: str, bundle: str):
    """(new text, report lines) of the bundle `.gitignore`: the run-time lines added (MW-027); an earlier install's
    `cards/` and `ledger/` lines named, never removed (C36); an earlier install's `engine/` line (any spelling, any line
    end) removed, the others kept in the file's own line ending style (MW-035, MW-041)."""
    text = ensure_lines(text, IGNORE_HEAD, [f"{name}/" for name in IGNORED_FOLDERS] + list(RUNTIME_IGNORES))
    have = text.splitlines()
    report = []
    old = [f"{name}/" for name in ("cards", "ledger") if f"{name}/" in have]
    if old:
        report.append(f"ignore: {bundle}/.gitignore still ignores {', '.join(old)} from an earlier install; "
                      "remove those lines: cards and ledger are tracked (R18)")
    if any(line.strip(" \r") in STALE_ENGINE_IGNORES for line in have):
        kept = [line for line in have if line.strip(" \r") not in STALE_ENGINE_IGNORES]
        text = eol_of(text).join(kept) + eol_of(text)
        report.append("ignore: removed engine/ (from an earlier install)")
    return text, report


def attributes_text(text: str) -> str:
    """R19c, MW-027: the bundle `.gitattributes` with the register's and the copy's `-text` lines."""
    return ensure_lines(text, ATTRIBUTES_HEAD, [REGISTER_ATTRIBUTE, ENGINE_ATTRIBUTE])


# ---- the commit step --------------------------------------------------------------------------------------------

def commit_message(prefix, version: str) -> str:
    """MW-035: `<commit.message_prefix> mkway <version>: install`, no prefix when unset."""
    return (f"{prefix} " if prefix else "") + f"mkway {version}: install"


def install_paths(bundle: str, present, profile_rel=None, extra=()) -> list:
    """MW-036: the paths install itself writes, relative to the root: the committed settings file, then `.gitignore`,
    `.gitattributes`, `mkway.lock` and `engine` of the bundle when present, then `profile_rel` (the profile) only when
    this run created it. Never the bundle folder: sessions write cards, asks and ledger rows there."""
    found = [SETTINGS_FILE]
    for name in OWN_NAMES:
        if name in present:
            found.append(f"{bundle}/{name}")
    if profile_rel:
        found.append(profile_rel)
    return found + list(extra)  # MW-116: the reader agent file


def commit_line(prefix, version: str, paths: list, root_posix: str) -> str:
    """MW-027, MW-035, MW-036, MW-041: the ONE line the owner pastes (PowerShell and bash) from any folder: `git -C
    "<root>"` in both commands, the root quoted and written with `/`; add install's own paths, then commit only those."""
    text = " ".join(paths)
    git_root = f'git -C "{root_posix}"'
    return f'{git_root} add {text}; {git_root} commit -m "{commit_message(prefix, version)}" -- {text}'


# ---- check ------------------------------------------------------------------------------------------------------

def failed_names(output: str) -> str:
    """MW-025: `; failed: <node>, ...` for the `FAILED`/`ERROR` rows of pytest's short summary: up to ten names, then
    `and N more`; empty when the output has none (a crash before collection)."""
    names = []
    for m in re.finditer(r"^(?:FAILED|ERROR) (\S+)", output or "", re.M):
        if m.group(1) not in names:
            names.append(m.group(1))
    if not names:
        return ""
    text = "; failed: " + ", ".join(names[:FAILED_NAMES_MAX])
    if len(names) > FAILED_NAMES_MAX:
        text += f" and {len(names) - FAILED_NAMES_MAX} more"
    return text


def hash_line(lock, actual: Optional[str]):
    """(line, ok) of the copy-hash step: no lock, the hash differs, or it matches."""
    if lock is None:
        return "copy hash: no lock (fix: mkway install)", False
    if lock.get("hash") == actual:
        return "copy hash: matches the lock", True
    return "copy hash: differs from the lock (fix: mkway install)", False


def tests_line(returncode: int, stdout: str):
    """(line, ok) of the copy's test run, from pytest's exit code and output."""
    summary = ((stdout or "").strip().splitlines() or ["no output"])[-1]
    if returncode == 0:
        passed = re.search(r"(\d+) passed", summary)
        return f"tests: {passed.group(1) if passed else 0} passed", True
    return f"tests: not green ({summary})" + failed_names(stdout), False


def version_tag_line(version_text: Optional[str], in_chat: bool, tags: Optional[list]):
    """MW-016: the `mkway check` line that compares the root's `VERSION` text with the tags at HEAD (`v<version>`).
    A warning, never a failure. None when the root has no `VERSION` file (`version_text` None); `tags` is None when git
    did not answer."""
    if version_text is None:
        return None
    if in_chat:
        return "version tag: not compared inside a Claude chat (run `mkway check` in your own terminal)"
    want = "v" + version_text.strip()
    if tags is None:
        return "version tag: not compared (git did not answer)"
    if want in tags:
        return f"version tag: {want} at HEAD matches VERSION"
    if tags:
        return (f"version tag: warning: HEAD is tagged {', '.join(sorted(tags))}, which differs from VERSION "
                f"({want}); the owner tags the release")
    return f"version tag: warning: the tag {want} is missing at HEAD; the owner tags the release (check never writes one)"
