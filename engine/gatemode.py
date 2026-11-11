"""Gate modes: class, calls log, watch marker and trip (card MW-012).

Every manifest entry has a `class`: `integrity` or `form`; no class reads `integrity`. An integrity gate never degrades
and never reads a marker. A form gate has two modes: enforcing (the default) and watch. In watch the gate still runs,
the dispatcher turns its refusal into a `would-refuse` log row (same reason id and text) and allows.

`<state.dir>/gate_calls.jsonl`: one short row per gate per call (time, gate, verdict: allow, refuse, log, error), written
by the dispatcher. `<state.dir>/gate_mode/<gate>.watch`: the watch marker, a JSON object (gate, cause: installed,
tripped or owner; time; calls and refused over the last 24 hours at that time). A marker is written by the trip, by a
first install, and by the owner's `mkway gate watch`; only the owner's `mkway gate on` removes it. There is no
automatic return to blocking.

The trip: after a refusal by a form gate that is enforcing, the gate's rows of the last 24 hours are counted; with at
least `gates.trip.min_calls` calls (default 20) and a refusal share above `gates.trip.share` (default 0.34) the
marker is written with cause `tripped`. The call that tripped it stays refused; watch starts with the next call. An
`error` row is neither a call nor a refusal here.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Optional

import logs

CALLS = "gate_calls.jsonl"
MODE_DIR = "gate_mode"
SUFFIX = ".watch"
INTEGRITY, FORM = "integrity", "form"
CAUSES = ("installed", "tripped", "owner")
WINDOW = datetime.timedelta(hours=24)
DEFAULT_MIN_CALLS = 20  # `gates.trip.min_calls`
DEFAULT_SHARE = 0.34    # `gates.trip.share`
COUNTED = ("allow", "refuse", "log")  # an `error` row is no call and no refusal
WOULD_REFUSE = "would-refuse"
TRANSITIONS = {"tripped": "gate-tripped", "owner": "gate-watch", "installed": "gate-watch-installed"}
ON_ROW = "gate-on"


def entry_class(entry) -> str:
    """`form` only when the entry says so; a missing or unknown class is `integrity` (it never degrades)."""
    return FORM if isinstance(entry, dict) and entry.get("class") == FORM else INTEGRITY


def gate_class(entries, gate: str) -> str:
    """`form` when the gate (a profile switch name) has code and every entry of it is form; else `integrity`."""
    mine = [e for e in entries if e.get("function") and e.get("gate", e.get("name")) == gate]
    return FORM if mine and all(entry_class(e) == FORM for e in mine) else INTEGRITY


def trip_settings(profile) -> tuple:
    """(min_calls, share) from `gates.trip`; an unusable value takes its default, so a gate never fails on a bad key."""
    gates = profile.get("gates") if isinstance(profile, dict) else None
    raw = gates.get("trip") if isinstance(gates, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    calls, share = raw.get("min_calls"), raw.get("share")
    if isinstance(calls, bool) or not isinstance(calls, int) or calls < 1:
        calls = DEFAULT_MIN_CALLS
    if isinstance(share, bool) or not isinstance(share, (int, float)) or not share > 0:
        share = DEFAULT_SHARE
    return calls, share


# ---- the calls log ----------------------------------------------------------------------------------------------

def calls_path(state: Path) -> Path:
    return Path(state) / CALLS


def append_call(state: Path, gate: str, verdict: str) -> None:
    logs.append_jsonl(calls_path(state), {"time": logs.now().isoformat(timespec="milliseconds"), "gate": gate,
                                          "verdict": verdict})


def _when(text) -> Optional[datetime.datetime]:
    try:
        when = datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def counts(state: Path, gate: str, now=None) -> tuple:
    """(calls, refused) of this gate over the last 24 hours; `error` rows count as neither."""
    since = (now or logs.now()) - WINDOW
    calls = refused = 0
    try:
        text = calls_path(state).read_text(encoding="utf-8")
    except OSError:
        return 0, 0
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("gate") != gate or row.get("verdict") not in COUNTED:
            continue
        when = _when(row.get("time"))
        if when is None or when < since:
            continue
        calls += 1
        refused += row["verdict"] == "refuse"
    return calls, refused


# ---- the watch marker -------------------------------------------------------------------------------------------

def marker_path(state: Path, gate: str) -> Path:
    return Path(state) / MODE_DIR / f"{gate}{SUFFIX}"


def is_watching(state: Path, gate: str) -> bool:
    return marker_path(state, gate).is_file()


def read_marker(state: Path, gate: str) -> Optional[dict]:
    """The marker's JSON object, `{}` when the file is there but unreadable, None when there is no marker."""
    path = marker_path(state, gate)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_marker(state: Path, gate: str, cause: str, calls: int = 0, refused: int = 0) -> dict:
    """Write (or replace) the marker; a temp file, then replace: never a half-written marker."""
    data = {"gate": gate, "cause": cause, "time": logs.now().isoformat(timespec="milliseconds"), "calls": calls,
            "refused": refused}
    path = marker_path(state, gate)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return data


def remove_marker(state: Path, gate: str) -> bool:
    """True when a marker was there and is gone."""
    try:
        marker_path(state, gate).unlink()
    except FileNotFoundError:
        return False
    return True


def transition_row(gate: str, reason_id: str, *, cause=None, session=None, event="command", **extra) -> dict:
    """The log row of a mode change (trip, owner watch, owner on, install); it has a time like every row."""
    return logs.row(session=session, event=event, tool=None, gate=gate, reason_id=reason_id, target=None, kind="log",
                    cause=cause, **extra)


# ---- the start block --------------------------------------------------------------------------------------------

def watching_gates(state: Path, manifest) -> list:
    """The form gates (profile switch names, sorted) that have a marker. An integrity gate is never listed."""
    names = sorted({e.get("gate", e.get("name")) for e in manifest if e.get("function")})
    return [g for g in names if gate_class(manifest, g) == FORM and is_watching(state, g)]


def _would_refuse_today(state: Path, entry_names: set) -> int:
    today = logs.now().date()
    count = 0
    try:
        text = (Path(state) / logs.REFUSALS).read_text(encoding="utf-8")
    except OSError:
        return 0
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("kind") == WOULD_REFUSE and row.get("gate") in entry_names:
            when = _when(row.get("time"))
            count += when is not None and when.astimezone(datetime.timezone.utc).date() == today
    return count


def watch_line(root: Path, state: Path, manifest, gate: str) -> str:
    """The start block's line for one form gate in watch."""
    marker = read_marker(state, gate) or {}
    calls, refused = counts(state, gate)
    names = {e["name"] for e in manifest if e.get("gate", e.get("name")) == gate}
    try:
        log = (Path(state) / logs.REFUSALS).relative_to(root).as_posix()
    except ValueError:
        log = (Path(state) / logs.REFUSALS).as_posix()
    return (f"gate {gate}: WATCH since {marker.get('time') or 'not established'} "
            f"({marker.get('cause') or 'not established'}; {refused} of {calls} in 24 h); "
            f"would-refuse today: {_would_refuse_today(state, names)}; log: {log}")


# ---- the trip ---------------------------------------------------------------------------------------------------

def trip(state: Path, profile, gate: str) -> Optional[dict]:
    """Count the gate's last 24 hours; when the trip rule holds, write the marker (cause `tripped`) and return
    `{"calls": n, "refused": r}`, else None."""
    calls, refused = counts(state, gate)
    min_calls, share = trip_settings(profile)
    if calls < min_calls or not refused / calls > share:
        return None
    write_marker(state, gate, "tripped", calls, refused)
    return {"calls": calls, "refused": refused}
