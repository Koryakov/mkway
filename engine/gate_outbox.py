"""The outbox gate (card MW-019): three entries on one function, `outbox_check.pre`, `outbox_check.post` and
`outbox_check.stop` (manifest; one switch each).

- Edit gate (PreToolUse; Write, Edit, MultiEdit), class form: a write that leaves a check file (`<document><suffix>`
  under `outbox.dir`) whose `sha256:` line is missing, or is not the sha256 of the document now, is refused
  `check-sha-mismatch`. A check names the exact text a fresh reader read, so a stale check cannot be forged by hand; the
  text gives the line to write. It is judged on the file the write leaves (an Edit is applied to the file on disk first).
  A check of a document that does not exist is refused. Every other path, tool and profile passes.
- Post step (PostToolUse; same tools): after a write of a check file the row of the write (document, sha256 of the
  check file as written, the hook's session id, the time) is appended to `<state>/outbox_checks.jsonl`: the proof that a
  session wrote it with a write tool. A failed record is a refusal `check-record-failed` that names the path (R271c-D1). A write of a
  verdict file (`tests/verdicts/<card>.md`) leaves no record since MW-080 (ruling R196 item 5): the proof of a verdict row
  is the record of the engine command `mkway verdict add`, so a row typed with a write tool reads `verdict-unproven` at the
  close in every gate mode.
- Verdict file (MW-080, PreToolUse; Write, Edit, MultiEdit of `tests/verdicts/<card>.md`): refused
  `verdict-file-by-command`, a helpful message that names the command; it follows the gate mode of this entry (watch: a
  `would-refuse` row, the write goes ahead, and the row still has no proof).
- Stop reminder (Stop): a warn `outbox-changed-after-check` that names each file whose check is `stale` (its text
  changed after the check), once per session and set of files. It never blocks.

The decisions are `engine/core_ask.py` (card MW-065); this module is the shell: it reads the facts (the path as the engine
reads it, the document's sha256, the check file on disk, the files whose check is stale), calls the decision, and writes
the record of a write. Everything else is `engine/outbox.py`. No task name, no pattern and no natural-language word is
in this file.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import core_ask as core
import gate
import gate_owner_ask
import outbox
import profiles
import verdicts

WRITE_TOOLS = core.WRITE_TOOLS
MISMATCH = core.MISMATCH


def _facts(ctx) -> core.OutboxFacts:
    """The facts of the call: the tool, the outbox folder of the profile, the check suffix, the path as the engine reads
    it (relative to the hook's working folder)."""
    tool_input = ctx.tool_input
    folder = profiles.outbox_settings(ctx.profile)["dir"]
    path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    rel = ctx.norm(path, cwd=ctx.cwd) if ctx.tool_name in WRITE_TOOLS and folder and isinstance(path, str) else None
    return core.OutboxFacts(tool_name=ctx.tool_name, tool_input=tool_input, rel=rel, dir=folder, suffix=outbox.suffix())


def _target(ctx):
    """(check path, document path) when this call writes a check file under `outbox.dir`, else None."""
    return core.outbox_target(_facts(ctx))


def _pre(ctx):
    try:  # MW-080 (R194): a verdict row has one writer, the engine command; this message names it
        rel = _verdict_rel(ctx)
    except Exception:
        rel = None
    if rel is not None:
        return gate.refuse("verdict-file-by-command",
                           f"{rel} is a verdict file: a verdict row is written only by the engine command "
                           f"`python mkway/engine/mkway.py verdict add <card> <node> [<node> ...] <true|weak|wrong> "
                           f"\"<reason>\"`, run in a session that did not build or commit the card's tests, after a fresh "
                           f"checker agent read the committed test file. A row typed with Write, Edit or MultiEdit has no "
                           f"proof and reads `verdict-unproven` at `card close`")
    try:
        facts = _facts(ctx)
        target = core.outbox_target(facts)
    except Exception:  # not provably a check path: not this gate's write
        return gate.allow()
    if target is None:
        return gate.allow()
    rel, document = target
    try:
        root = Path(ctx.root)
        facts = dataclasses.replace(
            facts, doc_sha=outbox.sha_of(root / document),
            check_text="" if ctx.tool_name == "Write" else gate_owner_ask.read_text(root / rel))
    except Exception as exc:  # fail closed, for a check path only
        facts = dataclasses.replace(facts, error=exc.__class__.__name__)
    return gate_owner_ask.as_verdict(core.decide_check_write(facts))


def _verdict_rel(ctx):
    """The path of the verdict file (`tests/verdicts/<card>.md`) this write leaves, from the task root, else None."""
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    path = tool_input.get("file_path")
    if ctx.tool_name not in WRITE_TOOLS or not isinstance(path, str):
        return None
    rel = ctx.norm(path, cwd=ctx.cwd)
    return rel if isinstance(rel, str) and verdicts.is_verdict_file(rel) else None


def _post(ctx):
    try:
        target = _target(ctx)
        if target is None or not (Path(ctx.root) / target[0]).is_file():
            return gate.allow()
    except Exception:
        return gate.allow()
    try:
        outbox.record_check(ctx.root, ctx.profile, ctx.session_id, target[0])
    except Exception as exc:
        try:
            where = Path(profiles.state_dir(Path(ctx.root), ctx.profile)) / outbox.RECORDS
        except Exception:
            where = f"{outbox.RECORDS} in the state folder"
        return gate.refuse("check-record-failed", f"the record of the write of {target[0]} could not be written "
                                                  f"({exc.__class__.__name__}): {where} is not written, so its check "
                                                  f"will read `unproven` until it is written again with a write tool; "
                                                  f"report it to the operator: the owner repairs the file")
    return gate.allow()


def _stop(ctx):
    try:
        stale = outbox.stale_files(ctx.root, ctx.profile)
        first = bool(stale) and ctx.once([f"{s.rel}:{s.sha}" for s in stale])
    except Exception:
        return gate.allow()
    decision = core.decide_stale_reminder(tuple(s.rel for s in stale), first)
    if decision.kind != "allow":
        return gate_owner_ask.as_verdict(decision)
    return _lead_warning(ctx)


def _lead_warning(ctx):
    """MW-068, ruling R179 condition 1: a lead's Stop repeats `blind verdict not enforced: outbox.checkers missing in
    profile` while the check is on and the key is missing; it never blocks and stops when the key is set."""
    try:
        import cardtool  # late: it imports gates' helpers
        import core_verdicts
        import leads
        profile = ctx.profile if isinstance(ctx.profile, dict) else {}
        text = core_verdicts.stop_warning(leads.is_lead(profiles.shared_state_dir(ctx.root, profile), ctx.session_id),
                                          cardtool.verdicts_required(profile),
                                          not profiles.outbox_settings(profile)["checkers"])
    except Exception:
        return gate.allow()
    if text and not ctx.once([text]):  # MW-112 (MW112-D1): said once per session, never at every Stop
        return gate.allow()
    return gate.warn("verdict-not-enforced", text) if text else gate.allow()


def check(event, ctx):
    if event == "PreToolUse":
        return _pre(ctx)
    if event == "PostToolUse":
        return _post(ctx)
    if event == "Stop":
        return _stop(ctx)
    return gate.allow()
