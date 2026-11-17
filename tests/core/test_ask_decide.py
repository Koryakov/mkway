"""Card MW-065: table tests of the pure decisions of the ask family (`engine/core_ask.py`): the owner-ask edit gate and stop
gate, the search gate and the outbox check write gate. Facts in, Decision out: no disk, no git, no process, no clock.
One test id is one case with one expected verdict (`pytest.param` ids name the case); every refusal reason has a deny test
and the nearest allow test. Every expected value is a literal written from the rule text of the cards MW-007, MW-008,
MW-014 and MW-019, never computed by the code under test."""
import datetime

import pytest

import _engine  # noqa: F401  (puts the engine folder on the path)
from core_ask import (EditFacts, OutboxFacts, SearchFacts, StopFacts, decide_check_write, decide_edit, decide_search,
                      decide_stale_reminder, decide_stop)

DIR = "mkway/asks"
ASK = f"{DIR}/t_ask.md"
LOCK_SOURCES = "kind: lock\nchecked: commit lock closed\n"
FAR = "2099-01-01T10:00"
TOOLS = ["Write", "Edit", "MultiEdit"]


def ident(d):
    """The reason id of a refusal, else `allow`."""
    return d.reason if d.kind == "refuse" else "allow"


def ask_text(*, omit=(), **values):
    """The text of a complete ask: the question and the five field lines of the card MW-014."""
    base = {"default": "keep option A", "deadline": FAR, "blocked": "the report part", "reversible": "yes",
            "status": "open"}
    base.update(values)
    return "Which option?\n" + "".join(f"{k}: {v}\n" for k, v in base.items() if k not in omit)


COMPLETE = ask_text()
SHAPES = {"default": "default: <text or none>", "deadline": "deadline: <ISO local time or none>",
          "blocked": "blocked: <what waits, or none>", "reversible": "reversible: yes|no", "status": "status: open"}
IDENTITY = {"old_string": "status: open", "new_string": "status: open"}


def edit(rel=ASK, *, tool="Write", text=COMPLETE, sources_text=LOCK_SOURCES, sources=("ledger",), folder=DIR,
         session="s1", open_ids=(), max_open=1, exists=False, tool_allowed=False, tool_input="auto", **over):
    """The facts of one write of an ask. A Write carries `text`; an Edit or a MultiEdit leaves the file on disk as
    `text` says, by an edit that changes nothing."""
    if tool_input == "auto":
        if tool == "Write":
            tool_input = {"file_path": rel, "content": text}
        elif tool == "Edit":
            tool_input = {"file_path": rel, **IDENTITY}
        else:
            tool_input = {"file_path": rel, "edits": [IDENTITY]}
    return EditFacts(tool_name=tool, tool_input=tool_input, rel=rel, dir=folder, sources=tuple(sources),
                     max_open=max_open, tool_allowed=tool_allowed, session_id=session, sources_text=sources_text,
                     ask_text=text if tool != "Write" else "", ask_exists=exists, open_ids=tuple(open_ids), **over)


def sources_of(text, **kw):
    return decide_edit(edit(sources_text=text, **kw))


def names_all(d, lines):
    return all(line in d.text for line in lines)


def names_none(d, lines):
    return not any(line in d.text for line in lines)


# ---- which writes are the edit gate's ---------------------------------------------------------------------------------

@pytest.mark.parametrize("rel", [
    pytest.param("work/x.md", id="another-folder"), pytest.param("mkway/asks/t_check.md", id="a-file-that-is-not-an-ask"),
    pytest.param("mkway/asks/t_sources.md", id="the-sources-file-itself"),
    pytest.param("notes/t_ask.md", id="an-ask-name-in-another-folder"),
    pytest.param("mkway/asks/sub/t_ask.md", id="a-nested-folder"), pytest.param("mkway/asks/_ask.txt", id="wrong-suffix"),
    pytest.param("mkway/t_ask.md", id="the-parent-folder"), pytest.param(None, id="outside-the-root")])
def test_a_write_to_a_path_that_is_not_an_ask_is_allowed(rel):
    """Checks: only `<asks dir>/<name>_ask.md` is the gate's, and no sources file is needed for any other path; catches a gate that blocks the sources file or any other file (E4)."""
    assert ident(decide_edit(edit(rel, sources_text=None))) == "allow"


@pytest.mark.parametrize("tool", ["Read", "NotebookEdit", "Bash"])
def test_a_tool_that_does_not_write_is_allowed(tool):
    """Checks: only Write, Edit and MultiEdit are gated; catches a gate that refuses a read of an ask that has no sources (E4)."""
    assert ident(decide_edit(edit(tool=tool, sources_text=None))) == "allow"


@pytest.mark.parametrize("rel, tool_input", [pytest.param(None, {"content": "x"}, id="no-path"),
                                             pytest.param(ASK, None, id="no-tool-input-record")])
def test_a_write_with_no_path_or_no_input_record_is_allowed(rel, tool_input):
    """Checks: a call with no path, or a tool input that is not a record, is not an ask path; catches a gate that crashes or refuses on a call it cannot read (E4)."""
    assert ident(decide_edit(edit(rel, tool_input=tool_input, sources_text=None))) == "allow"


# ---- the sources file beside the ask ----------------------------------------------------------------------------------

@pytest.mark.parametrize("tool", TOOLS)
def test_an_ask_with_no_sources_file_is_refused_and_names_it(tool):
    """Catches: a session that asks without writing down what it checked; an ask with no `<name>_sources.md` beside it is refused ask-sources-missing by each write tool, and the text names the file (E5)."""
    d = decide_edit(edit(tool=tool, sources_text=None))
    assert d.kind == "refuse"
    assert d.reason == "ask-sources-missing"
    assert "t_sources.md" in d.text


@pytest.mark.parametrize("tool", TOOLS)
def test_an_ask_with_a_sources_file_of_a_kind_is_allowed(tool):
    """Checks: the nearest allow: the same ask with a sources file of a kind and its line passes by each write tool; catches a gate that refuses a complete ask (E5)."""
    assert ident(decide_edit(edit(tool=tool, sources_text=LOCK_SOURCES))) == "allow"


@pytest.mark.parametrize("text", [pytest.param("no kind here\n", id="no-kind-line"),
                                  pytest.param("kind: other\n", id="a-kind-of-no-rule")])
def test_a_sources_file_with_no_valid_kind_is_refused_and_names_the_kinds(text):
    """Catches: a sources file that proves nothing but is accepted; no kind line, or a kind that is none of the three, is refused ask-sources-kind and the text names the three kinds (E5)."""
    d = sources_of(text)
    assert d.kind == "refuse"
    assert d.reason == "ask-sources-kind"
    assert "kind: substance|session|lock" in d.text


@pytest.mark.parametrize("text, missing, present", [
    ("kind: substance\n", ["review: N contradictions", "> review: <verbatim quote>"], []),
    ("kind: substance\nreview: 2 contradictions\n", ["> review: <verbatim quote>"], ["review: N contradictions"]),
    ("kind: substance\n> review: :27 «a line»\n", ["review: N contradictions"], ["> review: <verbatim quote>"]),
    ("kind: substance\nreview: 0 contradictions\n> review:\n", ["> review: <verbatim quote>"], []),
    ("kind: substance\nreview: many contradictions\n> review: x\n", ["review: N contradictions"], []),
    ("kind: substance\nreview: 0 contradictions\n review: x\n", ["> review: <verbatim quote>"], []),
    ("kind: substance\nchecked: ListAgents\n", ["review: N contradictions"], []),
])
def test_substance_needs_a_count_line_and_a_quote_line(text, missing, present):
    """Catches: a count with no quote, a quote with no count, or an empty quote; substance needs `review: N contradictions` and a `> review: <verbatim>` line, and the refusal ask-sources-lines names each missing line and no line that is there (E6)."""
    d = sources_of(text, sources=("review",))
    assert d.kind == "refuse"
    assert d.reason == "ask-sources-lines"
    assert names_all(d, missing)
    assert names_none(d, present)


FULL = "kind: substance\nreview: 0 contradictions\n> review: :27 «a verbatim line of the source»\n"


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("text", [
    pytest.param(FULL, id="plain"), pytest.param(FULL.replace("0 contradictions", "1 contradiction"), id="one-contradiction"),
    pytest.param(FULL.replace("\n", "\r\n"), id="crlf"),
    pytest.param(FULL.replace("kind: substance", "Kind:  Substance"), id="cased-kind-line")])
def test_a_full_substance_sources_file_is_allowed(text, tool):
    """Checks: the nearest allow of the substance rows: the full file passes by each write tool, one contradiction counts as well as none, and a CRLF file and a cased Kind line count; catches a gate that refuses a complete file (E6)."""
    assert ident(sources_of(text, tool=tool, sources=("review",))) == "allow"


@pytest.mark.parametrize("text, line", [
    pytest.param("kind: session\n", "checked: ListAgents", id="session-no-line"),
    pytest.param("kind: session\nchecked: Other\n", "checked: ListAgents", id="session-other-checked"),
    pytest.param("kind: lock\n", "checked: <lock state>", id="lock-no-line"),
    pytest.param("kind: lock\nchecked:\n", "checked: <lock state>", id="lock-empty-state"),
    pytest.param("kind: lock\nchecked:   \nnext line\n", "checked: <lock state>", id="lock-blank-state")])
def test_a_session_or_lock_file_without_its_checked_line_is_refused(text, line):
    """Catches: a session ask that says it checked nothing, or a lock ask with an empty checked line; the refusal ask-sources-lines names the missing line (E7)."""
    d = sources_of(text)
    assert d.kind == "refuse"
    assert d.reason == "ask-sources-lines"
    assert line in d.text


@pytest.mark.parametrize("text", [
    pytest.param("kind: session\nchecked: ListAgents\n", id="session"),
    pytest.param("kind: session\nchecked: listagents 10:20\n", id="session-cased-with-text"),
    pytest.param("kind: lock\nchecked: commit lock closed since 10:00\n", id="lock")])
def test_a_session_or_lock_file_with_its_checked_line_is_allowed(text):
    """Checks: the nearest allow: checked: ListAgents in any case with anything after it, or checked: and a lock state, passes; catches a gate that refuses a complete session or lock file (E7)."""
    assert sources_of(text).kind == "allow"


MOVED = dict(folder="notes/asks", sources=("review", "canon"))
REVIEW = "kind: substance\nreview: 0 contradictions\n> review: :27 «a verbatim line of the source»\n"
CANON = "canon: 1 contradictions\n> canon: D-1 «a verbatim line»\n"


def test_the_default_folder_is_not_gated_when_the_profile_moves_it():
    """Checks: with owner_ask.dir moved an ask in the default folder is not an ask path; catches a folder hard-coded in the gate (E8)."""
    assert ident(decide_edit(edit("mkway/asks/t_ask.md", sources_text=None, **MOVED))) == "allow"


def test_the_moved_folder_is_gated():
    """Catches: a folder hard-coded in the gate; with owner_ask.dir moved an ask in the moved folder with no sources file is refused (E8)."""
    assert ident(decide_edit(edit("notes/asks/t_ask.md", sources_text=None, **MOVED))) == "ask-sources-missing"


def test_a_listed_source_that_is_missing_is_named_and_the_present_one_is_not():
    """Catches: a source name hard-coded in the gate; with sources review and canon listed and only review present, the refusal names the canon lines and not the review lines (E8)."""
    d = decide_edit(edit("notes/asks/t_ask.md", sources_text=REVIEW, **MOVED))
    assert d.reason == "ask-sources-lines"
    assert names_all(d, ["canon: N contradictions", "> canon: <verbatim quote>"])
    assert names_none(d, ["review: N contradictions", "> review: <verbatim quote>"])


def test_every_listed_source_present_is_allowed():
    """Checks: the nearest allow, both listed sources met, passes; catches a gate that asks for a source the profile does not list (E8)."""
    assert ident(decide_edit(edit("notes/asks/t_ask.md", sources_text=REVIEW + CANON, **MOVED))) == "allow"


def test_a_quote_of_another_source_does_not_stand_in_for_a_listed_one():
    """Catches: a quote line counted for the wrong source; a review quote line is no canon quote line (E8)."""
    d = decide_edit(edit("notes/asks/t_ask.md", sources_text=REVIEW + "canon: 1 contradictions\n> review: again\n",
                         **MOVED))
    assert d.reason == "ask-sources-lines"
    assert "> canon: <verbatim quote>" in d.text


def test_a_sources_file_that_cannot_be_read_is_refused_missing():
    """Catches: a gate that lets the ask through when it cannot read the proof; a sources file the shell could not read is ask-sources-missing (E9)."""
    assert ident(decide_edit(edit(sources_text=None))) == "ask-sources-missing"


def test_a_sources_file_that_is_not_text_is_refused_kind():
    """Catches: a gate that crashes on a hostile file, or accepts it; text with replacement characters and no kind line is ask-sources-kind (E9)."""
    assert ident(decide_edit(edit(sources_text="��\x00kind: substance\n"))) == "ask-sources-kind"


def test_a_failure_while_deciding_an_ask_path_fails_closed():
    """Catches: a gate that lets a write through because its own check failed; a tool input that breaks the decision on an ask path is a refusal (E9)."""
    d = decide_edit(edit(tool="Edit", tool_input={"file_path": ASK, "old_string": "x", "new_string": "y"},
                         text=object()))
    assert d.kind == "refuse"
    assert d.reason == "ask-sources-missing"
    assert "the sources check failed" in d.text


# ---- the ledger source ------------------------------------------------------------------------------------------------

HITS = "kind: substance\nledger: 2 hits\n> ledger: D-4 «a verbatim line of the ledger»\n"
ZERO = "kind: substance\nledger: 0 hits\nsearch: S-3\n"


@pytest.mark.parametrize("text, missing, present", [
    ("kind: substance\n", ["ledger: N hits"], []),
    ("kind: substance\nledger: 2 hits\n", ["> ledger: <verbatim quote>"], ["ledger: N hits"]),
    ("kind: substance\nledger: 2 hits\n> ledger:\n", ["> ledger: <verbatim quote>"], ["ledger: N hits"]),
    ("kind: substance\n> ledger: D-4 «a line»\n", ["ledger: N hits"], ["> ledger: <verbatim quote>"]),
    ("kind: substance\nledger: many hits\n> ledger: x\n", ["ledger: N hits"], []),
    ("kind: substance\nledger: 2 hits\nsearch: S-1\n", ["> ledger: <verbatim quote>"], ["ledger: N hits"]),
    ("kind: substance\nreview: 0 contradictions\n> review: x\n", ["ledger: N hits"], []),
])
def test_substance_with_hits_needs_the_count_and_a_ledger_quote(text, missing, present):
    """Catches: an ask that carries a ledger count with no ledger words behind it; by default substance needs the `ledger: N hits` line and, above 0, a `> ledger: <verbatim>` line, and the refusal ask-sources-lines names each missing line and no line that is there (E18)."""
    d = sources_of(text)
    assert d.kind == "refuse"
    assert d.reason == "ask-sources-lines"
    assert names_all(d, missing)
    assert names_none(d, present)


@pytest.mark.parametrize("text", [
    "kind: substance\nledger: 0 hits\n",
    "kind: substance\nledger: 0 hits\nsearch:\n",
    "kind: substance\nledger: 0 hits\n> ledger: x\n",
    "kind: substance\nledger: 0 hits\n search: S-3\n",
])
def test_zero_hits_need_a_search_record_line(text):
    """Catches: a zero count that nobody can check; `ledger: 0 hits` needs a `search: <record id>` line, and a ledger quote does not stand in for it (E19)."""
    d = sources_of(text)
    assert d.kind == "refuse"
    assert d.reason == "ask-sources-lines"
    assert "search: <record id>" in d.text
    assert names_none(d, ["ledger: N hits", "> ledger: <verbatim quote>"])


@pytest.mark.parametrize("text", [
    pytest.param(HITS, id="hits"), pytest.param(ZERO, id="zero-with-search"),
    pytest.param(HITS.replace("2 hits", "1 hit"), id="one-hit"),
    pytest.param(HITS.replace("ledger: 2 hits", "Ledger: 2 HITS"), id="cased"),
    pytest.param(ZERO.replace("\n", "\r\n"), id="crlf"),
    pytest.param(ZERO.replace("search: S-3", "Search: anything"), id="cased-search-line"),
    pytest.param("kind: session\nchecked: ListAgents\n", id="session-needs-no-ledger-line"),
    pytest.param("kind: lock\nchecked: commit lock closed\n", id="lock-needs-no-ledger-line")])
def test_a_full_ledger_sources_file_is_allowed(text):
    """Checks: the nearest allow of the ledger rows: both full forms pass, one hit as well as many, `hit` as well as `hits`, any case, CRLF; the session and lock kinds need no ledger line; catches a gate that refuses a complete file (E20)."""
    assert sources_of(text).kind == "allow"


def test_with_ledger_and_canon_listed_only_canon_is_named_missing():
    """Catches: a gate that turns every source into a ledger; with ledger and canon listed, the ledger lines met in their own form and the refusal names only the canon lines (E20)."""
    d = sources_of(HITS, sources=("ledger", "canon"))
    assert d.reason == "ask-sources-lines"
    assert names_all(d, ["canon: N contradictions", "> canon: <verbatim quote>"])
    assert "ledger" not in d.text.split("lacks", 1)[1].split(". ")[0]


def test_with_ledger_and_canon_listed_both_met_is_allowed():
    """Checks: the nearest allow: the ledger in its own form and canon in the contradictions form pass; catches a gate that refuses a file that meets every listed source (E20)."""
    assert sources_of(ZERO + CANON, sources=("ledger", "canon")).kind == "allow"


# ---- the five field lines, the open ask, the pop-up tool --------------------------------------------------------------

@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("field", list(SHAPES))
def test_a_missing_field_line_is_refused_and_named(field, tool):
    """Catches: an ask with no default or no deadline, which lets a session wait on the owner with nothing to fall back on; ask-fields-missing names that line and no line that is there (E1)."""
    d = decide_edit(edit(tool=tool, text=ask_text(omit=(field,))))
    assert d.kind == "refuse"
    assert d.reason == "ask-fields-missing"
    assert SHAPES[field] in d.text
    assert names_none(d, [s for f, s in SHAPES.items() if f != field])


def test_an_ask_with_no_field_names_all_five():
    """Catches: a gate that names only the first missing line, so the session fixes one line per refusal; a bare question is refused and names all five lines (E1)."""
    d = decide_edit(edit(text="Which option?\n"))
    assert d.reason == "ask-fields-missing"
    assert names_all(d, list(SHAPES.values()))


@pytest.mark.parametrize("line, field", [
    ("default:", "default"), ("default:   ", "default"), ("blocked:", "blocked"),
    ("deadline: tomorrow", "deadline"), ("deadline:", "deadline"), ("deadline: 2026-13-45T10:00", "deadline"),
    ("reversible: maybe", "reversible"), ("reversible:", "reversible"),
    ("status: answered", "status"), ("status: default-taken", "status"), ("status:", "status"),
])
def test_a_field_with_an_unusable_value_counts_as_missing(line, field):
    """Catches: a deadline no board can compare, or an ask written as already answered; a field with no value, a non-ISO deadline, a reversible that is not yes or no, or a status other than open counts as missing (E2)."""
    d = decide_edit(edit(text=ask_text(omit=(field,)) + f"{line}\n"))
    assert d.kind == "refuse"
    assert d.reason == "ask-fields-missing"
    assert SHAPES[field] in d.text


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("text", [
    pytest.param(COMPLETE, id="complete"),
    pytest.param(ask_text(default="none", deadline="none", blocked="none"), id="none-values"),
    pytest.param(ask_text(deadline="2099-01-01 10:00"), id="deadline-with-a-space"),
    pytest.param(ask_text(deadline="2099-01-01T10:00:30"), id="deadline-with-seconds"),
    pytest.param(ask_text(reversible="no"), id="reversible-no"),
    pytest.param(COMPLETE.replace("\n", "\r\n"), id="crlf"),
    pytest.param(COMPLETE.replace("default:", "Default:").replace("status:", "STATUS:"), id="cased-lines")])
def test_a_complete_ask_is_allowed(text, tool):
    """Checks: the nearest allow of the field rows: a complete ask passes by each write tool, any text or none after default and blocked, a none or ISO deadline with T or a space, reversible yes or no, status open, and CRLF and cased lines count; catches a gate that refuses a complete file (E3)."""
    assert ident(decide_edit(edit(tool=tool, text=text, session=None))) == "allow"


DISK = ask_text(omit=("blocked",))
KEEP = {"file_path": ASK, "old_string": "reversible: yes", "new_string": "reversible: no"}
ADD = {"file_path": ASK, "old_string": "reversible: yes", "new_string": "reversible: yes\nblocked: the part"}
CLOSE = {"file_path": ASK, "old_string": "status: open", "new_string": "status: answered"}


@pytest.mark.parametrize("tool, tool_input, disk, shape", [
    pytest.param("Edit", KEEP, DISK, "blocked", id="an-edit-that-leaves-the-missing-line-out"),
    pytest.param("Edit", CLOSE, COMPLETE, "status", id="an-edit-that-closes-the-status"),
])
def test_an_edit_that_leaves_the_ask_incomplete_is_refused_and_named(tool, tool_input, disk, shape):
    """Catches: a gate that reads only the replaced text, or only the old file; an Edit that leaves a field out or turns `status: open` into another status is refused and the line named (E3)."""
    d = decide_edit(edit(tool=tool, tool_input=tool_input, text=disk, exists=True))
    assert d.reason == "ask-fields-missing"
    assert SHAPES[shape] in d.text


@pytest.mark.parametrize("tool, tool_input", [
    pytest.param("Edit", ADD, id="an-edit-that-adds-the-missing-line"),
    pytest.param("MultiEdit", {"file_path": ASK, "edits": [ADD]}, id="a-multiedit-that-adds-it"),
    pytest.param("MultiEdit", {"file_path": ASK, "edits": [ADD, KEEP]}, id="edits-apply-in-order")])
def test_an_edit_that_completes_the_ask_is_allowed(tool, tool_input):
    """Checks: the nearest allow: an Edit or MultiEdit that adds the missing line passes though the file on disk lacked it, edits applying in order; catches a gate that judges the old file instead of the file the write leaves (E3)."""
    assert decide_edit(edit(tool=tool, tool_input=tool_input, text=DISK, exists=True)).kind == "allow"


def test_the_sources_check_decides_before_the_fields():
    """Catches: a fields check that hides the sources refusal; with no sources file and no fields the refusal is ask-sources-missing (E3)."""
    assert decide_edit(edit(text="x", sources_text=None)).reason == "ask-sources-missing"


@pytest.mark.parametrize("rel", ["mkway/asks/t_sources.md", "mkway/asks/t_check.md", "work/x.md"])
def test_a_write_that_is_not_an_ask_path_needs_no_fields(rel):
    """Checks: the nearest allow: a write that is not an ask path needs no fields; catches a fields check that gates a sources file (E3)."""
    assert ident(decide_edit(edit(rel, text="x"))) == "allow"


def test_a_second_open_ask_by_the_same_session_is_refused():
    """Catches: one session that leaves five asks open and repeats one; while one ask of the session has status open, a new ask by that session is refused ask-already-open and the text says to add to the open ask or wait (E4)."""
    d = decide_edit(edit("mkway/asks/u_ask.md", open_ids=("t",)))
    assert d.kind == "refuse"
    assert d.reason == "ask-already-open"
    assert names_all(d, ["add to the open ask", "wait"])
    assert "t" in d.text


def test_a_session_with_no_open_ask_may_ask():
    """Checks: the nearest allow: the same new ask by a session with no open ask passes; catches a session blocked by another session's ask (E4)."""
    assert ident(decide_edit(edit("mkway/asks/u_ask.md", open_ids=()))) == "allow"


@pytest.mark.parametrize("tool", ["Edit", "Write"])
def test_a_write_to_the_open_ask_itself_is_allowed(tool):
    """Checks: a write to an ask already on disk is an addition to it, not a second ask; catches a session that cannot add to its own open ask (E4)."""
    assert ident(decide_edit(edit(ASK, tool=tool, open_ids=("t",), exists=True))) == "allow"


def test_the_open_limit_of_the_profile_lets_the_second_ask_through():
    """Checks: owner_ask.max_open 2 lets a session with one open ask write a second; catches a limit that is hard-coded (E4)."""
    assert ident(decide_edit(edit("mkway/asks/u_ask.md", open_ids=("t",), max_open=2))) == "allow"


def test_the_open_limit_of_the_profile_refuses_the_third_ask():
    """Catches: a limit that is hard-coded; owner_ask.max_open 2 refuses a session with two open asks (E4)."""
    assert decide_edit(edit("mkway/asks/v_ask.md", open_ids=("t", "u"), max_open=2)).reason == "ask-already-open"


def test_a_call_with_no_session_id_is_never_refused_by_the_open_rule():
    """Checks: with no session id the one-open rule does not apply; catches a crash or a refusal on a call with no session (E4)."""
    assert ident(decide_edit(edit("mkway/asks/u_ask.md", open_ids=("t",), session=None))) == "allow"


def test_a_failure_reading_the_open_asks_refuses_a_new_ask():
    """Catches: a new ask let through because the open rule could not be checked; when the shell could not read the session's open asks, a new ask is refused with the failure named (E4)."""
    d = decide_edit(edit("mkway/asks/u_ask.md", open_error="OSError"))
    assert d.kind == "refuse"
    assert d.reason == "ask-sources-missing"
    assert "(OSError)" in d.text


def test_a_failure_reading_the_open_asks_does_not_matter_for_an_ask_on_disk():
    """Checks: the nearest allow: a write to an ask already on disk does not need the open asks; catches a gate that refuses an addition to an ask because of a failure it did not need (E4)."""
    assert ident(decide_edit(edit(ASK, open_error="OSError", exists=True))) == "allow"


def test_the_pop_up_question_tool_is_refused_with_the_file_route():
    """Catches: a session that stops the work on a pop-up nobody sees; AskUserQuestion is refused ask-tool-off and the text names the file route, the asks folder, the `_ask.md` file and its fields (E5)."""
    d = decide_edit(edit(tool="AskUserQuestion", tool_input={"questions": []}))
    assert d.kind == "refuse"
    assert d.reason == "ask-tool-off"
    assert names_all(d, ["mkway/asks/<name>_ask.md", "default", "deadline"])


def test_the_pop_up_question_tool_is_allowed_when_the_profile_allows_it():
    """Checks: the nearest allow: `owner_ask.tool_allowed: true` lets the pop-up through; catches a switch that does nothing (E5)."""
    assert decide_edit(edit(tool="AskUserQuestion", tool_input={}, tool_allowed=True)).kind == "allow"


@pytest.mark.parametrize("tool", ["Bash", "Read", "Task"])
def test_a_tool_other_than_the_pop_up_is_untouched_by_the_tool_switch(tool):
    """Checks: no other tool is touched by the pop-up rule; catches a tool switch that refuses every tool (E5)."""
    assert decide_edit(edit(None, tool=tool, tool_input={"command": "x"})).kind == "allow"


# ---- the stop gate ----------------------------------------------------------------------------------------------------

USER = {"type": "user", "message": {"content": "a question"}}
TOOL_RESULT_USER = {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}
TEXT_BLOCK_USER = {"type": "user", "message": {"content": [{"type": "text", "text": "and then?"}]}}


def said(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def tool(name, path):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name,
                                                          "input": {"file_path": path, "content": "x"}}]}}


def wrote(name="t", tool_name="Write"):
    return tool(tool_name, f"{DIR}/{name}_ask.md")


def written_paths(entries):
    found = set()
    for entry in entries or ():
        content = entry.get("message", {}).get("content")
        for block in content if isinstance(content, list) else ():
            if block.get("type") == "tool_use":
                found.add(block["input"]["file_path"])
    return found


def stop(entries, last=None, *, active=False, markers=("Request:",), folder=DIR, on_disk=(ASK,)):
    """The facts of one Stop: a path in the transcript reads as itself (the shell's reading of paths is its own test)."""
    return decide_stop(StopFacts(
        hook_active=active, last_message=last, entries=None if entries is None else tuple(entries),
        markers=tuple(markers), dir=folder, rels={p: p for p in written_paths(entries)}, on_disk=frozenset(on_disk)))


ASKED = said("Request: yes or no?")
NOTES = dict(markers=("Ask:", "Q:"), folder="notes/asks", on_disk=("notes/asks/t_ask.md", ASK))


@pytest.mark.parametrize("entries, last, kw", [
    pytest.param([USER, said("Info: done.")], None, {}, id="no-marker-in-the-last-text"),
    pytest.param([USER], "See the Request: above.", {}, id="marker-in-the-middle-of-a-line"),
    pytest.param([USER], "no ask here\nsecond line", {}, id="no-marker-line"),
    pytest.param([USER], "", {}, id="empty-reply"),
    pytest.param([USER, wrote(), ASKED], None, {}, id="ask-written-this-turn"),
    pytest.param([USER, wrote(tool_name="Edit"), ASKED], None, {}, id="ask-edited-this-turn"),
    pytest.param([USER, wrote(tool_name="MultiEdit"), ASKED], None, {}, id="ask-multiedited-this-turn"),
    pytest.param([USER, wrote(), TOOL_RESULT_USER, ASKED], None, {}, id="a-tool-result-is-not-a-user-message"),
    pytest.param([USER, wrote()], "Request: x", {}, id="the-hook-gives-the-last-message"),
    pytest.param([USER, said("Request: first"), said("Info: last")], None, {}, id="the-last-text-is-the-reply"),
    pytest.param([USER, said("Request: x")], None, {"active": True}, id="stop-hook-active"),
    pytest.param([USER], "Request: x", NOTES, id="the-default-marker-is-no-marker-when-the-profile-lists-others"),
    pytest.param([USER, tool("Write", "notes/asks/t_ask.md")], "Q: x", NOTES, id="ask-written-in-the-moved-folder"),
    pytest.param(None, "Info: x", {}, id="unreadable-transcript-no-marker"),
    pytest.param(None, None, {}, id="unreadable-transcript-no-message"),
])
def test_a_final_reply_that_may_go_to_the_owner_is_allowed(entries, last, kw):
    """Checks: the nearest allow of the stop rows: a reply with no marker passes whatever the turn did; a marker passes when this turn, after the last real user message, wrote an ask file that is on disk; with `stop_hook_active` it never blocks; catches a gate that blocks ordinary replies or traps a session in a loop (E11)."""
    assert ident(stop(entries, last, **kw)) == "allow"


@pytest.mark.parametrize("entries, last, kw", [
    pytest.param([USER, ASKED], None, {}, id="no-ask-file"),
    pytest.param([wrote(), USER, ASKED], None, {}, id="ask-written-before-the-user-message"),
    pytest.param([USER, wrote(), TEXT_BLOCK_USER, ASKED], None, {}, id="a-text-block-is-a-user-message"),
    pytest.param([USER], "**Request:** x", {}, id="marker-after-bold"),
    pytest.param([USER], "  Request: x", {}, id="marker-after-spaces"),
    pytest.param([USER], "First line.\nRequest: x\nlast line", {}, id="marker-on-a-later-line"),
    pytest.param([USER, said("Info: first"), said("Request: last")], None, {}, id="marker-in-the-last-text"),
    pytest.param([USER, wrote(tool_name="Read"), ASKED], None, {}, id="a-read-is-no-write"),
    pytest.param([USER, tool("Write", "notes/t_ask.md"), ASKED], None, {"on_disk": (ASK, "notes/t_ask.md")},
                 id="an-ask-name-in-another-folder"),
    pytest.param([USER, tool("Write", "mkway/asks/t_check.md"), ASKED], None,
                 {"on_disk": (ASK, "mkway/asks/t_check.md")}, id="a-file-that-is-not-an-ask"),
    pytest.param([USER, tool("Write", "mkway/asks/t_sources.md"), ASKED], None,
                 {"on_disk": (ASK, "mkway/asks/t_sources.md")}, id="the-sources-file"),
    pytest.param([USER, tool("Write", "mkway/asks/sub/t_ask.md"), ASKED], None,
                 {"on_disk": (ASK, "mkway/asks/sub/t_ask.md")}, id="a-nested-folder"),
    pytest.param([USER, wrote("gone"), ASKED], None, {}, id="the-ask-file-is-not-on-disk"),
    pytest.param([USER], "Ask: x", NOTES, id="a-listed-marker"),
    pytest.param([USER], "Q: x", NOTES, id="another-listed-marker"),
    pytest.param([USER, tool("Write", ASK)], "Q: x", NOTES, id="ask-written-outside-the-moved-folder"),
    pytest.param(None, "Request: x", {}, id="unreadable-transcript-with-a-marker"),
])
def test_a_final_reply_with_a_marker_and_no_ask_written_is_blocked(entries, last, kw):
    """Catches: an ask that goes to the owner with no ask file, or an old or look-alike file that covers a new ask; a reply with a marker line is blocked ask-not-written unless this turn wrote the ask file, and an ask written before the last user message, a read, another file or folder, a file not on disk, or an unreadable transcript do not count (E11)."""
    d = stop(entries, last, **kw)
    assert d.kind == "refuse"
    assert d.reason == "ask-not-written"


def test_the_block_names_the_marker_and_the_asks_folder():
    """Catches: a block that does not say what to write; the refusal names the marker found and `mkway/asks/<name>_ask.md` (E11)."""
    d = stop([USER, ASKED])
    assert names_all(d, ["Request:", "mkway/asks/<name>_ask.md"])
    assert "transcript could not be read" not in d.text


def test_the_block_of_an_unreadable_transcript_says_so():
    """Catches: a block that hides why no write could be seen; with no readable transcript the text says the transcript could not be read (E14)."""
    assert "transcript could not be read" in stop(None, "Request: x").text


def test_the_block_names_the_moved_folder():
    """Catches: a folder hard-coded in the text; with owner_ask.dir moved the refusal names the moved folder (E13)."""
    assert "notes/asks/<name>_ask.md" in stop([USER], "Ask: x", **NOTES).text


# ---- the search gate --------------------------------------------------------------------------------------------------

BASE = datetime.datetime(2026, 11, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
PATTERNS = ["notes/questions/**", "mkway/q_*.md"]
SEARCH_TEXT = "run `mkway search <words>` first, then ask"
QUESTION = "notes/questions/q1.md"


def at(seconds):
    return (BASE + datetime.timedelta(seconds=seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def user(seconds, content="a question"):
    return {"type": "user", "message": {"content": content}, "timestamp": at(seconds)}


def tool_result(seconds):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}, "timestamp": at(seconds)}


def working(seconds):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": "working"}]}, "timestamp": at(seconds)}


def record(seconds, *, session="s1", kind="search", value="S-1"):
    return {"session_id": session, "kind": kind, "value": value, "time": at(seconds).replace("Z", "+00:00"),
            "by": "session"}


def question(entries, *rows, tool_name="AskUserQuestion", tool_input="none", rel=None, session="s1",
             patterns=tuple(PATTERNS), **over):
    return decide_search(SearchFacts(
        tool_name=tool_name, tool_input={"questions": []} if tool_input == "none" else tool_input,
        patterns=list(patterns) if patterns is not None else None, rel=rel, session_id=session,
        entries=None if entries is None else tuple(entries), rows=tuple(rows), **over))


def sid(d):
    return d.reason if d.kind != "allow" else "allow"


TURN = [user(0), working(10), tool_result(25), working(26), tool_result(40)]


@pytest.mark.parametrize("entries, rows", [
    pytest.param([user(0), working(10)], [record(30)], id="a-search-after-the-user-message"),
    pytest.param(TURN, [record(20)], id="tool-results-are-not-user-messages"),
    pytest.param([working(5)], [record(-30)], id="no-user-message-in-the-transcript"),
])
def test_a_question_after_a_search_of_this_turn_is_allowed(entries, rows):
    """Checks: the nearest allow of the search rows: a search record of this session after the last real user message passes; a tool result is not a user message, and with no user message any record of the session counts; catches a gate that blocks a question that was searched (E12)."""
    assert sid(question(entries, *rows)) == "allow"


@pytest.mark.parametrize("entries, rows", [
    pytest.param([user(0), working(10)], [], id="no-record"),
    pytest.param([user(0), working(10)], [record(20, kind="take", value="CARD-001")], id="a-record-of-another-kind"),
    pytest.param([user(0), working(5)], [record(-30)], id="a-search-before-the-user-message"),
    pytest.param([user(0), working(5)], [record(30, session="other")], id="a-search-of-another-session"),
    pytest.param(TURN + [user(100, [{"type": "text", "text": "next question"}])], [record(20)],
                 id="a-new-user-message-after-the-search"),
])
def test_a_question_with_no_search_of_this_turn_is_refused(entries, rows):
    """Catches: a question that goes to the owner before any search, or a search of an earlier turn that lets this turn's question through; AskUserQuestion with no search record of this session after the last real user message is refused search-missing, and other record kinds, earlier turns or other sessions do not count (E12)."""
    assert sid(question(entries, *rows)) == "search-missing"


def test_the_search_refusal_says_to_search_first():
    """Catches: a refusal that does not say what to do; the text says to run `mkway search <words>` first, then ask (E12)."""
    assert SEARCH_TEXT in question([user(0)]).text


@pytest.mark.parametrize("tool_name", TOOLS)
@pytest.mark.parametrize("path", [QUESTION, "notes/questions/sub/q1.md", "mkway/q_a.md"])
def test_a_write_to_a_question_file_with_no_search_is_refused(path, tool_name):
    """Catches: a question file written with no search; a Write, Edit or MultiEdit of a path that matches a glob of `questions.files` is gated like the question (E14)."""
    d = question([user(0)], tool_name=tool_name, tool_input={"file_path": path, "content": "x"}, rel=path)
    assert d.kind == "refuse"
    assert d.reason == "search-missing"


def test_a_write_to_a_question_file_after_a_search_is_allowed():
    """Checks: the nearest allow: the same write with a search record of this turn passes; catches a gate that blocks every write to a question file (E14)."""
    d = question([user(0)], record(10), tool_name="Write", tool_input={"file_path": QUESTION}, rel=QUESTION)
    assert sid(d) == "allow"


@pytest.mark.parametrize("path", ["notes/other.md", "mkway/asks/t_ask.md", "mkway/q.md", "src/questions/q1.md"])
def test_a_write_to_a_path_that_matches_no_glob_is_allowed(path):
    """Checks: a write to a path that matches no `questions.files` glob passes; catches a gate that blocks every write (E14)."""
    assert sid(question([user(0)], tool_name="Write", tool_input={"file_path": path}, rel=path)) == "allow"


def test_a_read_of_a_question_file_is_allowed():
    """Checks: a tool that does not write is not gated; catches a gate that blocks a read of a question file (E14)."""
    assert sid(question([user(0)], tool_name="Read", tool_input={"file_path": QUESTION}, rel=QUESTION)) == "allow"


def test_a_write_with_no_tool_input_is_allowed():
    """Checks: a Write with no tool input is not a gated path; catches a gate that crashes on a call it cannot read (E14)."""
    assert sid(question([user(0)], tool_name="Write", tool_input=None, rel=QUESTION)) == "allow"


def test_with_no_question_files_in_the_profile_no_write_is_gated():
    """Checks: with no `questions.files` a write to any path passes; catches a gate that invents a path of its own (E14)."""
    d = question([user(0)], tool_name="Write", tool_input={"file_path": QUESTION}, rel=QUESTION, patterns=None)
    assert sid(d) == "allow"


def test_with_no_question_files_in_the_profile_the_question_tool_is_still_gated():
    """Catches: a profile with no files that turns the search gate off for questions; AskUserQuestion is gated whatever the profile lists (E14)."""
    assert sid(question([user(0)], patterns=None)) == "search-missing"


@pytest.mark.parametrize("entries, session, why", [
    pytest.param(None, "s1", "the transcript cannot be read", id="no-transcript"),
    pytest.param([{"type": "user", "message": {"content": "a question"}}], "s1", "the last user message has no time",
                 id="a-user-message-with-no-time"),
    pytest.param([user(0)], None, "the hook input has no session id", id="no-session-id"),
])
def test_an_unreadable_turn_boundary_is_a_log_row_never_a_refusal(entries, session, why):
    """Checks: when the turn boundary cannot be established the gate allows and returns a log verdict search-unverified that says why, and never blocks a question on its own failed reading (E15)."""
    d = question(entries, record(30), session=session)
    assert d.kind == "log"
    assert d.reason == "search-unverified"
    assert why in d.text


def test_a_failure_reading_the_records_is_a_log_row_that_names_it():
    """Catches: a gated call refused for a reading failure of the gate's own; the verdict is search-unverified and names the failure (E15)."""
    d = question([user(0)], rows_error="OSError")
    assert d.kind == "log"
    assert d.reason == "search-unverified"
    assert "OSError" in d.text


# ---- the outbox check write gate --------------------------------------------------------------------------------------

OUT = "outbox"
SUFFIX = ".check.md"
RIGHT = "0123456789abcdef" * 4
WRONG = "0" * 64
CHECK = f"{OUT}/a.md{SUFFIX}"


def check_text(sha, *, omit=(), extra=""):
    values = {"sha256": f"sha256: {sha}", "numbers": "numbers: 12 checked, 0 contradictions",
              "claims": "claims: 7 checked, 0 overstated, 0 without basis", "patterns": "patterns: clean",
              "links": "links: clean", "checker": "checker: critic"}
    return "\n".join(v for k, v in values.items() if k not in omit) + "\n" + extra


def check(rel=CHECK, *, tool="Write", content=None, disk="", old=None, new=None, edits=(), doc_sha=RIGHT, folder=OUT,
          **over):
    """The facts of one write of a check file; an Edit or a MultiEdit is applied to the check file on disk (`disk`)."""
    if tool == "Write":
        tool_input = {"file_path": rel, "content": content}
    elif tool == "Edit":
        tool_input = {"file_path": rel, "old_string": old, "new_string": new}
    else:
        tool_input = {"file_path": rel, "edits": [{"old_string": o, "new_string": n} for o, n in edits]}
    return decide_check_write(OutboxFacts(tool_name=tool, tool_input=tool_input, rel=rel, dir=folder, suffix=SUFFIX,
                                          doc_sha=doc_sha, check_text=disk, **over))


GOOD = check_text(RIGHT)
BAD = check_text(WRONG)


@pytest.mark.parametrize("kw", [
    pytest.param(dict(content=BAD), id="write-with-a-wrong-sha"),
    pytest.param(dict(tool="Edit", disk=BAD, old="links: clean", new="links: clean"), id="edit-of-a-wrong-check"),
    pytest.param(dict(tool="MultiEdit", disk=BAD, edits=[("links: clean", "links: clean")]),
                 id="multiedit-of-a-wrong-check"),
    pytest.param(dict(tool="Edit", disk=GOOD, old=f"sha256: {RIGHT}", new=f"sha256: {WRONG}"),
                 id="edit-that-changes-a-right-sha-to-a-wrong-one"),
    pytest.param(dict(content=check_text(WRONG, omit=("sha256",))), id="no-sha-line"),
    pytest.param(dict(content=GOOD + f"sha256: {WRONG}\n"), id="one-right-line-and-one-wrong-line"),
    pytest.param(dict(content=check_text("abc123")), id="a-short-digest"),
    pytest.param(dict(rel=f"{OUT}/sub/b.md{SUFFIX}", content=BAD), id="a-nested-check"),
    pytest.param(dict(content=GOOD, doc_sha=None), id="the-document-does-not-exist"),
    pytest.param(dict(content=GOOD, error="OSError"), id="the-shell-could-not-read-the-document"),
])
def test_a_write_that_leaves_a_check_with_no_right_sha_is_refused(kw):
    """Catches: a check written for text that has changed, a forged check that hides a wrong digest, or a check written ahead of its text; a write that leaves no right sha is refused check-sha-mismatch, and a missing or unreadable document fails closed (E10)."""
    d = check(**kw)
    assert d.kind == "refuse"
    assert d.reason == "check-sha-mismatch"


@pytest.mark.parametrize("kw", [
    pytest.param(dict(content=GOOD), id="write-with-the-right-sha"),
    pytest.param(dict(content=check_text(RIGHT.upper(), extra="numbers: 1 checked, 5 contradictions\n")),
                 id="the-sha-in-capitals-and-other-lines-unjudged"),
    pytest.param(dict(tool="Edit", disk=GOOD, old="links: clean", new="links: clean, 3 links"), id="edit-keeping-the-sha"),
    pytest.param(dict(tool="MultiEdit", disk=GOOD, edits=[("links: clean", "links: clean"), ("claims", "claims")]),
                 id="multiedit-keeping-the-sha"),
    pytest.param(dict(tool="Edit", disk=GOOD, old="no such text", new="x"), id="edit-whose-old-text-is-not-found"),
    pytest.param(dict(tool="Edit", disk=BAD, old=f"sha256: {WRONG}", new=f"sha256: {RIGHT}"),
                 id="edit-that-mends-a-wrong-sha"),
    pytest.param(dict(tool="MultiEdit", disk=BAD, edits=[(f"sha256: {WRONG}", f"sha256: {RIGHT}")]),
                 id="multiedit-that-mends-a-wrong-sha"),
])
def test_a_write_that_leaves_a_check_with_the_right_sha_is_allowed(kw):
    """Checks: the nearest allow: the same write with the document's sha256 passes by each write tool; a sha in capitals is the same sha, the other lines are not judged, and an Edit is judged on the file it leaves, so one that mends a wrong sha passes; catches a gate that refuses a good check, reads the case of the digits, or judges the tool input (E10)."""
    assert check(**kw).kind == "allow"


@pytest.mark.parametrize("kw, wanted", [
    pytest.param(dict(content=BAD), ["sha256: " + RIGHT, "mkway outbox", "a.md"], id="a-wrong-sha-names-the-line-to-write"),
    pytest.param(dict(content=check_text(WRONG, omit=("sha256",))), ["sha256: "], id="no-sha-line-names-the-line"),
    pytest.param(dict(rel=f"{OUT}/none.md{SUFFIX}", content=BAD, doc_sha=None), [f"{OUT}/none.md"],
                 id="a-missing-document-is-named"),
    pytest.param(dict(content=GOOD, error="OSError"), ["(OSError)"], id="a-failure-is-named"),
])
def test_the_refusal_text_says_what_to_write(kw, wanted):
    """Catches: a refusal that does not say how to mend the check; it gives the line to write, names `mkway outbox`, the missing document, or the failure (E10)."""
    assert names_all(check(**kw), wanted)


@pytest.mark.parametrize("kw", [
    pytest.param(dict(rel=f"{OUT}/a.md", content="new text\n"), id="the-document-itself"),
    pytest.param(dict(rel=f"notes/a.md{SUFFIX}", content=BAD), id="a-check-name-in-another-folder"),
    pytest.param(dict(rel=f"{OUT}/readme.txt", content="x"), id="a-file-that-is-not-a-check"),
    pytest.param(dict(content=BAD, folder=None), id="a-profile-with-no-outbox-dir"),
    pytest.param(dict(rel=f"{OUT}/a.md", content="x", error="OSError"), id="a-failure-on-a-file-that-is-not-a-check"),
])
def test_a_write_that_is_not_a_check_file_is_allowed(kw):
    """Checks: the document itself, a check-suffixed file in another folder, a non-check file under outbox and a profile with no outbox.dir all pass; catches a gate that refuses writes it has no rule for (E10)."""
    assert check(**kw).kind == "allow"


def test_a_tool_that_does_not_write_is_not_the_outbox_gates():
    """Checks: a tool that is not a write tool passes; catches a gate that refuses a read of a check (E10)."""
    f = OutboxFacts(tool_name="Bash", tool_input={"command": "echo x"}, rel=None, dir=OUT, suffix=SUFFIX, doc_sha=RIGHT)
    assert decide_check_write(f).kind == "allow"


@pytest.mark.parametrize("stale, first, kind", [
    pytest.param((f"{OUT}/b.md",), True, "warn", id="a-stale-file-the-first-time"),
    pytest.param((f"{OUT}/b.md",), False, "allow", id="a-stale-file-again"),
    pytest.param((), True, "allow", id="no-stale-file-the-first-time"),
    pytest.param((), False, "allow", id="no-stale-file-again"),
])
def test_the_stop_reminder_warns_only_for_a_stale_file_the_first_time(stale, first, kind):
    """Catches: a reminder that nags every turn or reminds about nothing, or a Stop gate that blocks; a stale check warns once for the set and never refuses, and no stale file or the same set again gives none, all four combinations of the two facts (E15)."""
    assert decide_stale_reminder(stale, first).kind == kind


def test_the_stop_reminder_names_each_stale_file_and_the_board_command():
    """Catches: a changed text that leaves the turn unremarked; the warn is outbox-changed-after-check and names each stale file and `mkway outbox`, and no other file (E15)."""
    d = decide_stale_reminder((f"{OUT}/b.md", f"{OUT}/c.md"), True)
    assert d.reason == "outbox-changed-after-check"
    assert names_all(d, [f"{OUT}/b.md, {OUT}/c.md", "mkway outbox"])
    assert f"{OUT}/a.md" not in d.text
