"""The pure core of `mkway upgrade` and `mkway green record` (card MW-104; rulings R257 to R257h): what is accepted, refused and
said is decided here, from text and facts the shell (`upgrade.py`) read; this module reads nothing: no file, no process, no
environment, no clock. It imports only what `core_install.py` imports. No task name and no natural-language word is in it.

Homes (the order's H1 to H4): the config folder `<upgrade dir>` (`upgrade_folder`), the owner's grant `policy.json`
(`parse_grant`), the release config `release.json` read at the engine HEAD (`parse_release`) and the green record
`green.jsonl` (`parse_green`, `find_row`, `check_green_record`). The checks of the mkup 1.0.0 spec section 4 follow its order;
every refusal keeps the spec's literal text with the order's rewrites (`TEXTS`). Windows differs from other systems only in
the folder separator and in comparing paths without regard to capitals, so every path function takes `windows`.

A function that can refuse returns `(value, None)` or `(None, text)`; a text ends «Nothing was changed.» where the spec says
so (the shell adds it to the refusals that the spec ends that way).
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Optional

TOOL_ID = "tool:mkway-upgrade"
SOURCE_TEXT = "mkway upgrade"
TOPIC = "engine update"
BRANCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
SHA_RE = re.compile(r"[0-9a-f]{40}")
TAG_RE = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
SEMVER_RE = re.compile(r"\s*(\d+)\.(\d+)\.(\d+)")
INSTALL_LINE = re.compile(r'git -C "[^"]*" add (.+?); git -C "[^"]*" commit -m "(.*)" -- ')
GRANT_KEYS = ("target", "root", "roots", "shared")
MOVED_KEYS = (("engine", "the engine repository mkway upgrade runs from"), ("branch", "release.json (branch)"),
              ("python", "the running interpreter"), ("mkcl-log", "the green record"),
              ("test-command", "release.json (full_command)"))
RELEASE_KEYS = ("branch", "full_command", "narrow_command", "narrow_paths")
COMMAND_HINT = 'must be a command line, or a list like ["python", "-m", "pytest"]'
WILDCARD_TEXT = 'the only wildcard allowed is a trailing "/**" after a folder name'
DOTS_TEXT = 'it must not contain "..", "." or empty parts'
ROOTS_LIST = 'roots must be a list of folder names (relative, for example ["task\\a", "task\\b"])'
WALK_LIMIT = 200
GREEN_REQUIRED = ("repo", "into", "branch", "from", "sha", "command", "kind")
OLDER_NAMES = {"release": "the release {tag} ({new})", "head": "the engine HEAD {new}"}


# ---- H1: the config folder --------------------------------------------------------------------------------------------

def _filled(env, name):
    value = env.get(name)
    return value if isinstance(value, str) and value.strip() else None


def upgrade_folder(env, windows: bool, home: str):
    """(folder, override used): MKWAY_UPGRADE_DIR when set and not blank; else, on Windows, `%APPDATA%\\mkway\\upgrade`; else
    `$XDG_CONFIG_HOME/mkway/upgrade`; else `<home>/.config/mkway/upgrade`."""
    over = _filled(env, "MKWAY_UPGRADE_DIR")
    if over:
        return over, True
    sep = "\\" if windows else "/"
    if windows and _filled(env, "APPDATA"):
        base = env["APPDATA"]
    elif _filled(env, "XDG_CONFIG_HOME"):
        base = env["XDG_CONFIG_HOME"]
    else:
        base = home + sep + ".config"
    return base + sep + "mkway" + sep + "upgrade", False


def folder_in_tree_text(folder: str, top: str) -> str:
    return (f"the upgrade folder {folder} is inside a git working tree ({top}) and is not ignored by it; put it outside "
            "every repository or ignore it; nothing was changed")


def installed_copy_text() -> str:
    return "run mkway upgrade from the engine repository, not from an installed copy; nothing was changed"


# ---- paths ------------------------------------------------------------------------------------------------------------------

def is_full_path(path, windows: bool) -> bool:
    if not isinstance(path, str) or not path.strip():
        return False
    if windows:
        return bool(re.match(r"[A-Za-z]:[\\/]", path)) or path.startswith("\\\\") or path.startswith("/")
    return path.startswith("/")


def folder_key(path: str, windows: bool) -> str:
    """One key for one folder: no trailing separator, and on Windows `/` for `\\` and no regard to capitals."""
    text = path.replace("\\", "/") if windows else path
    text = text.rstrip("/") or text[:1]  # a drive root `C:/` keeps its name `C:`; the root `/` stays `/`
    return text.lower() if windows else text


def _segments(name: str, windows: bool):
    """The parts of a relative folder name with `.` and empty parts dropped and `..` taken; None when it climbs out."""
    out = []
    for part in re.split(r"[\\/]+" if windows else r"/+", name):
        if part in ("", "."):
            continue
        if part == "..":
            if not out:
                return None
            out.pop()
        else:
            out.append(part)
    return out


def _joined_key(base: str, name: str, windows: bool) -> str:
    full = name if is_full_path(name, windows) else base + "/" + name
    text = full.replace("\\", "/") if windows else full
    stack = []
    for part in re.split(r"/+", text):
        if part in ("", "."):
            continue
        if part == "..":
            del stack[-1:]  # a `..` at the top stays at the top
        else:
            stack.append(part.lower() if windows else part)
    return "/".join(stack)


# ---- commands ---------------------------------------------------------------------------------------------------------------

def command_error(value) -> Optional[str]:
    """None for a command (a trimmed non-empty text, or a non-empty list of non-empty texts); else the rule."""
    if isinstance(value, str):
        return None if value.strip() else COMMAND_HINT
    if isinstance(value, list) and value and all(isinstance(x, str) and x != "" for x in value):
        return None
    return COMMAND_HINT


def _quoted(item: str) -> str:
    return '"' + item.replace('"', '\\"') + '"' if re.search(r"[\s'\"]", item) else item


def display_command(value) -> str:
    """The form the merge records: a text trimmed; a list joined by spaces, an item with white space or a quote wrapped in
    double quotes with its own double quotes written `\\"`."""
    return value.strip() if isinstance(value, str) else " ".join(_quoted(x) for x in value)


# ---- H2: the grant ----------------------------------------------------------------------------------------------------------

def grant_missing_text(file: str) -> str:
    return f"There is no grant: {file} does not exist. Only the owner writes that file."


def _text1(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def parse_grant(text: str, file: str, windows: bool):
    """(grant, None) or (None, `policy.json is invalid: <why>`). The grant: {target, roots (names in the grant's own
    spelling), shared}. Unknown keys are errors (a typo must not switch a rule off); a BOM is accepted."""
    def bad(why):
        return None, f"policy.json is invalid: {why}"

    try:
        data = json.loads(text.lstrip("﻿"))
    except ValueError as exc:
        return bad(f"not valid JSON ({exc})")
    if not isinstance(data, dict):
        return bad("top level must be an object")
    for key, home in MOVED_KEYS:
        if key in data:
            return bad(f"{key} is not a grant key: remove it from the upgrade grant ({file}); {home}")
    for key in data:
        if key not in GRANT_KEYS:
            return bad(f'unknown key "{key}" (known: {", ".join(GRANT_KEYS)})')
    target = data.get("target")
    if not is_full_path(target, windows) or re.search(r"[*?]", target):
        return bad("target must be one full path (a single folder: no list, no wildcard)")
    if "root" in data and "roots" in data:
        return bad("give root or roots, not both")
    if "root" not in data and "roots" not in data:
        return bad("root or roots is required: name the task root (or roots) inside the target that may be updated")
    if "roots" in data:
        roots = data["roots"]
        if not isinstance(roots, list):
            return bad(ROOTS_LIST)
        if not roots:
            return bad("roots needs at least one root")
        if not all(_text1(x) for x in roots):
            return bad(ROOTS_LIST)
        given = [(x, f'roots entry "{x}"') for x in roots]
    else:
        given = [(data["root"], "root")]
    sep = "\\" if windows else "/"
    names, keys = [], []
    for name, label in given:
        inside = f"{label} must be a folder inside the target (relative, for example task\\app)"
        if not _text1(name):
            return bad(inside)
        if re.search(r"[*?]", name):
            return bad(f"{label} must name one folder: no wildcard")
        parts = None if is_full_path(name, windows) else _segments(name, windows)
        if not parts:
            return bad(inside)
        names.append(sep.join(parts))
        keys.append([p.lower() if windows else p for p in parts])
    for i, mine in enumerate(keys):
        for j, other in enumerate(keys):
            if i == j:
                continue
            if mine == other:  # the first pair found is the earlier one listed first
                return bad(f'root "{names[i]}" is listed twice')
            if mine[:len(other)] == other:
                return bad(f'root "{names[i]}" is inside another root ("{names[j]}"): an update of one would rewrite '
                           "the other")
    shared = data.get("shared", "")
    if shared != "" and not is_full_path(shared, windows):
        return bad("shared must be empty or a full path")
    return {"target": target, "roots": names, "shared": shared}, None


def target_problem(wanted, grant_target: str, windows: bool) -> Optional[str]:
    """None when the call's target is the grant's folder (same folder: capitals on Windows, slashes and a trailing separator
    do not matter); else the refusal."""
    text = wanted.strip() if isinstance(wanted, str) else ""
    if not text:
        return "target is required (the one folder the policy names)."
    if not is_full_path(text, windows):
        return "target must be a full path."
    if folder_key(text, windows) != folder_key(grant_target, windows):
        return (f"{text} is not the target the policy names ({grant_target}). Only that folder is updated; other copies get "
                "the engine through git.")
    return None


def pick_root(target: str, roots, asked, windows: bool):
    """(the grant's own spelling of the root, None) or (None, text). With one listed root the name is optional; a root that is
    not listed is refused however much it looks like a task folder."""
    name = asked.strip() if isinstance(asked, str) else ""
    if not name:
        if len(roots) == 1:
            return roots[0], None
        return None, f"root is required: the policy lists {len(roots)} roots ({', '.join(roots)}); name the one to update."
    want = _joined_key(target, name, windows)
    for root in roots:
        if _joined_key(target, root, windows) == want:
            return root, None
    return None, f"root {name} is not in the policy's list ({', '.join(roots)}). Only listed roots are updated."


def lock_missing_text(root: str) -> str:
    return f"No mkway/mkway.lock in {root}: the engine is not installed there, so there is nothing to update."


def not_top_text(target: str) -> str:
    return f"{target} is not the top folder of a git working tree."


# ---- H3: release.json -------------------------------------------------------------------------------------------------------

def release_missing_text() -> str:
    return "release.json is missing at HEAD. Nothing was changed."


def pattern_error(pattern) -> Optional[str]:
    """None when the pattern is an exact path or a trailing `dir/**`; else the reason (spec 3b)."""
    if not isinstance(pattern, str) or pattern == "":
        return "it must be a non-empty text"
    if "\\" in pattern:
        return "use forward slashes"
    if pattern.startswith("/"):
        return "it must be relative to the repository"
    body = pattern[:-3] if pattern.endswith("/**") else pattern
    if "*" in body:
        return WILDCARD_TEXT
    if not _parts_ok(body):
        return DOTS_TEXT
    return None


def _parts_ok(text: str) -> bool:
    return all(part not in ("", ".", "..") for part in text.split("/"))


def parse_release(text: str):
    """(release, None) or (None, `release.json is invalid: <why>`). The release: branch, full_command and narrow_command (a
    trimmed text or a list), their display forms, narrow_paths. Unknown keys are errors."""
    def bad(why):
        return None, f"release.json is invalid: {why}"

    try:
        data = json.loads(text.lstrip("﻿"))
    except ValueError as exc:
        return bad(f"not valid JSON ({exc})")
    if not isinstance(data, dict):
        return bad("top level must be an object")
    for key in data:
        if key not in RELEASE_KEYS:
            return bad(f'unknown key "{key}" (known: {", ".join(RELEASE_KEYS)})')
    for key in ("branch", "full_command", "narrow_paths", "narrow_command"):
        if key not in data:
            return bad(f"{key} is missing")
    branch = data["branch"]
    if not (isinstance(branch, str) and BRANCH_RE.fullmatch(branch) and ".." not in branch):
        return bad("branch must be a branch name")
    for key in ("full_command",):
        if command_error(data[key]):
            return bad(f"{key} {COMMAND_HINT}")
    rules = data["narrow_paths"]
    if not (isinstance(rules, list) and rules and all(isinstance(r, list) and r for r in rules)):
        return bad("narrow_paths must be a non-empty list of non-empty path lists")
    for i, rule in enumerate(rules):
        for pattern in rule:
            why = pattern_error(pattern)
            if why:
                return bad(f'narrow_paths[{i}]: "{pattern}" is not a valid path pattern ({why})')
    if command_error(data["narrow_command"]):
        return bad(f"narrow_command {COMMAND_HINT}")
    full, narrow = _normal(data["full_command"]), _normal(data["narrow_command"])
    return {"branch": branch, "full_command": full, "full_display": display_command(full),
            "narrow_paths": [list(r) for r in rules], "narrow_command": narrow,
            "narrow_display": display_command(narrow)}, None


def _normal(command):
    return command.strip() if isinstance(command, str) else list(command)


# ---- the matcher (spec 3b, 8e) ---------------------------------------------------------------------------------------------

def _safe_path(path) -> bool:
    return isinstance(path, str) and path != "" and "\\" not in path and not path.startswith("/") and _parts_ok(path)


def covers(pattern: str, path: str) -> bool:
    """`dir/**` covers every path that starts with `dir/`; an exact pattern covers that path only; case-sensitive."""
    return path.startswith(pattern[:-2]) if pattern.endswith("/**") else path == pattern


def rule_for(paths, rules) -> Optional[int]:
    """The index of the first rule (a list of patterns) that covers EVERY path, or None. A path with a backslash, a leading
    slash or a dot part is never covered; no path, or no rule, is no route."""
    if not rules or not paths or not all(_safe_path(p) for p in paths):
        return None
    for index, rule in enumerate(rules):
        if all(any(covers(pattern, p) for pattern in rule) for p in paths):
            return index
    return None


def first_uncovered(paths, rules) -> Optional[str]:
    """The first path that no rule covers (an unsafe path included), to say why the narrow route does not apply."""
    for path in paths:
        if not _safe_path(path) or not any(covers(pattern, path) for rule in rules for pattern in rule):
            return path
    return None


# ---- H4: the green record ---------------------------------------------------------------------------------------------------

def parse_green(text: str) -> list:
    """The rows of the green record: one JSON object per line; a line that does not parse as an object is skipped."""
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _same_repo(value, repo: str, windows: bool) -> bool:
    return isinstance(value, str) and value.strip() != "" and folder_key(value, windows) == folder_key(repo, windows)


def find_row(rows, sha: str, repo: str, into: str, command: str, windows: bool, kind: str = "full"):
    """The latest row that PROVES `sha`: its sha equals it, its kind is `kind` (a narrow row also names a `from` text), its
    repo is the engine repository (same folder), its `into` is the release branch and its command is the display form of
    release.json's full_command. None otherwise."""
    found = None
    for row in rows:
        if (row.get("sha") == sha and row.get("kind") == kind and row.get("into") == into
                and row.get("command") == command and _same_repo(row.get("repo"), repo, windows)
                and (kind != "narrow" or isinstance(row.get("from"), str))):
            found = row
    return found


def _other_command(rows, sha: str, repo: str, into: str, command: str, windows: bool):
    """The command of a green row at `sha` (same repo and branch) that is not the current one, or None."""
    found = None
    for row in rows:
        if (row.get("sha") == sha and row.get("kind") in ("full", "narrow") and row.get("into") == into
                and isinstance(row.get("command"), str) and row["command"] != command
                and _same_repo(row.get("repo"), repo, windows)):
            found = row["command"]
    return found


def _branch_names_ok(text: str) -> bool:
    names = [n.strip() for n in text.split(",")]
    return all(BRANCH_RE.fullmatch(n) and ".." not in n for n in names)


def check_green_record(fields, windows: bool):
    """(the row to append, None) or (None, `<field> <why>`) for the fields of `mkway green record` (all texts, as the command
    line gives them). `branch` may hold several names joined by `, ` (a batch merge)."""
    for key in GREEN_REQUIRED:
        value = fields.get(key)
        if not isinstance(value, str) or not value.strip():
            return None, f"{key} is required"
    if not is_full_path(fields["repo"], windows):
        return None, "repo must be a full path"
    if not _branch_names_ok(fields["into"]) or "," in fields["into"]:
        return None, "into must be a branch name"
    if not _branch_names_ok(fields["branch"]):
        return None, "branch must be a branch name"
    for key in ("from", "sha"):
        if not SHA_RE.fullmatch(fields[key]):
            return None, f"{key} must be 40 lowercase hex characters"
    if fields["kind"] not in ("full", "narrow"):
        return None, "kind must be full or narrow"
    rule = fields.get("rule")
    if rule is not None and not re.fullmatch(r"\d+", rule):
        return None, "rule must be a whole number"
    seconds = fields.get("seconds")
    if seconds is not None:
        try:
            number = float(seconds)
        except ValueError:
            return None, "seconds must be a number"
        if not math.isfinite(number) or number < 0:
            return None, "seconds must be a number"
        seconds = number
    return {"kind": fields["kind"], "repo": fields["repo"], "into": fields["into"], "branch": fields["branch"].strip(),
            "from": fields["from"], "sha": fields["sha"], "command": fields["command"].strip(),
            "rule": int(rule) if rule is not None else None, "seconds": seconds}, None


# ---- the proof of the chosen sha ---------------------------------------------------------------------------------------------

def no_proof_text(green_file: str, command: str, sha: str, branch: str, reason: str) -> str:
    return (f"No green record in {green_file} shows a full, passing test run ({command}) for the engine HEAD {sha[:8]} on "
            f"{branch}, and the narrow-test route does not apply: {reason} Merge it with mkcl-merge first. Nothing was "
            "changed.")


def wrong_command_reason(sha: str, other: str, command: str) -> str:
    return (f'the mkcl merge that ended at {sha[:8]} ran "{other}", but full_command in release.json is "{command}". mkcl\'s '
            "command changed after that merge: merge again with mkcl-merge so the run uses the current command (only the "
            "owner edits that file; mkway upgrade never changes it).")


def narrow_walk(head: str, rows, repo: str, into: str, command: str, windows: bool):
    """The narrow route's walk back from `head` (spec 4): while a commit has no full row it needs a narrow row, and the walk
    steps to that row's `from`. ({green, mergeResults}, None) or (None, reason). At most 200 steps."""
    cur, merges = head, 0
    for _step in range(WALK_LIMIT):
        if find_row(rows, cur, repo, into, command, windows, "full"):
            return {"green": cur, "mergeResults": merges}, None
        row = find_row(rows, cur, repo, into, command, windows, "narrow")
        if row is None:
            other = _other_command(rows, cur, repo, into, command, windows)
            if other is not None:
                return None, wrong_command_reason(cur, other, command)
            return None, (f"commit {cur[:8]} was not produced by a mkcl merge with a passing narrow run (a hand-made or "
                          "untested commit is in the way).")
        merges += 1
        cur = row["from"]
        if not SHA_RE.fullmatch(cur):
            return None, 'a mkcl merge-result on the way has no usable "from".'
    return None, f"more than {WALK_LIMIT} merges since the last full-green head."


def narrow_cover(green: str, sha: str, paths, rules, chain, branch: str):
    """({fullGreenHead, rule, patterns, changedPaths}, None) or (None, reason): the full-green head must be on the first-parent
    chain, the changed paths (None: they could not be listed) must be non-empty, and ONE rule must cover every one."""
    if not chain or green not in chain:
        return None, f"the full-green head {green[:8]} is not on the first-parent chain of {branch}."
    if paths is None:
        return None, f"the changed paths since {green[:8]} could not be listed."
    if not paths:
        return None, f"no path changed between {green[:8]} and {sha[:8]}."
    index = rule_for(paths, rules)
    if index is None:
        path = first_uncovered(paths, rules)
        if path is None:
            return None, f"no single narrow_paths rule covers every path changed since the full-green head {green[:8]}."
        return None, f"{path} (changed since the full-green head {green[:8]}) is not covered by the narrow_paths rule."
    return {"fullGreenHead": green, "rule": index, "patterns": list(rules[index]), "changedPaths": len(paths)}, None


# ---- release mode (M1) -------------------------------------------------------------------------------------------------------

def no_tag_text() -> str:
    return "no release tag is proven green; nothing was changed"


def parse_tag_refs(text: str) -> list:
    """(tag, commit) pairs from `for-each-ref` lines `<tag> <object> <object the tag points at>`: the commit is the third word
    for an annotated tag, else the second. A line that is not that is skipped."""
    pairs = []
    for line in text.splitlines():
        words = line.split()
        if len(words) in (2, 3) and all(SHA_RE.fullmatch(w) for w in words[1:]):
            pairs.append((words[0], words[-1]))
    return pairs


def choose_release(tags, chain, rows, repo: str, into: str, command: str, windows: bool, branch: str) -> dict:
    """The newest tag `vN.N.N` by version order (not tag date) whose commit is on the first-parent `chain` of the release
    branch AND is proven by a full row. {tag, sha, skipped}: `skipped` lists (tag, reason) of the newer tags passed over; a
    narrow chain never proves a tag. tag is None when none qualifies."""
    found = []
    for tag, sha in tags:
        match = TAG_RE.fullmatch(tag)
        if match:
            found.append((tuple(int(n) for n in match.groups()), tag, sha))
    found.sort(reverse=True)
    skipped, on_chain = [], set(chain or ())
    for _version, tag, sha in found:
        if sha not in on_chain:
            skipped.append((tag, f"not on the first-parent chain of {branch}"))
        elif find_row(rows, sha, repo, into, command, windows, "full") is None:
            skipped.append((tag, "no full green record"))
        else:
            return {"tag": tag, "sha": sha, "skipped": skipped}
    return {"tag": None, "sha": None, "skipped": skipped}


# ---- the downgrade guard and the versions ----------------------------------------------------------------------------------

def semver_tuple(text):
    """(major, minor, patch) read from the start of a version text, else None."""
    match = SEMVER_RE.match(text) if isinstance(text, str) else None
    return tuple(int(n) for n in match.groups()) if match else None


@dataclass(frozen=True)
class GuardFacts:
    """What `decide_upgrade` reads; a fact left None has not been read yet and its check is skipped. `mode` is `release` (a
    tag) or `head`."""
    chosen: str
    mode: str
    tag: Optional[str] = None
    lock_source: Optional[str] = None
    source_in_repo: Optional[bool] = None
    chosen_is_ancestor: Optional[bool] = None
    source_is_ancestor: Optional[bool] = None
    chosen_version: Optional[str] = None
    lock_semver: Optional[str] = None


@dataclass(frozen=True)
class Verdict:
    """allow | refuse(text) | uptodate (the lock already holds the chosen sha: stop, spec 4.7)."""
    kind: str
    text: str = ""


def _refuse(text: str) -> Verdict:
    return Verdict("refuse", text)


def decide_upgrade(f: GuardFacts) -> Verdict:
    """Spec 4 steps 7 to 8 with the downgrade guard (7a to 7c, 8a), in the order the shell can read their facts. Every refusal
    ends «Nothing was changed.»"""
    if f.lock_source == f.chosen:
        return Verdict("uptodate")
    if not (isinstance(f.lock_source, str) and SHA_RE.fullmatch(f.lock_source)):
        return _refuse("the installed engine has no source commit (installed from a plain folder); reinstall from the "
                       "engine repository. Nothing was changed.")
    old, new = f.lock_source[:8], f.chosen[:8]
    if f.source_in_repo is False:
        return _refuse(f"the installed engine {old} is not in the engine repository. Nothing was changed.")
    if f.chosen_is_ancestor:
        who = OLDER_NAMES[f.mode].format(tag=f.tag, new=new)
        return _refuse(f"{who} is older than the installed engine {old}. Nothing was changed.")
    if f.chosen_is_ancestor is False and f.source_is_ancestor is False:
        return _refuse(f"the engine {new} and the installed engine {old} have diverged. Nothing was changed.")
    if f.chosen_version is not None:
        chosen, lock = semver_tuple(f.chosen_version), semver_tuple(f.lock_semver)
        if chosen is None or lock is None:
            return _refuse(f'The version cannot be compared (engine VERSION "{f.chosen_version.strip()}", lock '
                           f'"{f.lock_semver.strip() if isinstance(f.lock_semver, str) else "none"}"). A major change is the '
                           "owner's hand; nothing was changed.")
        if chosen[0] != lock[0]:
            return _refuse(f"The engine is on major version {chosen[0]} and the install is on {lock[0]}. A new major is the "
                           "owner's hand; nothing was changed.")
        if chosen < lock:
            return _refuse(f"version {f.chosen_version.strip()} is lower than the installed {f.lock_semver.strip()}. "
                           "Nothing was changed.")
    return Verdict("allow")


# ---- the install, the ledger, the commit ------------------------------------------------------------------------------------

def _unsafe_path(path: str) -> bool:
    return (path.startswith("-") or bool(re.match(r"[A-Za-z]:|[\\/]", path))
            or ".." in re.split(r"[\\/]", path))


def read_install_line(out: str):
    """({paths, prefix}, None) or (None, text): the one line install prints, `git -C "<root>" add <paths>; ... commit -m
    "[<prefix> ]mkway <ver>: install" -- <paths>`. Every path is relative, not option-like and inside the root."""
    match = INSTALL_LINE.search(out)
    if not match:
        return None, "install ran, but its commit line was not found in its output, so the paths to commit are not known."
    paths = match.group(1).split()
    for path in paths:
        if _unsafe_path(path):
            return None, f'install printed an unsafe path ("{path}"), so nothing was committed.'
    message = re.fullmatch(r"(?:(.*) )?mkway \S+: install", match.group(2))
    if not message:
        return None, (f'install\'s commit message ("{match.group(2)}") has an unknown form, so the commit prefix is not '
                      "known.")
    return {"paths": paths, "prefix": message.group(1) or ""}, None


def commit_message_for(prefix: str, sha: str) -> str:
    return (prefix + " " if prefix else "") + f"mkway install {sha[:8]}"


def ledger_quote(old: str, new: str, narrow, release_tag, folder, migrated: bool = False) -> str:
    """`engine updated <old8> -> <new8>, grant policy.json, dry run ok`, then the narrow head, the release tag (release mode),
    the upgrade folder (when the override was used) and, when the profile key was renamed, that rename (MW-107, R274a 10)."""
    text = f"engine updated {old[:8]} -> {new[:8]}, grant policy.json, dry run ok"
    if narrow:
        text += f", narrow-tested head (full-green head {narrow['fullGreenHead'][:8]}, narrow rule {narrow['rule']})"
    if release_tag:
        text += f", release {release_tag}"
    if folder:
        text += f", upgrade dir {folder}"
    if migrated:
        text += f", profile key {OLD_OUTSIDE_KEY} renamed to {NEW_OUTSIDE_KEY}"
    return text


# ---- the outside-write key (MW-107, R274, R274a 5 and 10, R274b 1) ------------------------------------------------------------

OLD_OUTSIDE_KEY, NEW_OUTSIDE_KEY = "leads.outside_writable", "paths.outside_writable"
PROFILE_FILE = "mkway/profile.json"
OUTSIDE_RULE = ("a session writes only inside its root and in the folders of paths.outside_writable (the engine's own three "
                "and the profile's additions); the gate is hard from install, so before the owner installs the lead confirms "
                "that the list holds every outside folder the open cards write")


def migrate_profile(profile) -> tuple:
    """(the profile with `leads.outside_writable` moved into `paths.outside_writable`, the number of folders moved), or
    (None, 0) when the profile has no such key and there is nothing to migrate. The folders of the old key come after those
    already in the new one, each once; an emptied `leads` object is dropped; no other key is touched."""
    leads = profile.get("leads") if isinstance(profile, dict) else None
    if not isinstance(leads, dict) or "outside_writable" not in leads:
        return None, 0
    value = leads["outside_writable"]
    moved = [item for item in value if isinstance(item, str)] if isinstance(value, list) else []  # R274e (W45): no value that is no text travels
    kept = {key: value for key, value in leads.items() if key != "outside_writable"}
    paths = profile.get("paths") if isinstance(profile.get("paths"), dict) else {}
    old = paths.get("outside_writable") if isinstance(paths.get("outside_writable"), list) else []
    merged = old + [item for item in moved if item not in old]
    result = {key: value for key, value in profile.items() if key not in ("leads", "paths")}
    if kept:
        result["leads"] = kept
    result["paths"] = {**paths, "outside_writable": merged}
    return result, len(moved)


def ignored_text(profile) -> str:
    """R274e (W45): what the migration leaves behind in a malformed old value, said in the dry run: the whole value when it is no
    list, or the items that are no text; "" when the value is sound."""
    leads = profile.get("leads") if isinstance(profile, dict) else None
    value = leads.get("outside_writable") if isinstance(leads, dict) else None
    if not isinstance(value, list):
        return "the value is not a list and is ignored"
    bad = sum(1 for item in value if not isinstance(item, str))
    if not bad:
        return ""
    return f"{bad} item that is no text is ignored" if bad == 1 else f"{bad} items that are no text are ignored"


def migration_text(count: int, ignored: str = "") -> str:
    return f"{OLD_OUTSIDE_KEY} -> {NEW_OUTSIDE_KEY} ({count} folder{'' if count == 1 else 's'}{'; ' + ignored if ignored else ''})"


def migration_failed_text(reason: str) -> str:
    """MW-129 (R310 3 c): the copy of the card records into the shared folder failed before the install: the task stays on its
    old engine, the tree is clean, and the way out is the same owner line again."""
    return (f"the shared card records could not be copied ({reason}). The engine was not changed. Make the shared folder "
            f"writable, then run the same upgrade line again. Nothing was changed.")


def profile_dirty_text() -> str:
    return (f"{PROFILE_FILE} has changes that are not committed, and the upgrade renames {OLD_OUTSIDE_KEY} in it and commits "
            f"the file. Commit or restore {PROFILE_FILE} first, then run the upgrade again. Nothing was changed.")


# ---- messages ---------------------------------------------------------------------------------------------------------------

def no_by_text() -> str:
    return ("The engine's ledger command has no --by option, so it cannot record a row by=" + TOOL_ID + ". A mkway card has "
            "to add that first; nothing was changed.")


def engine_dirty_text(engine: str, count: int) -> str:
    return f"The engine repository {engine} is not clean ({count} changed or untracked files). Nothing was changed."


def wrong_branch_text(branch: str, current) -> str:
    where = f"it is on {current}" if current else "detached HEAD"
    return f"The engine repository is not on branch {branch} ({where})."


def engine_unreadable_text(engine: str, why: str) -> str:
    return f"The engine repository {engine} cannot be read ({why})."


def root_unreadable_text(root: str, why: str) -> str:
    return f"The task root {root} cannot be read ({why})."


def lock_unreadable_text(file: str, why: str) -> str:
    return f"The lock {file} cannot be read ({why})."


def green_unreadable_text(file: str, why: str) -> str:
    return f"Cannot read the green record {file} ({why})."


def dirty_paths_text(lines) -> str:
    return (f"The install paths already have changes that are not this update's ({len(lines)}). Nothing was changed.\n"
            + "\n".join(lines[:20]))


def up_to_date_summary(target: str, sha: str) -> str:
    return f"The engine in {target} is up to date ({sha[:8]})."


def updated_summary(target: str, old: str, new: str, commit: str, message: str) -> str:
    return f"Engine updated {old[:8]} -> {new[:8]} in {target}; one commit ({commit[:8]}: {message})."


def install_failed_text(how: str, tail: str) -> str:
    return f"install failed ({how}): {tail}"


def written_note(root: str) -> str:
    return f"The install may have written files in {root}; nothing was committed. Look at git status there."


def log_unwritable_text(why: str) -> str:
    return f"Cannot write the log, so nothing was changed ({why})."


def log_unwritable_after_text(why: str) -> str:
    return f"Cannot write the log ({why})."


def ledger_failed_text(why: str) -> str:
    return f"the ledger row was not written ({why})."


def ledger_unrunnable_text(python: str, why: str) -> str:
    return f"{python} could not run the engine's ledger command ({why})."
