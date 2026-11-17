"""The dispatcher (card MW-002, deliverable 3; R11 point 1, defect 35).

One process per hook call: `mkway.py hook <event> --group <name>`. It reads the hook JSON from stdin, finds the
root and the profile, loads the profile once, and runs the gates of that event and group in manifest order. It
skips a gate the profile turns off and a gate whose own matcher does not match the tool name. The first refuse
ends the run. It then writes Claude Code's documented hook output (see `render`).

onFailure is applied here, per gate: a gate that raises is `gate-error`; `block` refuses, anything else allows.
Any other exception (the dispatcher itself, the stdin, the manifest, a gate module that cannot load, a `SystemExit`
outside a gate call) is caught by the outer handler: a `dispatcher-error` row, one stderr line and a
`systemMessage`. In `edit` and `shell` it exits 2 (the tool call is blocked); in every other group it exits 0
(R13c). A failed log write never reaches it: the verdict stands and a `systemMessage` is added; a failed once-store
write counts as «first time». A broken profile is not a crash: it stays the `profile-invalid` warn. A crash never passes silently.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Union

import gatemode
import logs
import paths
import profiles
import startline
from gate import ALLOW, LOG, REFUSE, Context, Verdict

ENGINE_DIR = Path(__file__).resolve().parent  # the engine's own files (manifest, gate modules); never the task root
TOOL_EVENTS = ("PreToolUse", "PostToolUse")
BLOCK_EVENTS = ("Stop", "PostToolUse", "UserPromptSubmit")  # top-level `decision: block` + `reason`
BLOCKING_GROUPS = ("edit", "shell")  # = the manifest group table's `onFailure: block` (R13c; test E54)
CONTEXT_EVENTS = ("PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop", "SessionStart")
REPAIR = ("Repair: run `mkway check` (it changes no state) and report its output to the operator; the owner repairs "
          "the settings or the engine copy (a protected target), then the call is repeated")
NOT_A_BREACH = ("the gate's own code failed; this is not a rule breach. Report it, and do not change your work to "
                "satisfy a broken gate")


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str
    not_loaded: list = field(default_factory=list)


class OnceStore:
    """`once(gate, targets)` is true only the first time in a session for that gate and that set of targets. One
    empty file per key under `<state.dir>/once/`, created exclusively."""

    def __init__(self, state_dir: Path, session_id: Optional[str]):
        self.folder = Path(state_dir) / "once"
        self.session = session_id or ""

    def once(self, gate: str, targets: Union[str, Iterable[str]]) -> bool:
        items = [targets] if isinstance(targets, str) else list(targets)
        target_hash = hashlib.sha256("\n".join(sorted(set(map(str, items)))).encode("utf-8")).hexdigest()
        key = hashlib.sha256(f"{self.session}\0{gate}\0{target_hash}".encode("utf-8")).hexdigest()
        self.folder.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.folder / key, "x", encoding="utf-8"):
                return True
        except FileExistsError:
            return False


def matcher_matches(matcher, tool_name) -> bool:
    if matcher in (None, "", "*"):
        return True
    try:
        return re.fullmatch(matcher, tool_name or "") is not None
    except re.error:
        return matcher == tool_name


def load_function(spec: str, gate_paths):
    module_name, _, func_name = spec.partition(":")
    added = [str(p) for p in gate_paths if str(p) not in sys.path]
    sys.path[:0] = added
    try:
        module = importlib.import_module(module_name)
    finally:
        for p in added:
            if p in sys.path:
                sys.path.remove(p)
    return getattr(module, func_name)


AT_ROOT = object()  # make_context's default `cwd`: the root (callers outside a hook, and the engine's own tests)


def make_context(*, profile, root, session_id, event, gate, tool_name, tool_input, budget_seconds, once,
                 tool_response=None, profile_file=None, env=None, cwd=AT_ROOT, hook_input=None,
                 payload=None) -> Context:
    """The gate's context with the shared helpers bound to this root and tool (card MW-003, deliverable 1). `cwd` is
    the hook input's `cwd` (batch 3, item 15): a relative write is read from it; when it is missing (None) or
    outside the root, a relative write counts as everywhere. A caller that names no `cwd` gets the root."""
    import helpers
    import records
    import register
    root = Path(root)
    shell = "powershell" if tool_name == "PowerShell" else "bash"
    env = {} if env is None else env
    home = env.get("USERPROFILE") or env.get("HOME") or None
    prefix = helpers.top_prefix(root)
    state = profiles.state_dir(root, profile)
    if cwd is AT_ROOT:
        start, cwd = "", str(root)
    else:
        rel = helpers.norm(cwd, root, top_prefix=prefix, home=home) if isinstance(cwd, str) else None
        start = None if rel is None else ("" if rel == "." else rel)
    return Context(
        cwd=cwd, hook_input=hook_input, payload=payload,
        profile=profile, root=root, session_id=session_id, event=event, gate=gate, tool_name=tool_name,
        tool_input=tool_input, budget_seconds=budget_seconds, once=once, tool_response=tool_response,
        profile_file=Path(profile_file) if profile_file else paths.profile_path(root),
        norm=lambda p, cwd=None: helpers.norm(p, root, top_prefix=prefix, home=home, cwd=cwd),
        commit_cmd=lambda cmd: helpers.commit_cmd(cmd, root=root, shell=shell, start=start),
        shell_writes=lambda cmd, home=None: helpers.shell_writes(cmd, shell, cwd=start, root=root, home=home),
        mkway_calls=lambda cmd: helpers.mkway_calls(cmd, shell),
        records=records.View(state, session_id, closed=lambda: register.closed_ids(root, profile)), env=env)


def load_manifest(engine_dir: Path) -> list:
    return json.loads((Path(engine_dir) / "manifest.json").read_text(encoding="utf-8"))["entries"]


def _tag(gate_name, reason_id, message) -> str:
    return f"[mkway {gate_name} {reason_id}] {message}"


def render(event: str, refusal, warns: list):
    """(exit code, stdout, stderr) in Claude Code's documented hook output.
    PreToolUse: refuse = hookSpecificOutput.permissionDecision deny + permissionDecisionReason.
    Stop, PostToolUse, UserPromptSubmit: refuse = top-level decision block + reason.
    A warn = hookSpecificOutput.additionalContext (it blocks nothing). SessionStart cannot block: a refuse there is
    context. Another event: a refuse is exit code 2 with the message on stderr («not established» in the card)."""
    context = "\n".join(warns)
    if event == "SessionStart" and refusal:
        context = "\n".join([refusal] + warns)
        refusal = None
    if refusal is None and not context:
        return 0, "", ""
    if event == "Stop":  # MW-075: a Stop warn is shown to the user only; additionalContext would wake the session again
        out = {"decision": "block", "reason": refusal} if refusal else {}
        if context:
            out["systemMessage"] = context
        return 0, json.dumps(out), ""
    if event not in CONTEXT_EVENTS:
        if refusal:
            return 2, "", refusal + "\n"
        # R271c: a warn on SubagentStop (a failed agent record) is a visible message: the event carries no context
        return (0, json.dumps({"systemMessage": context}), "") if context else (0, "", "")
    out: dict = {}
    specific: dict = {"hookEventName": event}
    if refusal and event == "PreToolUse":
        specific["permissionDecision"] = "deny"
        specific["permissionDecisionReason"] = refusal
    elif refusal and event in BLOCK_EVENTS:
        out["decision"] = "block"
        out["reason"] = refusal
    if context:
        specific["additionalContext"] = context
    if len(specific) > 1:
        out["hookSpecificOutput"] = specific
    return 0, json.dumps(out), ""


def _vcs_hint(profile_arg):
    if not profile_arg:
        return None
    try:
        return json.loads(Path(profile_arg).read_text(encoding="utf-8")).get("vcs")
    except Exception:
        return None


def _guarded(log_errors: list, write, default=None):
    """A refusal, timing or once-store write. A failure is recorded and the run goes on: a failed log write alone
    never blocks and never unblocks; the output then adds a `systemMessage` (R13c, fix check N1)."""
    try:
        return write()
    except Exception as exc:
        log_errors.append(exc.__class__.__name__)
        return default


def run(event: str, group: str, stdin_text: str, *, env=None, root_arg=None, profile_arg=None, engine_dir=ENGINE_DIR,
        manifest=None, gate_paths=None, cwd=None) -> Result:
    info = {"session": None, "event": event, "group": group, "tool": None, "gate": None, "root": None,
            "state": None, "where": "the dispatcher"}
    try:
        return _run(event, group, stdin_text, env, root_arg, profile_arg, Path(engine_dir), manifest,
                    gate_paths if gate_paths is not None else [Path(engine_dir)], cwd, info)
    except BaseException as exc:  # the outer error handler; a SystemExit too, e.g. at a gate import (fix check 2 L2)
        if isinstance(exc, KeyboardInterrupt):
            raise
        return _crash(exc, info)


def _note_session(event: str, root, profile, session) -> None:
    """MW-017 (addition 1): the SessionStart hook appends `{session_id, root, ts}` to the shared `sessions.jsonl`; a prompt
    refreshes the last-seen row at most once in ten minutes."""
    import sessions
    sessions.touch(profiles.shared_state_dir(root, profile), session, root, force=event == "SessionStart")


def _notify_trip(state, gate_name: str, counts: dict) -> None:
    """MW-017: a form gate that tripped into watch is a notice to every registered lead (no lead: nothing is written)."""
    import leads
    leads.notify_all(state, f"gate {gate_name} tripped into watch: {counts.get('refused')} of {counts.get('calls')} calls "
                            f"refused in the last 24 h; it now logs would-refuse and no longer blocks. The owner "
                            f"returns it to blocking with `mkway gate on {gate_name}`")


NE = "not established"  # a value the record does not hold is never guessed


def _deliver_refusal(root, profile, state, session, payload, warns: list, log, log_errors: list):
    """MW-128 (R301, R301a): the Stop step. When the last engine call of this session's turn was refused and nothing was sent on,
    the engine writes the refusal into the orderer's inbox itself, records the gate refusal row id as delivered and blocks ONCE
    with the exact ping line, never when `stop_hook_active` is true and never twice for one id. The facts come from the engine's
    own records, never the transcript; `core_refusal` decides. Returns (the block reason or None to let the Stop pass, the action:
    `allow`, `block`, `delivered`, `no-orderer` or `error`; MW-132 runs its own step only after `allow`). A Stop hook
    cannot fail closed: when a fact cannot be read or the inbox row cannot be written, the stop is allowed with a calls-log
    error row (reason `refusal-delivery-failed`), a screen line and, from the row, a notice on this session's start line; the id
    is not recorded as delivered, so the next Stop tries once more."""
    import core_refusal as core
    import messages
    refusal_id = None
    try:
        shared = profiles.shared_state_dir(root, profile)
        sends = tuple(messages.sends_by(shared, session))
        orderer = messages.orderer_of(root, profile, session)
        delivered = frozenset(gatemode.delivered_ids(state))
        hook_active = bool(payload.get("stop_hook_active"))

        def decided(rows):
            facts = core.Facts(calls=tuple(core.Call(c["call"], c["time"], c["refused"], c["id"]) for c in rows),
                               sends=sends, orderer=orderer, delivered=delivered, hook_active=hook_active)
            return core.decide(facts)

        calls = gatemode.turn_calls(state, session)
        decision = decided(calls)
        if decision.action == core.ALLOW:  # R301a 2: a refusal whose write failed once is tried again at the next stop
            retry = gatemode.retry_candidate(state, session)
            if retry:
                calls = [retry]
                decision = decided(calls)
        refusal_id = decision.refusal_id
        if decision.action == core.ALLOW:
            return None, "allow"
        row = calls[-1]
        if decision.action == core.NO_ORDERER:
            log(logs.row(session=session, event="Stop", tool=None, gate="refusal_delivery", reason_id="refusal-no-orderer",
                         target=None, kind="log", refusal=refusal_id))
            gatemode.mark_delivered(state, refusal_id, session, "no-orderer")
            return None, "no-orderer"
        sent = messages.send_refusal(root, profile, shared, session, decision.orderer, row.get("target") or NE,
                                     row.get("message") or NE, refusal_id)
        outcome = core.finish(decision, True)
        gatemode.mark_delivered(state, refusal_id, session, "delivered", sent.row["id"])
        log(logs.row(session=session, event="Stop", tool=None, gate="refusal_delivery", reason_id="refusal-delivered",
                     target=None, kind="log", refusal=refusal_id, inbox_id=sent.row["id"], to=decision.orderer))
        return (core.block_reason(sent.row["id"]), "block") if outcome.block else (None, "delivered")
    except Exception as exc:
        cls = exc.__class__.__name__
        _guarded(log_errors, lambda: gatemode.append_call(
            state, "refusal_delivery", "error", session=session, event="Stop", reason_id="refusal-delivery-failed",
            refusal=refusal_id, error=cls, message=_error_line(exc)))
        warns.append(f"mkway refusal-delivery-failed: the refusal of your last engine call could not be written to your "
                     f"orderer ({cls}); nothing was blocked. Tell your orderer yourself: send the exact command and the "
                     f"refusal line with `mkway send` (the row is in gate_calls.jsonl)")
        return None, "error"


def _count(value):
    """The number of items of a hook input list (`background_tasks`); None when the field is absent or no list."""
    return len(value) if isinstance(value, (list, tuple)) else None


def _hand_off(root, profile, state, session, payload, warns: list, log_errors: list):
    """MW-132 (R337, R337a, R338, R338a): the Stop step after MW-128's. A session that holds a card its orderer ordered and ends its
    turn with no `mkway send` to that orderer has its last message (a hook input field, cut) written into the orderer's inbox at
    once, once per turn; a builder (its orderer a registered lead) is then blocked ONCE with the exact ping line, never when
    `stop_hook_active` is true. The facts come from the engine's own records and the hook input, never the transcript;
    `core_handoff` decides. Returns the block reason or None. A Stop hook cannot fail closed: when a fact cannot be read or the
    inbox row cannot be written, the stop is allowed with a calls-log error row (reason `handoff-notice-failed`, which is also
    this turn's try), a screen line and a start-line notice."""
    import core_handoff as core
    import leads
    import messages
    import register
    try:
        shared = profiles.shared_state_dir(root, profile)
        held = messages.held_card(root, profile, session)  # raises on a failed read: never «no card» or «no orderer»
        if held is None or leads.is_lead(shared, session):
            return None
        card, ordered = held
        hook_active = bool(payload.get("stop_hook_active"))
        turn = gatemode.handoff_turn(state, session, hook_active)
        if turn is None:  # the engine saw no turn of this session begin (no prompt row): nothing is judged, one record row
            logs.write_refusal(state, logs.row(session=session, event="Stop", tool=None, gate="handoff", reason_id=core.NO_TURN_START_ID,
                                               target=None, kind="log", card=card))
            return None
        facts = core.Facts(
            session=session, card=card, orderer=None if not ordered or ordered == register.OWNER else ordered,
            role=messages.role_of(root, profile, shared, session).kind, turn_start=turn,
            sends=tuple(messages.sends_to(shared, session)), delivered=gatemode.turn_delivered(state, session, turn),
            hook_active=hook_active, background_tasks=_count(payload.get("background_tasks")))
        decision = core.decide(facts)
        if decision.action == core.ALLOW:
            return None
        if decision.action == core.NO_ORDERER:
            logs.write_refusal(state, logs.row(session=session, event="Stop", tool=None, gate="handoff", reason_id="handoff-no-orderer",
                                               target=None, kind="log", card=card, turn=turn, orderer=ordered or NE))
            return None
        sent = messages.send_handoff(root, profile, shared, session, decision.orderer,
                                     core.notice_body(session, card, payload.get("last_assistant_message")), card)
        outcome = core.finish(decision, True)
        logs.write_refusal(state, logs.row(session=session, event="Stop", tool=None, gate="handoff", reason_id="handoff-notice",
                                           target=None, kind="log", card=card, to=decision.orderer, inbox_id=sent.row["id"],
                                           turn=turn, blocked=outcome.block, background_tasks=facts.background_tasks))
        return core.block_reason(card, sent.row["id"]) if outcome.block else None
    except Exception as exc:
        cls = exc.__class__.__name__
        _guarded(log_errors, lambda: gatemode.append_call(
            state, "handoff", "error", session=session, event="Stop", reason_id="handoff-notice-failed", error=cls,
            message=_error_line(exc)))
        warns.append(f"mkway handoff-notice-failed: your last message could not be written to your orderer ({cls}); nothing was "
                     f"blocked. Tell your orderer yourself: `mkway send` your question, your result, or what you wait for "
                     f"(the row is in gate_calls.jsonl)")
        return None


def _error_line(exc: BaseException) -> str:
    """The first line of the error's text, at most 200 characters; the class name when the error has no text."""
    lines = str(exc).strip().splitlines()
    return lines[0][:200] if lines else exc.__class__.__name__


def _crash(exc: Exception, info: dict) -> Result:
    """The outer error handler. In the groups whose entry carries `onFailure: block` (edit, shell) a failure the
    dispatcher cannot evaluate past exits 2, so the tool call is blocked with the reason. Every failure in the other
    groups exits 0. A failed log write never reaches here (`_guarded`). Each writes a `dispatcher-error` row when it can, one stderr line
    and a `systemMessage` (R13c)."""
    cls = exc.__class__.__name__
    blocking = info.get("group") in BLOCKING_GROUPS
    state = info["state"] or (Path(info["root"]) / profiles.DEFAULT_STATE_DIR if info["root"] else None)
    written = False
    if state is not None:
        try:
            logs.write_refusal(state, logs.row(session=info["session"], event=info["event"], tool=info["tool"],
                                               gate=info["gate"], reason_id="dispatcher-error", target=None,
                                               kind="error", exception=cls))
            written = True
        except Exception:
            written = False
    where = f"gate {info['gate']}" if info["gate"] else info["where"]
    outcome = ("the tool call is blocked, because the dispatcher could not evaluate its gates. The dispatcher's "
               "own code failed; this is not a rule breach. Report it, and do not change your work to satisfy a "
               "broken dispatcher. " + REPAIR if blocking else "nothing was blocked.")
    line = (f"mkway dispatcher-error: {cls} ({_error_line(exc)}) in {where}; {outcome} "
            + ("Logged in refusals.jsonl." if written else "The dispatcher-error row could not be written."))
    return Result(2 if blocking else 0, json.dumps({"systemMessage": line}), line + "\n", [])


def _run(event, group, stdin_text, env, root_arg, profile_arg, engine_dir, manifest, gate_paths, cwd, info) -> Result:
    info["where"] = "the root lookup"
    root = paths.find_root(env=env, root_arg=root_arg, vcs=_vcs_hint(profile_arg), cwd=cwd)
    info["root"] = root
    info["where"] = "the profile load"
    profile_file = paths.profile_path(root, profile_arg)
    profile, errors = profiles.load(profile_file)
    state = profiles.state_dir(root, profile)
    info["state"] = state
    info["where"] = "the dispatcher"
    log_errors: list = []

    def log(data):
        _guarded(log_errors, lambda: logs.write_refusal(state, data))

    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        raise TypeError("the hook input is not a JSON object")
    session = payload.get("session_id")
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    info.update(session=session, tool=tool)
    if event in ("SessionStart", "UserPromptSubmit"):  # MW-017: the shared sessions file, one row per start and per 10 min
        _guarded(log_errors, lambda: _note_session(event, root, profile, session))
    target = logs.target_of(tool_input)
    entries = manifest if manifest is not None else load_manifest(engine_dir)
    started = time.perf_counter()
    call_id = secrets.token_hex(6)  # MW-128: the rows of this hook call in the calls log share it
    gates_ms: dict = {}
    warns: list = []
    refusal = None
    not_loaded: list = []
    if event == "SessionStart":
        info["where"] = "the start line"
        head = startline.render(root, profile_file, profile, errors, entries, os.environ if env is None else env,
                                session=session)
        info["where"] = "the dispatcher"
    else:
        head = None

    def base_row(gate_name, reason_id, kind, **extra):
        return logs.row(session=session, event=event, tool=tool, gate=gate_name, reason_id=reason_id, target=target,
                        kind=kind, **extra)

    if errors:
        # C52 (R37 H1, changes C17): fail closed. `edit` and `shell` refuse every call with the validator's message;
        # no gate runs with defaults (a typo would drop the task's own lock targets). The other groups write one
        # `log` row per session, group and profile content (the once-store of C17 a).
        message = ("the profile is invalid: " + "; ".join(errors[:5]) + ". Every edit and shell call is refused "
                   "until the owner fixes the profile in their own editor; `mkway install` and `mkway check` run "
                   "in the owner's terminal")
        if group in BLOCKING_GROUPS:
            refusal = _tag("profile", "profile-invalid", message)
            log(base_row("profile", "profile-invalid", "refuse"))
        else:
            content = profile_file.read_bytes() if profile_file.is_file() else b""
            content_hash = hashlib.sha256(content).hexdigest()
            if _guarded(log_errors, lambda: OnceStore(state, session).once(f"profile.{group}", [content_hash]),
                        default=True):
                log(base_row("profile", "profile-invalid", "log"))
    else:
        store = OnceStore(state, session)
        selected = [e for e in entries if e.get("event") == event and e.get("group") == group and e.get("function")]
        for e in selected:
            name = e["name"]
            reason_ids = e.get("reason_ids") or []
            if not reason_ids:
                not_loaded.append(name)
                continue
            if not profiles.gate_on(profile, e.get("gate", name), e.get("default_on", False)):
                continue
            if event in TOOL_EVENTS and not matcher_matches(e.get("matcher"), tool):
                continue
            info["gate"] = name
            budget = profiles.budget_seconds(profile, e.get("gate", name))
            ctx = make_context(profile=profile, root=root, session_id=session, event=event, gate=name,
                               tool_name=tool, tool_input=tool_input, budget_seconds=budget,
                               once=lambda targets, _n=name: _guarded(log_errors, lambda: store.once(_n, targets),
                                                                      default=True),  # failure = first time (L1)
                               tool_response=payload.get("tool_response"), profile_file=profile_file,
                               env=os.environ if env is None else env, cwd=payload.get("cwd"), hook_input=payload,
                               payload=payload)
            info["where"] = f"loading gate {name}"
            function = load_function(e["function"], gate_paths)  # R13c: a module that cannot load is a dispatcher failure
            info["where"] = "the dispatcher"
            t0 = time.perf_counter()
            error = None
            try:
                verdict = function(event, ctx)
                if not isinstance(verdict, Verdict):
                    raise TypeError("the gate did not return a Verdict")
            except BaseException as exc:  # SystemExit from a gate is a gate error too (fix check N5)
                if isinstance(exc, KeyboardInterrupt):
                    raise
                error = exc
            elapsed_ms = (time.perf_counter() - t0) * 1000
            gates_ms[name] = round(elapsed_ms, 3)
            mode_gate = e.get("gate", name)
            form = gatemode.entry_class(e) == gatemode.FORM  # an integrity gate never reads a marker (MW-012)
            watching = form and _guarded(log_errors, lambda: gatemode.is_watching(state, mode_gate), default=False)
            if error is not None:
                cls = error.__class__.__name__
                applied = REFUSE if e.get("onFailure") == "block" else ALLOW
                log(base_row(name, "gate-error", "error", exception=cls, applied=applied))
                if applied == REFUSE:
                    refusal = _tag(name, "gate-error", f"gate {name} failed with {cls} ({_error_line(error)}): "
                                                       f"{NOT_A_BREACH}. {REPAIR}")
                call_verdict = "error"
            elif verdict.kind != ALLOW:
                if verdict.reason_id in reason_ids:
                    data = base_row(name, verdict.reason_id, verdict.kind)
                else:
                    data = base_row(name, "undeclared-reason", verdict.kind, gate_reason=verdict.reason_id)
                if verdict.kind == REFUSE and watching:  # MW-012: the same reason id and text, and the call goes ahead
                    data.update(kind=gatemode.WOULD_REFUSE, message=verdict.message)
                log(data)
                tagged = _tag(name, verdict.reason_id, verdict.message)
                if verdict.kind == REFUSE:
                    if not watching:
                        refusal = tagged
                elif verdict.kind != LOG:  # a log verdict is the row only (list item 5, R43 (c))
                    # MW-075: the same Stop warn text is shown once per session; the row above is written either way
                    if event != "Stop" or ctx.once([tagged]):
                        warns.append(tagged)
                call_verdict = "refuse" if verdict.kind == REFUSE else "log"
            else:
                call_verdict = "allow"
            call_facts = {"session": session, "event": event, "tool": tool, "call": call_id}  # MW-128: whose call it is
            if call_verdict == "refuse":  # MW-128: the exact command, the refusal line and the reason, for the refusal delivery
                call_facts.update(target=target, message=tagged, reason_id=verdict.reason_id,
                                  watching=True if watching else None)
            _guarded(log_errors, lambda: gatemode.append_call(state, mode_gate, call_verdict, round(elapsed_ms, 3),
                                                              **call_facts))  # MW-012, rule 2; MW-112: the time of the gate
            if call_verdict == "refuse" and form and not watching:  # MW-012, rule 4: this call stays refused
                tripped = _guarded(log_errors, lambda: gatemode.trip(state, profile, mode_gate))
                if tripped:
                    log(base_row(name, "gate-tripped", "log", cause="tripped", **tripped))
                    _guarded(log_errors, lambda: _notify_trip(profiles.shared_state_dir(root, profile), mode_gate,
                                                              tripped))  # MW-017: every lead is told
            if budget is not None and elapsed_ms > budget * 1000:
                log(base_row(name, "over-budget", "log", elapsed_ms=round(elapsed_ms, 3),
                                                   budget_seconds=budget))
            info["gate"] = None
            if refusal:
                break
    if event == "Stop" and group == "stop" and refusal is None and not errors and isinstance(session, str) and session:
        refusal, refusal_action = _deliver_refusal(root, profile, state, session, payload, warns, log, log_errors)  # MW-128 (R301, R301a)
        if refusal is None and refusal_action == "allow":  # MW-132: only when MW-128 did nothing at this stop (R1-10)
            refusal = _hand_off(root, profile, state, session, payload, warns, log_errors)
    if head:
        warns.insert(0, head)
    timing = {"time": logs.now().isoformat(timespec="milliseconds"), "session": session, "event": event,
              "group": group, "gates_ms": gates_ms, "total_ms": round((time.perf_counter() - started) * 1000, 3)}
    if event == "Stop":  # MW-132 (R340a): a Stop row keeps the hook input's flag; a stop with it true continues the turn before it
        timing["stop_hook_active"] = bool(payload.get("stop_hook_active"))
    _guarded(log_errors, lambda: logs.write_timing(state, timing))
    code, out, err = render(event, refusal, warns)
    if event == "SessionStart" and isinstance(profile, dict) and not errors:
        notice = startline.owner_notice(root, profile)  # M1 (R60): the owner sees it; it never raises
        if notice:
            data = json.loads(out) if out else {}
            data["systemMessage"] = notice
            out = json.dumps(data)
    if log_errors:  # the verdict stands; the user is told the row is missing (fix check N1)
        note = f"mkway dispatcher-error: {log_errors[0]} in the log write; the row could not be written."
        data = json.loads(out) if out else {}
        data["systemMessage"] = note + ("\n" + data["systemMessage"] if data.get("systemMessage") else "")
        out = json.dumps(data)
        err += note + "\n"
    return Result(code, out, err, not_loaded)
