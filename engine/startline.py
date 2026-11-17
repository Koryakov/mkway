"""The start line and the drift check (card MW-002, deliverable 8; R11 point 5, map section 3.4).

At SessionStart the dispatcher prints one block (as additionalContext): the version and the profile path; the
gates that are on, the gates that are off and the gates not loaded; vcs; the profile's broken keys, if any; the drift result; the count of
files in `locks/`; the gate-error and dispatcher-error counts; the user layer, for information only.

`drift(...)` compares (1) the copy's hash with the lock, (2) the live owned hook entries with a fresh generation as
whole entries (event, matcher, command, timeout, onFailure, asyncRewake), and `<state.dir>/machine.json` with the interpreter
of those entries (it must run and report Python 3.9 or later: `drift-machine`), (3) the profile with the schema. The start line turns any
difference into one warning line naming the fix. It only warns here; the MW-003 commit gate will call it too.
"""
from __future__ import annotations

import json
from pathlib import Path

import gatemode
import helpers
import install
import paths
import profiles

USER_LAYER = "~/.claude/settings.json"
MACHINE_CHECK_SECONDS = 5  # the start probe's own timeout, below the start entry's 15 s (fix check 3 L5)


def _lock(root: Path, bundle: str):
    try:
        return json.loads((Path(root) / bundle / "mkway.lock").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _version_text(root: Path, bundle: str, lock) -> str:
    """MW-016: `v<VERSION of the copy> (<sha or ref>)`: the copy's own `VERSION` file; the sha is the lock's source sha
    (12 characters), else the lock's version text (the ref: a tag or `unversioned`)."""
    try:
        version = (Path(root) / bundle / "engine" / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        version = ""
    if not version:
        return "(no VERSION file)"
    lock = lock or {}
    ref = str(lock.get("source_sha") or "")[:12] or lock.get("version") or "no lock"
    return f"v{version} ({ref})"


def _machine_python(root: Path, profile):
    """The interpreter install used on this machine (<state.dir>/machine.json), or None (C27). MW-027: in a worktree
    that no install ran in, the file is missing (state is untracked) and the committed entries carry the profile's
    `python.command`, so that is the answer then."""
    try:
        value = json.loads((profiles.state_dir(root, profile) / install.MACHINE_FILE).read_text("utf-8"))["python"]
    except FileNotFoundError:
        value = (profile.get("python") or {}).get("command") or "python" if isinstance(profile, dict) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return value if isinstance(value, str) and value.strip() else None


def _whole(entries) -> list:
    """Whole entries (C27, R13c): event, matcher, the full command, timeout and onFailure."""
    return sorted((e["event"], e.get("matcher") or "", e["command"], e.get("timeout"), e.get("on_failure") or "",
                   e.get("async_rewake") is True)  # MW-078: a missing or changed asyncRewake is drift
                  for e in entries)


def drift(root: Path, profile, errors: list, manifest: list, settings=None, profile_rel=None) -> list:
    """Drift items, each `<what>: <detail>`; an empty list means no drift."""
    root = Path(root)
    profile = profile if isinstance(profile, dict) else {}
    bundle = profiles.bundle_root(profile)
    items = []
    lock = _lock(root, bundle)
    if lock is None:
        items.append("copy: no mkway.lock")
    elif lock.get("hash") != install.copy_hash(root / bundle / "engine"):
        items.append("copy: the copy differs from the lock")
    settings = settings or root / install.SETTINGS_FILE
    owned = install.live_entries(settings, bundle)
    live = _whole(owned)
    machine = _machine_python(root, profile)
    fresh = _whole(install.generate_entries(profile, manifest, profile_rel=profile_rel, python=machine))
    if live != fresh:
        missing = len([e for e in fresh if e not in live])
        extra = len([e for e in live if e not in fresh])
        items.append(f"hook entries: {missing} missing or changed, {extra} not generated")
    # fix check 2 M2 (retro-chief10): machine.json names a Python 3.9+ that the owned entries use. Fix check 3 L5:
    # the comparison comes first, so a program named only in machine.json never runs; the probe has its own timeout
    if machine is None:
        items.append(f"drift-machine: {install.MACHINE_FILE} is missing or names no interpreter")
    elif not owned or any(install.entry_interpreter(e["command"], bundle) != machine for e in owned):  # F6
        items.append(f"drift-machine: {install.MACHINE_FILE} and the hook entries name different interpreters")
    else:
        problem = install.interpreter_problem(machine, timeout=MACHINE_CHECK_SECONDS)
        if problem == "timeout":
            items.append("drift-machine: interpreter check timed out")
        elif problem:
            items.append(f"drift-machine: {install.MACHINE_FILE} does not name an existing Python 3.9 or later")
    if errors:
        items.append("profile: invalid (" + ", ".join(e.split(":", 1)[0] for e in errors) + ")")
    return items


def _user_layer(env) -> str:
    home = (env or {}).get("USERPROFILE") or (env or {}).get("HOME")
    if not home:
        return f"user layer: {USER_LAYER} not checked, no home folder in the environment (information only)"
    path = Path(home) / ".claude" / "settings.json"
    if not path.is_file():
        return f"user layer: {USER_LAYER} missing (information only)"
    try:
        hooks = json.loads(path.read_text(encoding="utf-8")).get("hooks") or {}
        count = sum(len(g.get("hooks") or []) for groups in hooks.values() for g in groups)
    except (OSError, ValueError, AttributeError, TypeError):
        return f"user layer: {USER_LAYER} unreadable (information only)"
    return f"user layer: {USER_LAYER}, {count} hook commands (information only)"


def _error_counts(state: Path) -> str:
    counts = {"gate-error": 0, "dispatcher-error": 0}
    try:
        lines = (state / "refusals.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            reason = json.loads(line).get("reason_id")
        except (ValueError, AttributeError):
            continue
        if reason in counts:
            counts[reason] += 1
    return f"errors logged: gate-error {counts['gate-error']}, dispatcher-error {counts['dispatcher-error']}"


def _stop_crash_lines(state: Path, manifest: list) -> list:
    """MW-115 (named limit, K8): one line for each Stop-event gate that has crashed. A Stop hook cannot be wired fail-closed
    (a crashing hook cannot block, and Claude Code ends the turn after eight blocks in a row), so the dispatcher allowed
    the reply; the line says so and names the count of `gate-error` rows."""
    stop_names = {e["name"] for e in manifest if e.get("function") and e.get("event") == "Stop"}
    counts: dict = {}
    try:
        lines = (state / "refusals.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("reason_id") == "gate-error" and row.get("gate") in stop_names:
            counts[row["gate"]] = counts.get(row["gate"], 0) + 1
    return [f"Stop gate {name} failed {n} times and allowed the reply: a crashing Stop hook cannot block (Claude Code "
            f"ends the turn after eight blocks in a row); the gate-error rows in the refusal log name the error"
            for name, n in sorted(counts.items())]


def _refusal_failure_lines(state: Path, session) -> list:
    """MW-128 (R301a 2): one line for this session when the Stop hook could not write a refusal of its into the orderer's inbox
    (a Stop hook cannot fail closed, so the stop was allowed). The line names the count, the latest error and the way out; it
    ends when the gate refusal row is delivered. Never raises."""
    try:
        failed = gatemode.delivery_failures(state, session) if isinstance(session, str) and session else []
    except Exception:
        return []
    if not failed:
        return []
    last = failed[-1]
    return [f"refusal-delivery-failed: {len(failed)} refusal(s) of this session could not be written to its orderer's inbox "
            f"(latest: gate refusal row {last.get('refusal') or 'not established'}, {last.get('error') or 'not established'}); "
            f"the stop was allowed. Tell your orderer yourself: `mkway send` the exact command and the refusal line "
            f"(the row is in gate_calls.jsonl)"]


def _handoff_failure_lines(state: Path, session) -> list:
    """MW-132 (R338 6): one line for this session when the Stop hook could not write its last message into the orderer's inbox (a
    Stop hook cannot fail closed, so the stop was allowed). The line names the count, the latest error and the way out; a written
    notice ends it. Never raises."""
    try:
        failed = gatemode.handoff_failures(state, session) if isinstance(session, str) and session else []
    except Exception:
        return []
    if not failed:
        return []
    last = failed[-1]
    return [f"handoff-notice-failed: {len(failed)} turn end(s) of this session could not be written to its orderer's inbox "
            f"(latest: {last.get('error') or 'not established'} at {last.get('time') or 'not established'}); the stop was allowed. "
            f"Tell your orderer yourself: `mkway send` your question, your result, or what you wait for "
            f"(the row is in gate_calls.jsonl)"]


def _locks_line(root: Path, profile, bundle: str) -> str:
    """The count of lock files, then each open lock with its end time (lock_notice joins the start line, MW-003)."""
    import locks
    folder = root / bundle / "locks"
    count = sum(1 for x in folder.iterdir() if x.is_file()) if folder.is_dir() else 0
    try:  # MW-022: the markers live in the shared state folder; the older folder is counted too
        shared = locks.lock_folder(root, profile)
        if shared.is_dir() and not locks._same(shared, folder):
            count += sum(1 for x in shared.iterdir() if x.is_file())
    except (OSError, ValueError):
        pass
    line = f"locks: {count} files in {bundle}/locks"
    try:
        opened = locks.open_locks(root, profile)
    except (OSError, ValueError):
        opened = []
    if opened:
        line += "; " + ", ".join(f"{name} open until {until}" for name, until in opened)
    try:
        held = [h for h in locks.hold_lines(root, profile) if "closed" in h]
    except (OSError, ValueError):
        held = []
    if held:
        line += "; " + ", ".join(held)
    return line


REFUSAL_RULE = "a refusal is reported, never worked around"  # R15 A9
ROLE_BUDGET = (("lead", 40), ("builder", 30), ("operator", 30))  # MW-112 (R284): lines per role file the engine ships; engine constants, no profile key
ROLE_DIR = Path(__file__).resolve().parent / "roles"


def _role_lines(root: Path) -> list:
    """MW-112: one line per shipped role file, `role file: <path>, N/<budget> lines`; it only shows the number and never stops
    the block (a file that can not be read says so)."""
    out = []
    for name, budget in ROLE_BUDGET:
        path = ROLE_DIR / f"{name}.md"
        try:
            shown = path.relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            shown = path.as_posix()
        try:
            count = sum(1 for x in path.read_text(encoding="utf-8").splitlines() if x.strip())
        except OSError:
            out.append(f"role file: {shown}, not established (the file can not be read)")
            continue
        out.append(f"role file: {shown}, {count}/{budget} lines")
    return out
SIGNAL_MISSING = "session-signal-missing"
CHANGES = "card changes since the owner's last re-seal"


def _changes(root: Path, p):
    """(status, changes) where changes lists (id, was, now, why) since the baseline the owner's re-seal wrote
    (`register.BASELINE`; M1: a start or a compaction never moves it), or None when there is no baseline yet.
    Raises RegisterError when the seal fails, OSError when the register cannot be read."""
    import records
    import register
    register.check(root, p)
    status = {r["id"]: r.get("status", "") for r in register.read(root, p)}
    base = register.read_baseline(root, p)
    if base is None:
        return status, None
    before, since = base["status"], base["time"]
    recs = [r for r in records.rows(profiles.state_dir(root, p)) if str(r.get("time", "")) >= since]
    changes = []
    for card_id, now in status.items():
        was = before.get(card_id)
        if was == now:
            continue
        match = [r for r in recs if _record_sets(r, card_id, now)]
        why = f"{match[-1]['kind']} by {match[-1].get('by', 'session')}" if match else "no record"
        changes.append((card_id, was or "new", now, why))
    return status, changes


def _change_text(c) -> str:
    return f"{c[0]} {c[1]} -> {c[2]} ({c[3]})"


def owner_notice(root: Path, p):
    """M1 (R54, R60): the line the owner sees (`systemMessage`): the changes with no record and the moves into a
    status only the owner may set, since the owner's last re-seal; None when there are none."""
    import cardtool
    try:
        _status, changes = _changes(root, p)
    except Exception:  # the start line itself reports a broken register; the notice adds nothing then
        return None
    moves = set(cardtool.owner_moves(p))
    shown = [c for c in changes or [] if c[3] == "no record" or c[2] in moves]
    if not shown:
        return None
    return (f"mkway: {CHANGES}: " + "; ".join(_change_text(c) for c in shown)
            + ". Check them; `card resync` in your own terminal accepts them")


def _card_lines(root: Path, p, session) -> list:
    """The cards line (R15 A10) and the status changes since the owner's last re-seal with the record behind each
    (R19a's decided limit: a hand-edited and resealed status does not pass unseen)."""
    import records
    import register
    state = profiles.state_dir(root, p)
    try:
        status, changes = _changes(root, p)
    except register.RegisterError:
        return [f"cards: register-tampered ({register.seal_problem(root, p)}); {register.OWNER_FIX}"]
    except OSError:
        return ["cards: the register cannot be read"]
    mine = records.session_card(state, session, {i for i, s in status.items() if s == "closed"})
    held = f"this session holds {mine} ({status.get(mine, 'not in the register')})" if mine else \
        "this session holds no card"
    live = [f"{i} {s}" for i, s in status.items() if s != "closed"]
    lines = [f"cards: {held}; not closed: {', '.join(live) or 'none'}"]
    if changes is None:
        lines.append(f"{CHANGES}: not established (no baseline yet; the owner's `card resync` sets it)")
    else:
        lines.append(f"{CHANGES}: " + ("; ".join(_change_text(c) for c in changes) or "none"))
    return lines


def _staged_lines(root: Path, p, session) -> list:
    """MW-043: `staged outside your card: N` when this session holds an open card and N > 0 files are staged outside
    its Paths. A line only, never a refusal; a read that fails adds no line: the start block never fails here."""
    import gate_commit
    import records
    import register
    if p.get("vcs") != "git":
        return []
    try:
        state = profiles.state_dir(root, p)
        rows = register.read(root, p)
        mine = records.session_card(state, session, {r["id"] for r in rows if r.get("status") == "closed"})
        row = register.find(rows, mine) if mine else None
        if not row or row.get("status") != "open":
            return []
        found = gate_commit.staged_outside(root, p, row)
    except Exception:
        return []
    return [f"staged outside your card: {len(found)}"] if found else []


def _agent_lines(root: Path, p, session) -> list:
    """MW-004: one line for each agent of this session that ran over `agents.cap_minutes` or has a start row with no
    end row (`<state.dir>/agents.jsonl`). A file that cannot be read adds no line: the start block never fails here."""
    import agents
    try:
        return agents.report(profiles.state_dir(root, p), session, agents.cap_minutes(p))
    except Exception:
        return []


def _ledger_lines(root: Path, p) -> list:
    """MW-008: `ledger: N rows, M in force` when the ledger file exists, else no line. A file that cannot be read adds
    no line: the start block never fails here."""
    import ledger
    try:
        found = ledger.counts(root, p)
    except Exception:
        return []
    return [] if found is None else [f"ledger: {found[0]} rows, {found[1]} in force"]


def _outbox_lines(root: Path, p) -> list:
    """MW-019: `outbox: N files, M unchecked` when `outbox.dir` is set, else no line. A folder that cannot be read adds no
    line: the start block never fails here."""
    import outbox
    try:
        line = outbox.start_line(root, p)
    except Exception:
        return []
    return [] if line is None else [line]


def _deliverable_lines(root: Path, p) -> list:
    """MW-020: `deliverables: N built, M changed since built, K delivered` when `deliverables.paths` is set, else no
    line. A folder that cannot be read adds no line: the start block never fails here."""
    import deliverables
    try:
        line = deliverables.start_line(root, p)
    except Exception:
        return []
    return [] if line is None else [line]


def _ask_lines(root: Path, p) -> list:
    """MW-014: `open asks: N (oldest <age>); past deadline: M; defaults taken since the owner's last re-seal: K`. A
    folder that cannot be read adds no line: the start block never fails here."""
    import asks
    try:
        return [asks.start_line(root, p)]
    except Exception:
        return []


def _lead_lines(root: Path, p, session) -> list:
    """MW-017: a lead's own unacked notices; for any other session the notices unacked past `leads.escalate_hours`.
    The start block never fails here."""
    import leads
    try:
        return leads.start_lines(root, p, session)
    except Exception:
        return []


def _inbox_lines(root: Path, p, session) -> list:
    """MW-018: the unacked inbox items of a session that is no lead (a lead's lines are MW-017's). The start block never
    fails here."""
    import messages
    try:
        return messages.start_lines(profiles.shared_state_dir(root, p), session)
    except Exception:
        return []


def _rules_lines(root: Path, p) -> list:
    """MW-021: `rules: N cards, M without tests` when `rules.cards` and `rules.test_for` are set, else no line. A
    folder that cannot be read adds no line: the start block never fails here."""
    import rules
    try:
        line = rules.start_line(root, p)
    except Exception:
        return []
    return [line] if line else []


def _record_sets(row, card_id: str, status: str) -> bool:
    kind, value = row.get("kind"), row.get("value")
    if kind == "set":
        return value == f"{card_id} {status}"
    return value == card_id and {"open": "open", "close": "closed", "new": "proposed"}.get(kind) == status


def _signal_line(root: Path, p, env, session):
    """R23 (C44 is a second layer only): inside a hook a missing `CLAUDECODE` is warned and logged once per start;
    the shell gate's text check stays the guard."""
    import logs
    import records
    if env is None or records.SESSION_ENV in env:
        return None
    try:
        logs.write_refusal(profiles.state_dir(root, p), logs.row(
            session=session, event="SessionStart", tool=None, gate="start", reason_id=SIGNAL_MISSING, target=None,
            kind="warn"))
    except OSError:
        pass
    return (f"warning {SIGNAL_MISSING}: {records.SESSION_ENV} is not set inside this hook, so the cards tool "
            f"cannot tell a session's command from the owner's; the lock gate's command check still refuses a "
            f"session's owner-only command")


def _why_vcs_none(root: Path) -> str:
    """MW-028: one clause for the vcs line when the profile says none: the profile's word against what git says about
    the root. Never raises."""
    try:
        if install.detect_vcs(root) == "git":
            return ("the root is inside a git work tree, yet the profile says none: set \"vcs\": \"git\" in the "
                    "profile, then run `mkway install`")
    except Exception:
        return "the profile says none; git could not be asked"
    return "the profile says none and the root is in no git work tree"


def render(root: Path, profile_file: Path, profile, errors: list, manifest: list, env=None, session=None) -> str:
    root = Path(root)
    valid = isinstance(profile, dict) and not errors
    p = profile if isinstance(profile, dict) else {}
    bundle = profiles.bundle_root(p)
    lock = _lock(root, bundle)
    try:
        shown = Path(profile_file).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        shown = Path(profile_file).as_posix()
    # MW-107 (R274 5.8, R274a 11): the root of the session, the install root whether or not it is a git repository
    lines = [f"mkway {_version_text(root, bundle, lock)}; profile: {shown}",
             f"root: {helpers.real_root(root)}; every path you write starts here"]
    state = profiles.state_dir(root, p)
    try:  # MW-012: a form gate in watch is marked; the block never fails here
        watched = gatemode.watching_gates(state, manifest)
    except Exception:
        watched = []
    on = [e["name"] + (" (watch)" if e.get("gate", e["name"]) in watched else "")
          for e in manifest if valid and not e.get("waiter") and install._loadable_on(p, e)]  # MW-078: the waiter is no gate
    not_loaded = [e["name"] for e in manifest if e.get("function") and not e.get("reason_ids")]
    planned = sum(1 for e in manifest if not e.get("function") and not e.get("waiter"))
    lines.append(f"gates on: {', '.join(on) or 'none'}; not loaded: "
                 + (", ".join(f"{n} (no reason_ids)" for n in not_loaded) or "none")
                 + f"; {planned} manifest entries without code yet")
    # MW-007: the block names the gates that are off too, not only the ones that are on (a rule agreed on 2026-10-29).
    # An entry with code and reason ids that does not run is off: a profile switch, a manifest default, a nested
    # mode, or an invalid profile (no gate runs). An entry with no code is only counted above.
    off = [e["name"] for e in manifest
           if e.get("function") and e.get("reason_ids") and not (valid and install._loadable_on(p, e))]
    lines.append(f"gates off: {', '.join(off) or 'none'}")
    for gate in watched:  # MW-012, rule 7: one line per form gate in watch, every session until the owner's `gate on`
        try:
            lines.append(gatemode.watch_line(root, state, manifest, gate, profile=p))
        except Exception:
            lines.append(f"gate {gate}: WATCH (the counts could not be read)")
    try:  # MW-115: a marker of an install from before the gate became integrity: named once, then removed
        for gate in gatemode.stale_markers(state, manifest):
            lines.append(gatemode.stale_line(gate))
            gatemode.remove_marker(state, gate)
    except Exception:
        pass
    if p.get("vcs") == "git":
        lines.append("vcs: git")
    elif p.get("vcs") == "none":
        lines.append("vcs: none, every git step is off (" + _why_vcs_none(root) + ")")
    else:
        lines.append("vcs: not established (the profile does not say)")
    if errors:
        lines.append("profile-invalid: " + "; ".join(errors[:5]) + ". No gate runs and every edit and shell call is "
                     "refused until the owner fixes the profile in their own editor (C52)")
    bad_watch = profiles.session_id_watch_unreadable(p)  # MW-110, R279c Q2: one extra line, only when it cannot be read
    if bad_watch:
        lines.append(f"messaging.session_id_watch_until is {bad_watch!r}, not a date (YYYY-MM-DD): it counts as passed, so a "
                     f"session with no verified id is refused; the owner sets a date or empties it")
    rel = None  # the same `--profile` part the install wrote (content check F2)
    if Path(profile_file).resolve() != paths.profile_path(root).resolve():
        try:
            rel = Path(profile_file).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = None
    items = drift(root, p, errors, manifest, profile_rel=rel)
    lines.append("drift: none" if not items else "drift: " + "; ".join(items) + ". Fix: mkway install")
    lines.append(_locks_line(root, p, bundle))
    lines.extend(_card_lines(root, p, session))
    lines.extend(_staged_lines(root, p, session))
    lines.extend(_agent_lines(root, p, session))
    lines.extend(_ledger_lines(root, p))
    lines.extend(_ask_lines(root, p))
    lines.extend(_outbox_lines(root, p))
    lines.extend(_deliverable_lines(root, p))
    lines.extend(_lead_lines(root, p, session))
    lines.extend(_inbox_lines(root, p, session))
    lines.extend(_rules_lines(root, p))
    lines.append(REFUSAL_RULE)
    lines.extend(_role_lines(root))
    signal = _signal_line(root, p, env, session)
    if signal:
        lines.append(signal)
    lines.append(_error_counts(profiles.state_dir(root, p)))
    try:  # MW-112: the failed agent record stays on the start line until a row is written again (R271c)
        import board
        lines.extend(board.failed_agent_lines(profiles.state_dir(root, p)))
        import scorecard
        unread = scorecard.unread_state_writes(root, profiles.state_dir(root, p))  # R279d (a)
        if unread:
            lines.append(f"unreadable writes that passed and named the state folder: {unread} (logged, not blocked; "
                         f"`mkway scorecard` counts them)")
    except Exception:
        pass
    lines.extend(_stop_crash_lines(profiles.state_dir(root, p), manifest))  # MW-115, the named limit of K8
    lines.extend(_refusal_failure_lines(profiles.state_dir(root, p), session))  # MW-128, R301a 2
    lines.extend(_handoff_failure_lines(profiles.state_dir(root, p), session))  # MW-132, R338 6
    unresolved = _unresolved_count(profiles.state_dir(root, p))
    if unresolved:
        lines.append(f"write-target-unresolved: {unresolved} shell commands in the log wrote to targets the lock gate "
                     f"could not read (logged, not blocked; R43)")
    lines.append(_user_layer(env))
    return "\n".join(lines)


def _unresolved_count(state: Path) -> int:
    """The `write-target-unresolved` rows of the refusal log (list item 5, R43 (c)); 0 when it cannot be read."""
    import logs
    try:
        text = (Path(state) / logs.REFUSALS).read_text(encoding="utf-8")
    except OSError:
        return 0
    count = 0
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        count += isinstance(row, dict) and row.get("reason_id") == "write-target-unresolved" and \
            row.get("kind") == "log" and not row.get("note")  # a row with a note is the upgrade guard's own (MW-105)
    return count
