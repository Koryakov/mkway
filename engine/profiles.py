"""The branch profile: load, validate, and read the values the dispatcher needs (card MW-002, deliverable 5).

A broken profile never raises here: `load` returns its errors, and the dispatcher warns `profile-invalid` and
runs no gate. Only an unexpected read failure (for example the path is a folder) raises; the dispatcher's outer
handler logs it as `dispatcher-error`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import schema_check

ENGINE_DIR = Path(__file__).resolve().parent  # the engine's own files (schema, defaults); never the task root
DEFAULTS_FILE = ENGINE_DIR / "defaults.json"
DEFAULT_BUNDLE_ROOT = "mkway"
DEFAULT_STATE_DIR = "mkway/state"


def load(path: Path):
    """(profile or None, errors). Not found and not JSON are errors; the schema errors follow."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, ["(profile): not found"]
    except UnicodeDecodeError:  # an ANSI save: a broken profile, so a warn (fix check N3)
        return None, ["(profile): not UTF-8"]
    try:
        profile = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"(profile): not valid JSON (line {exc.lineno})"]
    return profile, validate(profile)


def engine_constants(schema: Optional[dict] = None) -> set:
    """(group, key) pairs of defaults.json that the schema does not declare: the profile cannot set them."""
    schema = schema if schema is not None else schema_check.load_schema()
    defaults = json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))
    out = set()
    for group, keys in defaults.items():
        if group.startswith("_") or not isinstance(keys, dict):
            continue
        declared = schema.get("properties", {}).get(group, {}).get("properties", {})
        out |= {(group, key) for key in keys if key not in declared}
    return out


def validate(profile) -> list:
    schema = schema_check.load_schema()
    errors = schema_check.check(profile, schema)
    if isinstance(profile, dict):
        for group, key in sorted(engine_constants(schema)):
            if isinstance(profile.get(group), dict) and key in profile[group]:
                errors.append(f"{group}.{key}: engine constant, the profile cannot set it")
    return errors


def _valid_relative(value) -> bool:
    return isinstance(value, str) and value != "" and schema_check._format_error("relative-path", value) is None


def state_dir(root: Path, profile) -> Path:
    """`<root>/<state.dir>`; the default `mkway/state` when the profile is missing or its value is not usable."""
    value = profile.get("state", {}).get("dir") if isinstance(profile, dict) and isinstance(
        profile.get("state"), dict) else None
    return Path(root) / (value if _valid_relative(value) else DEFAULT_STATE_DIR)


_SHARED: dict = {}  # (root, state dir) -> the shared dir: resolved once per process (MW-017, addition 1)


def _linked_main_state(root: Path, own: Path) -> Path:
    """`<main work tree root>/<the same path below the top>/<state.dir>` when `root` is in a linked git work tree (its
    git dir is not the common one), else `own`. Raises on anything unreadable: the caller then takes `own`."""
    import runner
    probes = [runner.git(root, "rev-parse", flag) for flag in ("--git-common-dir", "--git-dir", "--show-toplevel")]
    if any(p.returncode != 0 for p in probes):
        return own
    common, gitdir, top = (Path(root, p.stdout.strip()).resolve() for p in probes)
    if common == gitdir or common.name != ".git":
        return own
    below = Path(root).resolve().relative_to(top)
    return common.parent / below / own.resolve().relative_to(Path(root).resolve())


def shared_state_dir(root: Path, profile) -> Path:
    """Where files that cross work trees live (MW-017: `leads.json`, `inbox/`, `sessions.jsonl`). In a linked git work
    tree it is the main work tree's state folder; in the main one, in a folder with no git, and when git fails it is
    `state_dir`. Everything else stays in each work tree's own state folder."""
    own = state_dir(root, profile)
    key = (str(Path(root)), str(own))
    if key not in _SHARED:
        try:
            _SHARED[key] = _linked_main_state(Path(root), own)
        except Exception:  # git missing, a timeout, a state folder outside the root: the own folder
            _SHARED[key] = own
    return _SHARED[key]


OWNER_ASK_DIR = "asks"  # inside the bundle: `<bundle.root>/asks`, unless the profile names a folder (MW-007)
OWNER_ASK_MARKERS = ["Request:"]
OWNER_ASK_SOURCES = ["ledger"]  # MW-008: the past decisions; the name `ledger` has its own line form in the ask gate
OWNER_ASK_MAX_OPEN = 1  # MW-014: one open ask per session
OWNER_ASK_TOOL_ALLOWED = False  # MW-014: the pop-up question tool is off


def _clean_strings(value, *, source_name: bool = False):
    """The list when it is non-empty and every item is a usable string, else None (the default then applies)."""
    if not isinstance(value, list) or not value:
        return None
    for item in value:
        if not isinstance(item, str) or not item or (source_name and (item != item.strip() or ":" in item
                                                                        or any(c.isspace() for c in item))):
            return None
    return list(value)


def owner_ask(profile) -> dict:
    """The ask gate's settings (MW-007): `dir` (repo-relative, posix), `markers`, `sources`. A missing or unusable
    value takes its default, as `state_dir` does, so a gate never fails on a bad key."""
    raw = profile.get("owner_ask") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    folder = raw.get("dir")
    if _valid_relative(folder):
        folder = folder.replace("\\", "/").strip("/")
    else:
        folder = f"{bundle_root(profile)}/{OWNER_ASK_DIR}"
    open_max = raw.get("max_open")
    if isinstance(open_max, bool) or not isinstance(open_max, int) or open_max < 1:
        open_max = OWNER_ASK_MAX_OPEN
    allowed = raw.get("tool_allowed")
    return {"dir": folder,
            "markers": _clean_strings(raw.get("markers")) or list(OWNER_ASK_MARKERS),
            "sources": _clean_strings(raw.get("sources"), source_name=True) or list(OWNER_ASK_SOURCES),
            "max_open": open_max,  # MW-014: open asks one session may have
            "tool_allowed": allowed if isinstance(allowed, bool) else OWNER_ASK_TOOL_ALLOWED}


def notify_command(profile):
    """`notify.command` stripped, or None when it is missing or unusable (nothing then runs; MW-014)."""
    group = profile.get("notify") if isinstance(profile, dict) else None
    value = group.get("command") if isinstance(group, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def outbox_settings(profile) -> dict:
    """The outbox check's settings (MW-019): `dir` and `patterns_file` as posix repo-relative paths, `checkers` as a
    list of agent types. A missing or unusable value is none (an empty list for `checkers`): the engine invents no
    folder and no checker, so a profile that names none has no outbox, or no valid check."""
    raw = profile.get("outbox") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}

    def folder(value):
        return value.replace("\\", "/").strip("/") if _valid_relative(value) else None
    return {"dir": folder(raw.get("dir")), "checkers": _clean_strings(raw.get("checkers")) or [],
            "patterns_file": folder(raw.get("id_patterns_file"))}


def deliverable_settings(profile) -> dict:
    """The deliverables settings (MW-020): `paths` (globs of the result files made for others) and `require_base`
    (globs of the paths whose check file must name a delivered base). A missing or unusable value is an empty list:
    the engine invents no path."""
    raw = profile.get("deliverables") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    return {"paths": _clean_strings(raw.get("paths")) or [], "require_base": _clean_strings(raw.get("require_base")) or []}


LEADS_ESCALATE_HOURS = 4  # MW-017: hours a notice may stay unacked before the owner sees it
LEADS_MAX_CARDS = 5  # MW-017: the soft cap of cards one lead has ordered


def leads_settings(profile) -> dict:
    """The lead role's settings (MW-017): `escalate_hours`, `max_cards`. An unusable value takes its default, as the
    other accessors do, so a gate never fails on a bad key."""
    raw = profile.get("leads") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    hours, cap = raw.get("escalate_hours"), raw.get("max_cards")
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not hours > 0:
        hours = LEADS_ESCALATE_HOURS
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        cap = LEADS_MAX_CARDS
    return {"escalate_hours": hours, "max_cards": cap}


MESSAGING_DEFAULTS = {"duplicate_window_hours": 1, "dead_hours": 12, "ack_reminder_minutes": 30}  # MW-018


def messaging_settings(profile) -> dict:
    """The messaging keys (MW-018): `duplicate_window_hours`, `dead_hours`, `ack_reminder_minutes`. An unusable value
    (not a number above 0, a boolean included) takes its default, as the other accessors do, so a gate never fails on a
    bad key."""
    raw = profile.get("messaging") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key, default in MESSAGING_DEFAULTS.items():
        value = raw.get(key)
        ok = isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
        out[key] = value if ok else default
    return out


DELETE_MAX_BACKUP_MB = 5120  # the largest backup a delete may make (MW-009)
DELETE_SQL_ALLOWED = False


def delete_settings(profile) -> dict:
    """The delete gate's settings (MW-009): `max_backup_mb`, `sql_allowed`. An unusable value takes its default."""
    raw = profile.get("delete") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    size = raw.get("max_backup_mb")
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not size > 0:
        size = DELETE_MAX_BACKUP_MB
    allowed = raw.get("sql_allowed")
    return {"max_backup_mb": size, "sql_allowed": allowed if isinstance(allowed, bool) else DELETE_SQL_ALLOWED}


TEST_ROOTS = ["tests"]  # `test_roots` default (MW-005; KEYS.md row 1)
COMMIT_TESTS_BUDGET = 780  # seconds: `gates.commit_tests.budget_seconds` default (MW-005)
DOCS_DEFAULT = ["cards/**", "ledger/**", "*.md"]  # `paths.docs` default; the first two sit in the bundle (MW-005)
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def test_roots(profile) -> list:
    """The test folders (repo-relative, posix, no trailing slash); `["tests"]` when the key is missing or unusable."""
    value = profile.get("test_roots") if isinstance(profile, dict) else None
    if isinstance(value, list) and value and all(_valid_relative(v) for v in value):
        return [v.replace("\\", "/").strip("/") for v in value]
    return list(TEST_ROOTS)


def test_env(profile) -> list:
    """The environment variable names the commit's test run passes; none when the key is missing or unusable."""
    value = profile.get("test_env") if isinstance(profile, dict) else None
    if isinstance(value, list) and all(isinstance(v, str) and _ENV_NAME.match(v) for v in value):
        return list(value)
    return []


def tests_command(profile):
    """`tests.command` stripped, or None when it is missing or unusable (the gate then runs the default)."""
    group = profile.get("tests") if isinstance(profile, dict) else None
    value = group.get("command") if isinstance(group, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def commit_tests_budget(profile):
    """`gates.commit_tests.budget_seconds` when it is a number above 0, else the default (780)."""
    value = (profile.get("gates") or {}).get("commit_tests") if isinstance(profile, dict) and isinstance(
        profile.get("gates"), dict) else None
    value = value.get("budget_seconds") if isinstance(value, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return value
    return COMMIT_TESTS_BUDGET


def docs_globs(profile) -> list:
    """`paths.docs`, or the default: the bundle's cards and ledger folders and Markdown files (KEYS.md)."""
    paths = profile.get("paths") if isinstance(profile, dict) else None
    value = paths.get("docs") if isinstance(paths, dict) else None
    if isinstance(value, list) and value and all(isinstance(v, str) and v for v in value):
        return list(value)
    bundle = bundle_root(profile)
    return [f"{bundle}/{DOCS_DEFAULT[0]}", f"{bundle}/{DOCS_DEFAULT[1]}", DOCS_DEFAULT[2]]


def docs_only(profile, rels) -> bool:
    """True when `rels` (root-relative paths) is not empty and every path matches a `paths.docs` glob."""
    import helpers  # late: helpers has no dependency on the profile, and the dispatcher imports this module first
    rels = list(rels)
    globs = docs_globs(profile)
    return bool(rels) and all(any(helpers.matches(r, g) for g in globs) for r in rels)


def vcs(profile):
    return profile.get("vcs") if isinstance(profile, dict) else None


def bundle_root(profile) -> str:
    value = profile.get("bundle", {}).get("root") if isinstance(profile, dict) and isinstance(
        profile.get("bundle"), dict) else None
    return value if _valid_relative(value) else DEFAULT_BUNDLE_ROOT


def _levels(profile, gate_name: str):
    """The profile's switch objects along a dotted gate name: gates.a, gates.a.b, ..."""
    node = profile.get("gates", {}) if isinstance(profile, dict) else {}
    for part in gate_name.split("."):
        node = node.get(part) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            return
        yield node


def gate_on(profile, gate_name: str, default_on: bool) -> bool:
    """A level with `on: false` turns the gate off; else the deepest `on` wins; else the manifest default."""
    value = bool(default_on)
    for level in _levels(profile, gate_name):
        if "on" in level:
            if level["on"] is False:
                return False
            value = bool(level["on"])
    return value


def budget_seconds(profile, gate_name: str):
    found = None
    for level in _levels(profile, gate_name):
        if isinstance(level.get("budget_seconds"), (int, float)) and not isinstance(level["budget_seconds"], bool):
            found = level["budget_seconds"]
    return found
