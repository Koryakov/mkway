"""The branch profile: load, validate, and read the values the dispatcher needs (card MW-002, deliverable 5).

A broken profile never raises here: `load` returns its errors, and the dispatcher warns `profile-invalid` and
runs no gate. Only an unexpected read failure (for example the path is a folder) raises; the dispatcher's outer
handler logs it as `dispatcher-error`.
"""
from __future__ import annotations

import datetime
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
    errors = [e for e in errors if not e.startswith(LEGACY_OUTSIDE_KEY)]  # MW-107 (R274a 10): no profile error for the old key
    if isinstance(profile, dict):
        for group, key in sorted(engine_constants(schema)):
            if isinstance(profile.get(group), dict) and key in profile[group]:
                errors.append(f"{group}.{key}: engine constant, the profile cannot set it")
        errors.extend(_outside_errors(profile))
    return errors


LEGACY_OUTSIDE_KEY = "leads.outside_writable"  # MW-107 (R274, R274a 10, R274b 1): renamed `paths.outside_writable`; an alias until the
                                               # upgrade renames it in the profile (kept until the next major, removed with it)


def _outside_errors(profile) -> list:
    """MW-103: a pattern of `paths.outside_writable` with a `..` part is invalid (the schema checks the type, the length and
    the start). The old key `leads.outside_writable` is no error, whatever it holds (R274a 10): it is an alias."""
    section = profile.get("paths")
    items = section.get("outside_writable") if isinstance(section, dict) else None
    if not isinstance(items, list):
        return []
    return [f"paths.outside_writable[{i}]: must not hold a .. part" for i, item in enumerate(items)
            if isinstance(item, str) and ".." in re.split(r"[/\\]", item)]


def _valid_relative(value) -> bool:
    return isinstance(value, str) and value != "" and schema_check._format_error("relative-path", value) is None


def state_dir(root: Path, profile) -> Path:
    """`<root>/<state.dir>`; the default `mkway/state` when the profile is missing or its value is not usable."""
    value = profile.get("state", {}).get("dir") if isinstance(profile, dict) and isinstance(
        profile.get("state"), dict) else None
    return Path(root) / (value if _valid_relative(value) else DEFAULT_STATE_DIR)


def main_mirror_state(root: Path, own: Path):
    """`<main work tree root>/<the same path below the top>/<state.dir>` when `root` is in a linked git work tree (its
    git dir is not the common one), else None. Read-only: `mkway check` looks there for state that 0.2.0 and 0.2.1
    wrote outside the root (MW-026). Any failure (no git, a timeout, an odd layout) is None."""
    try:
        import runner
        probes = [runner.git(root, "rev-parse", flag) for flag in ("--git-common-dir", "--git-dir", "--show-toplevel")]
        if any(p.returncode != 0 for p in probes):
            return None
        common, gitdir, top = (Path(root, p.stdout.strip()).resolve() for p in probes)
        if common == gitdir or common.name != ".git":
            return None
        below = Path(root).resolve().relative_to(top)
        return common.parent / below / own.resolve().relative_to(Path(root).resolve())
    except Exception:
        return None


def shared_state_dir(root: Path, profile) -> Path:
    """Where the files that cross worktrees live (`leads.json`, `inbox/`, `sessions.jsonl`, `pings.jsonl`,
    `dead-letter.jsonl`, the lock markers). The engine never writes outside the mkway root by its own path logic
    (MW-026), so it is `state_dir`, unless the owner opts in with the absolute path `state.shared_dir`; a value that is
    not an absolute path is ignored."""
    value = profile.get("state", {}).get("shared_dir") if isinstance(profile, dict) and isinstance(
        profile.get("state"), dict) else None
    if isinstance(value, str) and schema_check._format_error("absolute-path", value) is None:
        return Path(value)
    return state_dir(root, profile)


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


def ping_mode(profile) -> str:
    """`gates.ping.mode` (MW-076): `watch` or `trip`; anything else, or no key, is `trip`."""
    gates = profile.get("gates") if isinstance(profile, dict) else None
    ping = gates.get("ping") if isinstance(gates, dict) else None
    mode = ping.get("mode") if isinstance(ping, dict) else None
    return "watch" if mode == "watch" else "trip"


def sessions_file(profile):
    """`sessions.file` (MW-076): the path of mkcl's sessions record, as written; None when missing or not text."""
    group = profile.get("sessions") if isinstance(profile, dict) else None
    value = group.get("file") if isinstance(group, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


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


def outside_writable(profile) -> list:
    """`paths.outside_writable` (MW-103, R255b; R274: for every session): the engine's own list from defaults.json, then the
    profile's additions that are usable (a string that is absolute or starts with `<home>/` or `<temp>/`, with no `..` part),
    then the folders of the old key `leads.outside_writable`, an alias until the upgrade renames it (R274b 1: nothing gets
    narrower before the rename). A profile adds, never removes; an unusable item is skipped, as the other accessors do, so a
    gate never fails on a bad key."""
    base = list(json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))["paths"]["outside_writable"])
    for group in ("paths", "leads"):
        section = profile.get(group) if isinstance(profile, dict) else None
        items = section.get("outside_writable") if isinstance(section, dict) else None
        for item in items if isinstance(items, list) else []:
            usable = (isinstance(item, str) and re.match(r"(/|[A-Za-z]:[/\\]|<home>/|<temp>/)", item)
                      and ".." not in re.split(r"[/\\]", item))
            if usable and item not in base:
                base.append(item)
    return base


CARDS_STALE_HOURS = 4  # MW-045: the same figure as `leads.escalate_hours`


def cards_stale_hours(profile):
    """`cards.stale_hours` (MW-045): hours a card holder may stay unseen before a take releases its card. An unusable
    value takes the default, as the other accessors do."""
    cards = profile.get("cards") if isinstance(profile, dict) else None
    hours = cards.get("stale_hours") if isinstance(cards, dict) else None
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not hours > 0:
        return CARDS_STALE_HOURS
    return hours


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


def session_id_watch_until(profile) -> str:
    """MW-110: `messaging.session_id_watch_until`, the last day an unset launcher variable is warned about and allowed (an
    ISO date, `YYYY-MM-DD`). Empty means no expiry, and so does any unusable value (not text, not a calendar date), so a
    bad key never ends the transition early and never fails a gate."""
    raw = profile.get("messaging") if isinstance(profile, dict) else None
    value = raw.get("session_id_watch_until") if isinstance(raw, dict) else None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return ""
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return ""
    return value


def session_id_watch_unreadable(profile) -> str:
    """MW-110 (R279c Q2): the value of `messaging.session_id_watch_until` as written when it cannot be read as a date; empty
    when the key is absent, empty or a date. Such a value counts as PASSED (fail closed): the gates, the start line and
    `mkway check` name it. A profile that is not an object has none."""
    raw = profile.get("messaging") if isinstance(profile, dict) else None
    value = raw.get("session_id_watch_until") if isinstance(raw, dict) else None
    if value is None or value == "" or session_id_watch_until(profile):
        return ""
    return str(value)


WAKE_DEFAULTS = {"mode": "on", "deadline_seconds": 14400, "poll_seconds": 5}  # MW-078; the same values as defaults.json


def wake_settings(profile) -> dict:
    """The inbox waiter's keys (MW-078): `mode` (`on` or `off`), `deadline_seconds` (a whole number above 0) and
    `poll_seconds` (a number above 0). An unusable value (a boolean included) takes its default, so the waiter never
    fails on a bad key."""
    raw = profile.get("wake") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    out = dict(WAKE_DEFAULTS)
    if raw.get("mode") in ("on", "off"):
        out["mode"] = raw["mode"]
    seconds = raw.get("deadline_seconds")
    if isinstance(seconds, int) and not isinstance(seconds, bool) and seconds > 0:
        out["deadline_seconds"] = seconds
    poll = raw.get("poll_seconds")
    if isinstance(poll, (int, float)) and not isinstance(poll, bool) and poll > 0:
        out["poll_seconds"] = poll
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


def git_builtins_extra(profile) -> set:
    """MW-031: `lock_gate.git_builtins_extra`, git built-in names the owner adds to the engine list; none when the key
    is missing or unusable."""
    group = profile.get("lock_gate") if isinstance(profile, dict) else None
    value = group.get("git_builtins_extra") if isinstance(group, dict) else None
    clean = _clean_strings(value)
    return set(clean) if clean else set()


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


def verdict_add_mode(profile) -> str:
    """`tests.verdict_add.mode` (MW-080): `trip` or `watch` as written, else empty; the command takes a missing or unusable
    key as trip (ruling R196a)."""
    group = profile.get("tests") if isinstance(profile, dict) else None
    sub = group.get("verdict_add") if isinstance(group, dict) else None
    value = sub.get("mode") if isinstance(sub, dict) else None
    return value if value in ("trip", "watch") else ""


RED_PROOF_MODES = ("trip", "watch")  # `tests.red_proof.mode` (MW-072): trip refuses, watch warns and writes the record


def red_proof_mode(profile) -> str:
    """`tests.red_proof.mode`: `watch` or `trip`; a missing or unusable value is `trip`, so the gate never turns itself off."""
    group = profile.get("tests") if isinstance(profile, dict) else None
    raw = group.get("red_proof") if isinstance(group, dict) else None
    mode = raw.get("mode") if isinstance(raw, dict) else None
    return mode if mode in RED_PROOF_MODES else "trip"


def red_proof_decision_pattern(profile, root=None) -> str:
    """`tests.red_proof.decision_pattern` (MW-090; the default, MW-134, R348a): the regex of the decisions a commit message may name.
    A key that is PRESENT stays as written, an empty one included (an explicit off); a present value that is no string is the empty
    string, which is no decision (fail closed). A MISSING key reads, when the caller names the `root` and the root has a ledger file,
    the ledger's id form (`ids.decision_row`, else `ledger.DEFAULT_ID`); with no ledger file, or with no `root`, it is the empty
    string as before. The one place the default lives, so every caller sees the same pattern. Whether it compiles is the gate's
    question."""
    group = profile.get("tests") if isinstance(profile, dict) else None
    raw = group.get("red_proof") if isinstance(group, dict) else None
    if isinstance(raw, dict) and "decision_pattern" in raw:
        pattern = raw["decision_pattern"]
        return pattern if isinstance(pattern, str) else ""
    if root is None:
        return ""
    import ledger  # late: the ledger imports this module
    return ledger.id_pattern(profile) if ledger.path(root, profile).is_file() else ""


def commit_tests_budget(profile):
    """`gates.commit_tests.budget_seconds` when it is a number above 0, else the default (780)."""
    value = (profile.get("gates") or {}).get("commit_tests") if isinstance(profile, dict) and isinstance(
        profile.get("gates"), dict) else None
    value = value.get("budget_seconds") if isinstance(value, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return value
    return COMMIT_TESTS_BUDGET


def shape_mode(profile) -> str:
    """`tests.shape.mode` (MW-073): `watch` when the profile says so, else `trip`; a missing or unusable value is `trip`."""
    group = profile.get("tests") if isinstance(profile, dict) else None
    shape = group.get("shape") if isinstance(group, dict) else None
    return "watch" if isinstance(shape, dict) and shape.get("mode") == "watch" else "trip"


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
