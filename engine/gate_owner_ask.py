"""The owner-ask gate (card MW-007): questions to the owner go one way.

A session may ask the owner only after it has written down the sources it checked. The gate has two entries on one
function (manifest `owner_ask.edit` and `owner_ask.stop`, one profile switch `gates.owner_ask`):

- Edit gate (PreToolUse; Write, Edit, MultiEdit): a write to `<asks dir>/<name>_ask.md` needs `<name>_sources.md`
  beside it, with a line `kind: substance|session|lock`:
  - substance: for each source name of the profile, a count line `<source>: N contradictions` and at least one quote
    line `> <source>: <verbatim>`; the source named `ledger` (the default, MW-008) has its own lines: `ledger: N hits`
    and, with N above 0, a `> ledger: <verbatim>` line, or, with N 0, a line `search: <record id>`;
  - session: `checked: ListAgents`;
  - lock: `checked: <lock state>` (any text after the colon).
  Otherwise it refuses, and the text names the missing line. It fails closed for an ask path only: a failure while
  deciding whether the path is an ask path allows the write (a gate that blocked every edit on a bug would be worse).
- Stop gate (Stop): a final reply with a line that starts with one of the profile's markers (after spaces and an
  optional `**`) must have written an ask file since the last real user message of the transcript: a Write, Edit or
  MultiEdit of `<asks dir>/<name>_ask.md` that exists on disk now (a write the edit gate refused leaves no file, so it
  does not count). Otherwise it blocks `ask-not-written`. With `stop_hook_active` it never blocks, so one block
  cannot trap a session. The transcript is the file the hook input names (`transcript_path`); when it cannot be
  read, the gate cannot see a write, so a marker line is still blocked and the text says so.

The decisions are `engine/core_ask.py` (card MW-065): pure functions of a Facts record. This module is the shell: it reads
the facts (the settings, the path as the engine reads it, the sources file, the ask file, the transcript, the files that
exist, the records), calls the decision, turns it into a verdict, and writes the post-step record. The asks folder, the
marker strings and the source names are profile keys with defaults (`profiles.owner_ask`); no task name and no
natural-language word is in this file.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import asks
import core_ask as core
import gate
import profiles
import records

WRITE_TOOLS = core.WRITE_TOOLS
HOW = core.HOW


def as_verdict(decision) -> gate.Verdict:
    """The gate verdict of a core decision (the search and the outbox gates use it too)."""
    if decision.kind == "allow":
        return gate.allow()
    return gate.Verdict(decision.kind, decision.reason, decision.text)


def read_text(path, default=""):
    """The text of a file as the gates read it (undecodable bytes replaced); `default` when it cannot be read."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return default


# ---- the edit gate ------------------------------------------------------------------------------------------------

def _ask_target(ctx, settings, path):
    """(repo-relative path, name) when `path` is `<asks dir>/<name>_ask.md`, else None."""
    if not isinstance(path, str) or not path:
        return None
    return core.ask_target(ctx.norm(path), settings["dir"])


def _edit_facts(ctx):
    """The call's facts and the ask target (None when the path is not an ask path). Raises when the settings or the path
    cannot be read: the caller then allows (not provably an ask path)."""
    settings = profiles.owner_ask(ctx.profile)
    tool_input = ctx.tool_input
    path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    rel = ctx.norm(path) if ctx.tool_name in WRITE_TOOLS and isinstance(path, str) and path else None
    facts = core.EditFacts(tool_name=ctx.tool_name, tool_input=tool_input, rel=rel, dir=settings["dir"],
                           sources=tuple(settings["sources"]), max_open=settings["max_open"],
                           tool_allowed=settings["tool_allowed"], session_id=ctx.session_id)
    return facts, core.ask_target(rel, settings["dir"])


def _ask_file_facts(ctx, rel: str, name: str) -> dict:
    """The facts only an ask path needs: the sources file beside the ask, the ask file as it is on disk (an Edit is
    applied to it), whether it exists, and the session's open asks (a failure to read them is named, not raised)."""
    root = Path(ctx.root)
    sources = root / rel.rpartition("/")[0] / f"{name}{core.SOURCES_SUFFIX}"
    exists = (root / rel).exists()
    found = {"sources_text": read_text(sources, None), "ask_exists": exists,
             "ask_text": "" if ctx.tool_name == "Write" else read_text(root / rel)}
    if ctx.session_id and not exists:
        try:
            found["open_ids"] = tuple(asks.open_of_session(ctx.root, ctx.profile, ctx.session_id))
        except Exception as exc:
            found["open_error"] = exc.__class__.__name__
    return found


def _edit(ctx):
    try:
        facts, target = _edit_facts(ctx)
    except Exception:  # not provably an ask path: not this gate's write (the settings could not be read)
        return gate.allow()
    if target is not None:
        try:
            facts = dataclasses.replace(facts, **_ask_file_facts(ctx, *target))
        except Exception as exc:  # fail closed, for an ask path only
            return as_verdict(core.failed_check(exc.__class__.__name__))
    return as_verdict(core.decide_edit(facts))


# ---- the post step and the reminder -------------------------------------------------------------------------------

def _records_path(ctx) -> str:
    """The records file a failed ask record could not be written to, for the refusal text."""
    try:
        return str(Path(profiles.state_dir(ctx.root, ctx.profile)) / records.RECORDS)
    except Exception:
        return "records.jsonl in the state folder"


def _post(ctx):
    """PostToolUse on a write of an ask file (MW-014): record which session wrote it, when it has no owner yet. The write
    already happened, but a failed record is a refusal naming the path (R271c-D1): the one-open rule cannot see the ask."""
    if ctx.tool_name not in WRITE_TOOLS or not isinstance(ctx.tool_input, dict):
        return gate.allow()
    try:
        settings = profiles.owner_ask(ctx.profile)
        target = _ask_target(ctx, settings, ctx.tool_input.get("file_path"))
        if target is None or not (Path(ctx.root) / target[0]).is_file():
            return gate.allow()
        asks.record_owner(ctx.root, ctx.profile, ctx.session_id, target[1])
    except Exception as exc:
        return gate.refuse("ask-record-failed", f"the ask's owner record could not be written "
                                                f"({exc.__class__.__name__}): "
                                                f"{_records_path(ctx)} is not "
                                                f"written, so the one-open rule cannot see this ask; report it to the "
                                                f"operator: the owner repairs the file")
    try:  # the owner's notification: never blocks, always a row
        done = asks.notify(ctx.root, ctx.profile, asks.read(Path(ctx.root) / target[0]))
    except Exception as exc:
        done = (False, f"the notify step failed ({exc.__class__.__name__})")
    if done is None:
        return gate.allow()
    return gate.log("notify-sent" if done[0] else "notify-failed", done[1])


def read_entries(path):
    """The entries of a transcript file (a line that is not JSON is skipped), or None when it cannot be read."""
    entries = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except (OSError, TypeError):
        return None
    return entries


def turn_split(path):
    """(entries after the last real user message, readable, that user message or None). The Stop gate and the search
    gate (MW-008) both read the turn boundary here; the rule is `core_ask.turn_split`."""
    entries = read_entries(path)
    if entries is None:
        return [], False, None
    after, user = core.turn_split(entries)
    return after, True, user


# ---- the stop gate ------------------------------------------------------------------------------------------------

def _stop_facts(ctx):
    hook_input = ctx.hook_input if isinstance(ctx.hook_input, dict) else {}
    if hook_input.get("stop_hook_active"):  # the decision allows at once: nothing else is read
        return core.StopFacts(hook_active=True, last_message=None, entries=None, markers=(), dir="")
    settings = profiles.owner_ask(ctx.profile)
    entries = read_entries(hook_input.get("transcript_path"))
    rels = {}
    for block in core.blocks(entries or (), "tool_use"):
        path = block.get("input", {}).get("file_path") if isinstance(block.get("input"), dict) else None
        if block.get("name") in WRITE_TOOLS and isinstance(path, str) and path and path not in rels:
            rels[path] = ctx.norm(path)
    root = Path(ctx.root)
    on_disk = frozenset(rel for rel in rels.values() if rel and (root / rel).is_file())
    return core.StopFacts(hook_active=False, last_message=hook_input.get("last_assistant_message"),
                          entries=None if entries is None else tuple(entries), markers=tuple(settings["markers"]),
                          dir=settings["dir"], rels=rels, on_disk=on_disk)


def _stop(ctx):
    return as_verdict(core.decide_stop(_stop_facts(ctx)))


def _remind(ctx):
    """UserPromptSubmit (MW-014): a session that owns an open ask past its deadline is told to take the default or keep
    waiting. A reminder only: a failure allows."""
    try:
        lines = asks.reminders(ctx.root, ctx.profile, ctx.session_id)
    except Exception:
        return gate.allow()
    return gate.warn("ask-past-deadline", chr(10).join(lines)) if lines else gate.allow()


def check(event, ctx):
    if event == "PreToolUse":
        return _edit(ctx)
    if event == "Stop":
        return _stop(ctx)
    if event == "PostToolUse":
        return _post(ctx)
    if event == "UserPromptSubmit":
        return _remind(ctx)
    return gate.allow()
