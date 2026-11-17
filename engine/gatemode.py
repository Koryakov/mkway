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
import secrets
from pathlib import Path
from typing import Optional

import logs

CALLS = "gate_calls.jsonl"
DELIVERED_FILE = "refusal-delivered.jsonl"  # MW-128: the gate refusal row ids the Stop hook has delivered (or found no orderer for)
CALL_EVENTS = ("PreToolUse", "PostToolUse")  # the events whose rows are engine calls (a tool call the gates judged)
TAIL_BYTES = 1 << 20  # MW-128: only the end of a log is read; the last call of a turn is always near it
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
WATCH_DAYS = 7  # MW-112 (R284a): the length of a trial when the owner gives no date; an engine constant, `--until` is the one lever


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


def append_call(state: Path, gate: str, verdict: str, duration_ms=None, **extra) -> None:
    """One row per gate per call. MW-112 (record R4): `duration_ms` is the time the gate took, when the caller measured it.
    MW-128: `extra` names the call (`session`, `event`, `tool`, `call`: one id for the rows of one hook call) and, on a refuse
    row, the command head or path (`target`, the refusal log's rule: cut to 200 characters, newlines as `\\n`, MW-061), the
    refusal line (`message`) and the reason id; a refuse row gets its own id (`gc-...`, the «gate refusal row id» of R301a).
    `watching` is true only on a refuse row written while the gate's watch marker was present (MW128-D1, rule c). A value that
    is None is left out."""
    moment = logs.now()
    row = {"time": moment.isoformat(timespec="milliseconds"), "gate": gate, "verdict": verdict}
    if duration_ms is not None:
        row["duration_ms"] = duration_ms
    if verdict == "refuse":
        row["id"] = f"gc-{moment.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    row.update({k: v for k, v in extra.items() if v is not None})
    logs.append_jsonl(calls_path(state), row)

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


# ---- the turn of a session (MW-128: the refusal delivery of the Stop hook) ---------------------------------------------

def _tail_rows(path: Path) -> list:
    """The JSON object rows in the last TAIL_BYTES of a log, oldest first; a missing or unreadable file reads as empty."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            start = max(0, fh.tell() - TAIL_BYTES)
            fh.seek(start)
            data = fh.read()
    except OSError:
        return []
    lines = data.decode("utf-8", errors="replace").splitlines()
    rows = []
    for line in lines[1:] if start else lines:  # after a cut, the first line may be a part of a row
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _is_boundary(row: dict, session: str) -> bool:
    """A timing row that starts a turn of this session: its UserPromptSubmit run, or its previous Stop run of the `stop` group."""
    return row.get("session") == session and (row.get("event") == "UserPromptSubmit" or (
        row.get("event") == "Stop" and row.get("group") == "stop"))


def turn_start(state: Path, session: str) -> Optional[str]:
    """MW-128, the order's «turn»: the time of the latest boundary row of this session in the engine's timing log
    (`timing-YYYY-MM-DD.jsonl`, one row per dispatcher run: today's file and yesterday's), None when there is none. The boundary
    rows are the UserPromptSubmit run and the previous Stop run of the `stop` group."""
    today = logs.now().date()
    best = None
    for day in (today - datetime.timedelta(days=1), today):
        for row in _tail_rows(Path(state) / f"timing-{day.isoformat()}.jsonl"):
            when = _when(row.get("time"))
            if when is not None and _is_boundary(row, session) and (best is None or when >= best[0]):
                best = (when, row["time"])
    return best[1] if best else None


def turn_calls(state: Path, session: str) -> list:
    """MW-128: the engine calls of this session in the turn, oldest first: the PreToolUse and PostToolUse rows of the calls log
    at or after the turn's start, one entry per hook call (`call`): `{call, time (of its last row), refused, id, target,
    message}`. `refused` is true when a row of the call is a gate refusal row: the verdict refuse of a gate that blocked (a
    row of a gate in watch mode is a would-refuse, and an error row is neither); `id` is that row's id."""
    since = _when(turn_start(state, session))
    found: dict = {}
    for row in _tail_rows(calls_path(state)):
        when = _when(row.get("time"))
        if row.get("session") != session or row.get("event") not in CALL_EVENTS or not row.get("call") or when is None:
            continue
        if since is not None and when < since:
            continue
        entry = found.setdefault(row["call"], {"call": row["call"], "refused": False, "id": None, "target": None,
                                               "message": None})
        entry["time"] = row["time"]
        if row.get("verdict") == "refuse" and not row.get("watching") and row.get("id"):
            entry.update(refused=True, id=row["id"], target=row.get("target"), message=row.get("message"))
    return sorted(found.values(), key=lambda c: _when(c["time"]))


def delivered_ids(state: Path) -> set:
    """MW-128: the gate refusal row ids the Stop hook has dealt with (a record written, or no orderer to write to)."""
    return {row["id"] for row in _tail_rows(Path(state) / DELIVERED_FILE) if isinstance(row.get("id"), str)}


def mark_delivered(state: Path, refusal_id: str, session: str, outcome: str, inbox_id=None) -> None:
    """MW-128: record that this gate refusal row id is dealt with; `outcome` is `delivered` (with the inbox row id) or
    `no-orderer`. The next Stop on the same id never writes or blocks again."""
    row = {"id": refusal_id, "session": session, "outcome": outcome, "time": logs.now().isoformat(timespec="milliseconds")}
    if inbox_id:
        row["inbox_id"] = inbox_id
    logs.append_jsonl(Path(state) / DELIVERED_FILE, row)


def retry_candidate(state: Path, session: str) -> Optional[dict]:
    """MW-128 (R301a 2: «the next stop retries once; never a loop»): the gate refusal row of this session whose delivery failed
    exactly once and is still not delivered, as `{call, time, refused, id, target, message}`; None when there is none. A Stop
    after a failed write opens a later turn, so the refusal is no longer in it: the error row is how it is found again. A
    refusal with two failed deliveries is not tried a third time. The latest such refusal wins."""
    done = delivered_ids(state)
    rows = _tail_rows(calls_path(state))
    failed: dict = {}
    for row in rows:
        if row.get("reason_id") == "refusal-delivery-failed" and row.get("session") == session and row.get("refusal"):
            failed[row["refusal"]] = failed.get(row["refusal"], 0) + 1
    for refusal_id in reversed(list(failed)):
        if failed[refusal_id] != 1 or refusal_id in done:
            continue
        for row in rows:
            if row.get("id") == refusal_id and row.get("verdict") == "refuse" and row.get("session") == session:
                return {"call": row.get("call") or refusal_id, "time": row["time"], "refused": True, "id": refusal_id,
                        "target": row.get("target"), "message": row.get("message")}
    return None


# ---- the turn of the handoff notice (MW-132) ----------------------------------------------------------------------------

HANDOFF_MARK_REASONS = ("handoff-notice", "handoff-no-orderer", "refusal-delivered", "refusal-no-orderer")  # record rows of the refusal log
HANDOFF_ERROR_REASONS = ("handoff-notice-failed", "refusal-delivery-failed")  # error rows of the calls log


def _delivery_marks(state: Path, session: str) -> list:
    """The times of the rows this session's Stop runs left that deliver a turn: the record rows of the notice, of the no-orderer case
    and of MW-128's delivery (refusal log), and the error rows of those two steps (calls log: one try per turn, never a loop)."""
    marks = []
    for row in _tail_rows(Path(state) / logs.REFUSALS):
        when = _when(row.get("time"))
        if when is not None and row.get("session") == session and row.get("event") == "Stop" \
                and row.get("reason_id") in HANDOFF_MARK_REASONS:
            marks.append(when)
    for row in _tail_rows(calls_path(state)):
        when = _when(row.get("time"))
        if when is not None and row.get("session") == session and row.get("event") == "Stop" \
                and row.get("verdict") == "error" and row.get("reason_id") in HANDOFF_ERROR_REASONS:
            marks.append(when)
    return marks


def _session_rows(state: Path, session: str) -> list:
    """Every timing row of this session (today's file and yesterday's), oldest first, as `(time, time text, is a Stop row of the
    `stop` group, its `stop_hook_active` flag, is a prompt row)`. A Stop row keeps the flag of its hook input; a row with no flag
    (written before MW-132) reads as false. A prompt row, a tool run and a start are rows too, and none of them opens a turn."""
    today = logs.now().date()
    found = []
    for day in (today - datetime.timedelta(days=1), today):
        for row in _tail_rows(Path(state) / f"timing-{day.isoformat()}.jsonl"):
            when = _when(row.get("time"))
            if when is not None and row.get("session") == session:
                found.append((when, row["time"], row.get("event") == "Stop" and row.get("group") == "stop",
                              row.get("stop_hook_active") is True, row.get("event") == "UserPromptSubmit"))
    return sorted(found, key=lambda item: item[0])


def _blocked_stops(state: Path, session: str) -> list:
    """The times of the record rows `handoff-notice` of this session with `blocked` true: each is a Stop this step blocked."""
    return [when for row in _tail_rows(Path(state) / logs.REFUSALS)
            for when in [_when(row.get("time"))]
            if when is not None and row.get("session") == session and row.get("reason_id") == "handoff-notice"
            and row.get("event") == "Stop" and row.get("blocked") is True]


def _blocked_flags(stops: list, blocked: list) -> list:
    """For each Stop row of the session, in order: true when this step blocked that stop. The record row of a block is written
    during the run, before the run's timing row, so it lies after the previous Stop row and not after this one."""
    return [any((i == 0 or m > stops[i - 1][0]) and m <= stop[0] for m in blocked) for i, stop in enumerate(stops)]


def handoff_turn(state: Path, session: str, hook_active: bool = False) -> Optional[str]:
    """MW-132 (R340a), the turn of the handoff notice: the time text of this session's boundary row, None when the engine holds
    no row of the session at all, or holds no prompt row of it (the engine saw no turn begin: nothing is judged; MW-128's rows rely
    on it). Only the Stop rows of the `stop` group open and close turns; a prompt row never does (a peer
    message that arrives mid-turn writes one). A stop with `stop_hook_active` true continues the turn of the stop before it (the task
    has two Stop hooks and this step cannot know which one blocked), so the current chain of continued stops is the current stop
    and the stops before it while their flag is true, back to the first stop of the chain. A stop also continues the turn of the
    stop before it when this step BLOCKED that stop (R342): a blocked stop cannot end a turn, because the flag may be false at the
    stop after the block and the ping, and the rule would loop. The boundary is the Stop row just before that first stop; with no
    such row it is the session's first row."""
    rows = _session_rows(state, session)
    if not any(r[4] for r in rows):
        return None
    stops = [r for r in rows if r[2]]
    blocked = _blocked_flags(stops, _blocked_stops(state, session))
    start = len(stops)
    flag = hook_active or (start > 0 and blocked[start - 1])
    while flag and start > 0:
        start -= 1
        flag = stops[start][3] or (start > 0 and blocked[start - 1])
    return stops[start - 1][1] if start >= 1 else rows[0][1]


def turn_delivered(state: Path, session: str, turn_start) -> bool:
    """MW-132 (R1-12): true when a delivery mark of this session is later than the turn's boundary: the record row of a notice
    (it also records whether it blocked), of a no-orderer case, of MW-128's delivery, or an error row of either step (one try per
    turn, never a loop). The turn is keyed by the boundary row's time, which is unique for a session: a timing row is written at the
    end of each run, after the marks of that run."""
    since = _when(turn_start)
    if since is None:
        return False
    return any(m > since for m in _delivery_marks(state, session))


def handoff_failures(state: Path, session: str) -> list:
    """MW-132: the calls-log error rows of failed handoff notices of this session (reason `handoff-notice-failed`) later than its
    latest written notice; each is `{error, time}`. The start line names them; a written notice ends the list."""
    last = None
    for row in _tail_rows(Path(state) / logs.REFUSALS):
        when = _when(row.get("time"))
        if when is not None and row.get("session") == session and row.get("reason_id") == "handoff-notice":
            last = when if last is None or when > last else last
    out = []
    for row in _tail_rows(calls_path(state)):
        when = _when(row.get("time"))
        if when is not None and row.get("session") == session and row.get("reason_id") == "handoff-notice-failed" \
                and (last is None or when > last):
            out.append({"error": row.get("error"), "time": row.get("time")})
    return out


def delivery_failures(state: Path, session: str) -> list:
    """MW-128: the calls-log error rows of failed deliveries of this session (reason id `refusal-delivery-failed`) whose gate
    refusal row is still not delivered; each is `{refusal, error, time}`."""
    done = delivered_ids(state)
    return [{"refusal": row.get("refusal"), "error": row.get("error"), "time": row.get("time")}
            for row in _tail_rows(calls_path(state))
            if row.get("reason_id") == "refusal-delivery-failed" and row.get("session") == session
            and row.get("refusal") not in done]


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


def stale_markers(state: Path, manifest) -> list:
    """The gates (profile switch names, sorted) that are integrity today and still have a watch marker: markers of an
    install from before the gate became integrity (MW-115). The dispatcher never reads such a marker, so the gate refuses
    at once; the start line names the change once, then the marker is removed."""
    names = sorted({e.get("gate", e.get("name")) for e in manifest if e.get("function")})
    return [g for g in names if gate_class(manifest, g) == INTEGRITY and is_watching(state, g)]


def stale_line(gate: str) -> str:
    """The start block's line for one stale marker (it starts with `changed:`, not with `gate `)."""
    return (f"changed: gate {gate} was in watch and now refuses from the first call (class integrity); "
            f"its old watch marker is removed")


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


def _would_refuse_total(state: Path, entry_names: set) -> int:
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
        count += isinstance(row, dict) and row.get("kind") == WOULD_REFUSE and row.get("gate") in entry_names
    return count


def watch_until(profile, gate: str):
    """MW-112: `gates.<gate>.watch_until` as written, None when the key is absent."""
    gates = profile.get("gates") if isinstance(profile, dict) else None
    entry = gates.get(gate) if isinstance(gates, dict) else None
    return entry.get("watch_until") if isinstance(entry, dict) and "watch_until" in entry else None


def until_date(raw) -> Optional[datetime.date]:
    """The end date as a date, None when the value is no `YYYY-MM-DD` text."""
    if not isinstance(raw, str):
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


def watch_ended(raw, today) -> bool:
    """A watch has ended after its date; a value that is no date counts as ended (fail closed, as R279c)."""
    due = until_date(raw)
    return due is None or today > due


def watch_line(root: Path, state: Path, manifest, gate: str, profile=None, today=None) -> str:
    """The start block's line for one form gate in watch. MW-112 (R284a): with an end date it says «watch ends <date>», and
    after the date «watch ended: <gate>: enforce or remove» with the count of would-refuse rows."""
    marker = read_marker(state, gate) or {}
    calls, refused = counts(state, gate)
    names = {e["name"] for e in manifest if e.get("gate", e.get("name")) == gate}
    try:
        log = (Path(state) / logs.REFUSALS).relative_to(root).as_posix()
    except ValueError:
        log = (Path(state) / logs.REFUSALS).as_posix()
    line = (f"gate {gate}: WATCH since {marker.get('time') or 'not established'} "
            f"({marker.get('cause') or 'not established'}; {refused} of {calls} in 24 h); "
            f"would-refuse today: {_would_refuse_today(state, names)}; log: {log}")
    raw = watch_until(profile, gate)
    if raw is None:
        return line
    if watch_ended(raw, today or logs.now().date()):
        return line + f"; watch ended: {gate}: enforce or remove; would-refuse: {_would_refuse_total(state, names)}"
    return line + f"; watch ends {raw}"


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
