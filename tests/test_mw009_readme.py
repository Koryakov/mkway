"""The README section «Deletes» and the start line's gates (card MW-009, part P6)."""
import json
import re

import pytest

from _engine import REPO, task_root
import dispatch
from test_mw007_start_block import _block, _line, _names, _set_gates

README = REPO / "README.md"
HEADING = "## Deletes"


def _text():
    return README.read_text(encoding="utf-8")


def _section():
    text = _text()
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def _flat(text):
    return " ".join(text.split())


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out (as test_register does)
def test_the_readme_has_one_section_deletes():
    """E31 (part 6): one heading `## Deletes`, with a body, and no other heading about deletes. Catches: a second
    section, or a heading with no text."""
    text = _text()
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_flat(_section())) > 1500
    assert len([h for h in re.findall(r"^## .*$", text, re.M) if "delete" in h.lower()]) == 1


@pytest.mark.engine_repo
def test_the_section_states_the_rules_reasons_keys_commands_and_limits():
    """E32 (part 6): the section names every reason id of the entry `delete` (read from the manifest), both keys with
    their defaults (read from the schema), the switch, the trash folder and the record file, the list command with its
    bad-line rule, the two owner-only trash commands, the start line's `gates off:`, the `CLAUDECODE` tripwire and the
    limits (SQL from a file, an encoded command, other git forms, the owner's terminal). Catches: a section that
    describes a gate the engine does not have, or leaves out a refusal a session will meet."""
    flat = _flat(_section())
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    reasons = {r for e in manifest if e["gate"] == "delete" for r in e["reason_ids"]}
    assert len(reasons) == 8
    for reason in reasons:
        assert f"`{reason}`" in flat, reason
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    for key in schema["properties"]["delete"]["properties"]:
        assert f"`delete.{key}`" in flat, key
    for needed in ("(default `5120`", "(default `false`", "`gates.delete`", "`gates off:`", "`gates on:`",
                   "`<state.dir>/trash/<timestamp>/<repo path>`", "`<state.dir>/deletes.jsonl`",
                   "`mkway delete --list <file>`", "`mkway trash list`", "`mkway trash empty --older-than <days>`",
                   "`CLAUDECODE`", "`via: list`", "`via: trash-empty`", "`git rm --cached`", "`git clean`",
                   "`git reset --hard`", "`vcs: git`", "`onFailure: block`", "never empties the trash by itself",
                   "Any bad line deletes nothing", "SQL read from a file or stdin is not seen",
                   "an encoded command is not read", "the owner's own terminal runs no hook"):
        assert needed in flat, needed


def test_the_start_line_names_the_delete_gate_on_and_off(tmp_path):
    """E33 (part 6): with the real manifest the entry `delete` is on the start block's `gates on:`; with
    `gates.delete.on: false` it is on `gates off:` and nothing else changes. Catches: a gate that was switched off and
    that nothing on the start block says."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    loaded = [e["name"] for e in manifest if e.get("function") and e.get("reason_ids")]
    assert "delete" in loaded
    root = task_root(tmp_path)
    block = _block(root, manifest)
    assert "delete" in _names(_line(block, "gates on:")) and _line(block, "gates off:") == "gates off: none"
    profile = _set_gates(root, {"delete": {"on": False}})
    block = _block(root, manifest, profile)
    assert _names(_line(block, "gates off:")) == ["delete"]
    assert "delete" not in _names(_line(block, "gates on:"))
