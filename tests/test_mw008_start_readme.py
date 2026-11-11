"""The start block lines, the README section and the KEYS lines of the decision ledger (card MW-008, parts 5 and 6).
Synthetic task roots only; no task data."""
import importlib
import json
import re

import pytest

from _engine import REPO, task_root
from _keys_md import section_rows, unquote
import dispatch
import startline

ENV = {"CLAUDECODE": "1"}
HEADING = "## Decisions: search before asking"
NOW = "in schema now"


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _block(root, profile=None):
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    return startline.render(root, root / "mkway" / "profile.json", profile if profile is not None else _profile(root),
                            [], manifest, ENV, session="s1")


def _line(block, prefix):
    (line,) = [x for x in block.splitlines() if x.startswith(prefix)]
    return line


def _names(line):
    return [n.strip() for n in line.split(":", 1)[1].split(";")[0].split(",") if n.strip() and n.strip() != "none"]


def test_the_start_block_names_the_search_gate_on_and_off(tmp_path):
    """E21 (part 5): with the real manifest the `search` gate is in `gates on`; a profile that switches it off moves
    it to `gates off`, and nothing else moves. Catches: a gate whose switch the start block does not show."""
    root = task_root(tmp_path)
    block = _block(root)
    assert "search" in _names(_line(block, "gates on:")) and "search" not in _names(_line(block, "gates off:"))
    profile = _profile(root)
    profile["gates"] = {"search": {"on": False}}
    block = _block(root, profile)
    assert _names(_line(block, "gates off:")) == ["search"]
    assert "search" not in _names(_line(block, "gates on:"))


def test_the_start_block_counts_the_ledger_rows(tmp_path):
    """E22 (part 5): when the ledger file exists the block has one line `ledger: N rows, M in force` (a row whose status
    is superseded or withdrawn is not in force); with no file there is no such line; an empty file is 0 rows. Catches:
    a ledger nobody is told about, or a count that includes closed decisions as live."""
    ledger = importlib.import_module("ledger")
    root = task_root(tmp_path)
    assert not [l for l in _block(root).splitlines() if l.startswith("ledger:")]
    for status in ("in force", "superseded", "withdrawn", "in force", "in force"):
        ledger.add(root, _profile(root), card="C", topic="t", quote="q", source="s", status=status)
    assert _line(_block(root), "ledger:") == "ledger: 5 rows, 3 in force"
    (root / "mkway" / "ledger" / "ledger.md").write_text("## Ledger\n", encoding="utf-8")
    assert _line(_block(root), "ledger:") == "ledger: 0 rows, 0 in force"


def _section():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves this out
def test_the_readme_has_one_section_decisions_search_before_asking():
    """E23 (part 6): one section `## Decisions: search before asking` with a body that names both commands, the
    ledger file and the search record file, the rule, every reason id of the `search` gate (read from the manifest),
    the lines of an ask (`ledger: N hits`, `> ledger: <verbatim>`, `ledger: 0 hits`, `search: <record id>`), the keys
    it reads and the start block line. Catches: a section that describes a gate or a command the engine does not
    have, or leaves out a refusal a session will meet."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert text.count("\n" + HEADING + "\n") == 1
    flat = " ".join(_section().split())
    assert len(flat) > 400
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    reasons = {r for e in manifest if e["gate"] == "search" for r in e["reason_ids"]}
    assert reasons == {"search-missing", "search-unverified"}
    for reason in reasons:
        assert f"`{reason}`" in flat, reason
    for needed in ("`mkway ledger add --card <id> --topic <text> --quote <verbatim> --source <text>`",
                   "`mkway search <words>`", "`<bundle.root>/ledger/ledger.md`", "`<state.dir>/searches.jsonl`",
                   "`knowledge.files`", "`questions.files`", "`ids.decision_row`", "`owner_ask.sources`",
                   "`ledger: N hits`", "`> ledger: <verbatim>`", "`ledger: 0 hits`", "`search: <record id>`",
                   "`gates.search`", "`ledger: N rows, M in force`", "`AskUserQuestion`"):
        assert needed in flat, needed


def test_keys_md_names_what_the_ledger_reads():
    """E24 (part 6): the `owner_ask.sources` line of KEYS.md names `ledger` as its default; the lines of
    `knowledge.files`, `questions.files` and `ids.decision_row` name MW-008 as a reader. Catches: a default that is
    written down as the old one, or a key whose reader nobody can find."""
    added = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert added["owner_ask.sources"][1:3] == [NOW, "`owner_ask.sources`"]
    assert "`ledger`" in added["owner_ask.sources"][3] and "`review`" not in added["owner_ask.sources"][3]
    assert "MW-008" in added["owner_ask.sources"][4] and "ledger: N hits" in added["owner_ask.sources"][4]
    assert "MW-008" in added["questions.files"][4]
    profile = {unquote(r[1]): r for r in section_rows("Profile keys")}
    assert "MW-008" in profile["knowledge.files"][4] and "MW-008" in profile["ids.decision_row"][4]
