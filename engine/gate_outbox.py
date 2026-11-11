"""The outbox gate (card MW-019): three entries on one function, `outbox_check.pre`, `outbox_check.post` and
`outbox_check.stop` (manifest; one switch each).

- Edit gate (PreToolUse; Write, Edit, MultiEdit), class form: a write that leaves a check file (`<document><suffix>`
  under `outbox.dir`) whose `sha256:` line is missing, or is not the sha256 of the document now, is refused
  `check-sha-mismatch`. A check names the exact text a fresh reader read, so a stale check cannot be forged by hand; the
  text gives the line to write. It is judged on the file the write leaves (an Edit is applied to the file on disk first).
  A check of a document that does not exist is refused. Every other path, tool and profile passes.
- Post step (PostToolUse; same tools): after a write of a check file the row of the write (document, sha256 of the
  check file as written, the hook's session id, the time) is appended to `<state>/outbox_checks.jsonl`: the proof that a
  session wrote it with a write tool. It never refuses; a failed record is a warn `check-record-failed`.
- Stop reminder (Stop): a warn `outbox-changed-after-check` that names each file whose check is `stale` (its text
  changed after the check), once per session and set of files. It never blocks.

Everything else is `engine/outbox.py`. No task name, no pattern and no natural-language word is in this file.
"""
from __future__ import annotations

from pathlib import Path

import gate
import gate_owner_ask
import outbox
import profiles

WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
MISMATCH = "check-sha-mismatch"


def _target(ctx):
    """(check path, document path) when this call writes a check file under `outbox.dir`, else None."""
    if ctx.tool_name not in WRITE_TOOLS or not isinstance(ctx.tool_input, dict):
        return None
    settings = profiles.outbox_settings(ctx.profile)
    path = ctx.tool_input.get("file_path")
    if not settings["dir"] or not isinstance(path, str):
        return None
    rel = ctx.norm(path, cwd=ctx.cwd)
    document = outbox.doc_of(settings, rel) if rel else None
    return (rel, document) if document else None


def _pre(ctx):
    try:
        target = _target(ctx)
    except Exception:  # not provably a check path: not this gate's write
        return gate.allow()
    if target is None:
        return gate.allow()
    rel, document = target
    how = f"`mkway outbox` lists every file with its check state ({outbox.HOW})"
    try:
        want = outbox.sha_of(Path(ctx.root) / document)
        if want is None:
            return gate.refuse(MISMATCH, f"{rel} is a check for {document}, which does not exist (or cannot be read): a "
                                         f"check belongs to the text a fresh reader read. {how}")
        values = outbox.sha_values(gate_owner_ask._resulting_text(ctx, rel))
    except Exception as exc:  # fail closed, for a check path only
        return gate.refuse(MISMATCH, f"the sha256 of {document} could not be compared ({exc.__class__.__name__}). {how}")
    if values and all(v == want for v in values):
        return gate.allow()
    if not values:
        return gate.refuse(MISMATCH, f"{rel} has no `sha256:` line. A check names the sha256 of the exact text the fresh "
                                     f"reader read: write the line `sha256: {want}` (the sha256 of {document} now). {how}")
    shown = next(v for v in values if v != want)
    return gate.refuse(MISMATCH, f"{rel} holds `sha256: {shown or '(no digest)'}`, but the sha256 of {document} now is "
                                 f"{want}: write the line `sha256: {want}`. If the document changed after the fresh "
                                 f"reader ran, run the reader again on the file as it is now before the check is "
                                 f"written. {how}")


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
        return gate.warn("check-record-failed", f"the record of the write of {target[0]} could not be written "
                                                f"({exc.__class__.__name__}); its check will read `unproven` until "
                                                f"it is written again with a write tool")
    return gate.allow()


def _stop(ctx):
    try:
        stale = outbox.stale_files(ctx.root, ctx.profile)
        if not stale or not ctx.once([f"{s.rel}:{s.sha}" for s in stale]):
            return gate.allow()
    except Exception:
        return gate.allow()
    return gate.warn("outbox-changed-after-check", (
        f"outbox: {', '.join(s.rel for s in stale)} changed after its check. A text leaves only after a fresh reader has "
        f"read it as it is now: run the checker again and write the new check; `mkway outbox` shows the state of every "
        f"file ({outbox.HOW})"))


def check(event, ctx):
    if event == "PreToolUse":
        return _pre(ctx)
    if event == "PostToolUse":
        return _post(ctx)
    if event == "Stop":
        return _stop(ctx)
    return gate.allow()
