"""The owner-ask edit gate with the ledger source (card MW-008, part 4): `kind: substance` needs the ledger count and a
ledger quote, or a zero count and the search record. Synthetic task roots only; no task data. The gate module is
imported inside each test, so a missing module fails that test and not the collection of the file."""
import importlib

import pytest

from _engine import gate_call, task_root
import _mw014

HITS = "kind: substance\nledger: 2 hits\n> ledger: D-4 «a verbatim line of the ledger»\n"
ZERO = "kind: substance\nledger: 0 hits\nsearch: S-3\n"


def _gate():
    return importlib.import_module("gate_owner_ask")


def _pre(root, tool="Write"):
    # changed by MW-014 (E3): the write carries a complete ask, so these rows stay about the sources lines
    return gate_call(_gate().check, root, tool=tool,
                     tool_input=_mw014.tool_input(root, "mkway/asks/t_ask.md", tool))


def _sources(root, text):
    folder = root / "mkway" / "asks"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "t_sources.md").write_text(text, encoding="utf-8", newline="")


@pytest.fixture
def task(tmp_path):
    return task_root(tmp_path)


@pytest.mark.parametrize("text, missing, present", [
    ("kind: substance\n", ["ledger: N hits"], []),
    ("kind: substance\nledger: 2 hits\n", ["> ledger: <verbatim quote>"], ["ledger: N hits"]),
    ("kind: substance\nledger: 2 hits\n> ledger:\n", ["> ledger: <verbatim quote>"], ["ledger: N hits"]),
    ("kind: substance\n> ledger: D-4 «a line»\n", ["ledger: N hits"], ["> ledger: <verbatim quote>"]),
    ("kind: substance\nledger: many hits\n> ledger: x\n", ["ledger: N hits"], []),
    ("kind: substance\nledger: 2 hits\nsearch: S-1\n", ["> ledger: <verbatim quote>"], ["ledger: N hits"]),
    ("kind: substance\nreview: 0 contradictions\n> review: x\n", ["ledger: N hits"], []),
])
def test_substance_with_hits_needs_the_count_and_a_ledger_quote(task, text, missing, present):
    """E18 (part 4): by default `kind: substance` needs the line `ledger: N hits` and, when N is above 0, at least one
    `> ledger: <verbatim>` line (`> ledger:` with nothing after the colon is no quote; a search line is no quote); the
    refusal `ask-sources-lines` names each missing line and no line that is there; the old `review` lines are not the
    default's. Catches: an ask that carries a ledger count with no ledger words behind it."""
    _sources(task, text)
    v = _pre(task)
    assert v.kind == "refuse" and v.reason_id == "ask-sources-lines"
    for line in missing:
        assert line in v.message, line
    for line in present:
        assert line not in v.message, line


@pytest.mark.parametrize("text", [
    "kind: substance\nledger: 0 hits\n",
    "kind: substance\nledger: 0 hits\nsearch:\n",
    "kind: substance\nledger: 0 hits\n> ledger: x\n",
    "kind: substance\nledger: 0 hits\n search: S-3\n",
])
def test_zero_hits_need_a_search_record_line(task, text):
    """E19 (part 4): `ledger: 0 hits` needs a line `search: <record id>` (any text after the colon); a ledger quote
    does not stand in for it, and the refusal names that line only. Catches: a zero count that nobody can check."""
    _sources(task, text)
    v = _pre(task)
    assert v.kind == "refuse" and v.reason_id == "ask-sources-lines"
    assert "search: <record id>" in v.message
    assert "ledger: N hits" not in v.message and "> ledger: <verbatim quote>" not in v.message


def test_a_full_ledger_sources_file_lets_the_ask_through(task, tmp_path):
    """E20 (part 4): both full forms allow the ask by every write tool (one hit counts as well as many, `hit` as well
    as `hits`, any case, CRLF); the session and lock kinds need no ledger line; with `sources: [ledger, canon]` the
    ledger lines are met in their own form and `canon` keeps `canon: N contradictions` and its quote line, and the
    refusal names only canon. Catches: a gate that refuses a complete file, or that turns every source into a ledger."""
    for text in (HITS, ZERO, HITS.replace("2 hits", "1 hit"), HITS.replace("ledger: 2 hits", "Ledger: 2 HITS"),
                 ZERO.replace("\n", "\r\n"), ZERO.replace("search: S-3", "Search: anything")):
        _sources(task, text)
        for tool in ("Write", "Edit", "MultiEdit"):
            assert _pre(task, tool).kind == "allow", (text, tool)
    for text in ("kind: session\nchecked: ListAgents\n", "kind: lock\nchecked: commit lock closed\n"):
        _sources(task, text)
        assert _pre(task).kind == "allow", text
    two = task_root(tmp_path / "two", owner_ask={"sources": ["ledger", "canon"]})
    _sources(two, HITS)
    v = _pre(two)
    assert v.reason_id == "ask-sources-lines"
    assert "canon: N contradictions" in v.message and "> canon: <verbatim quote>" in v.message
    assert "ledger" not in v.message.split("lacks", 1)[1].split(". ")[0]
    _sources(two, ZERO + "canon: 1 contradictions\n> canon: D-1 «a verbatim line»\n")
    assert _pre(two).kind == "allow"
