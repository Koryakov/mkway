"""Card MW-116: the manifest entry of the hook, the shipped template of the reader agent, the concept rows, the wording line, the
README section, the register row and the changelog line. The reasons are read from the manifest and the concept table, so
the text cannot drift from them. Synthetic text only."""
import json

import pytest

from _engine import REPO
import concept
import verdicts

WORDING = "the test file and the Acceptance rows of the named nodes only"
IDS = ("reader-read-refused", "reader-busy", "verdict-reader-unguarded")


def _manifest():
    return json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]


def test_the_manifest_lists_the_hook_as_a_frontmatter_entry_with_its_reasons():
    """Catches: a hook that lives only in an agent file: the manifest names it with the kind frontmatter, so the install test
    knows it is not in settings, and lists the three reason ids."""
    found = [e for e in _manifest() if e["name"] == "reader_allowlist"]
    assert len(found) == 1
    entry = found[0]
    assert entry["frontmatter"] is True and entry["event"] == "PreToolUse" and entry["class"] == "integrity"
    assert entry["function"] == "reader_hook:main"
    assert sorted(entry["reason_ids"]) == sorted(IDS)


@pytest.mark.parametrize("reason", IDS)
def test_each_new_id_is_a_k3_row_with_a_way_out_test(reason):
    """Catches: a refusal with no concept row or with no way-out test (a gap): each id is kind K3 and names a test node."""
    row = concept.REASONS[reason]
    assert row.kind_or_exit == "K3" and row.gap is None and row.way_out and row.way_out.startswith("tests/")


def test_the_lease_takeover_id_is_a_record_row_of_block_7_with_its_test():
    """Catches: the takeover record with no concept row, or counted as a gap: the id is a record of card 7 and names the test
    of the takeover as its way out (R295)."""
    row = concept.REASONS["reader-lease-expired"]
    assert (row.kind_or_exit, row.card, row.gap) == ("record", 7, None)
    assert row.way_out == ("tests/shell/test_mw116_reader_lease_shell.py::"
                           "test_a_lock_older_than_thirty_minutes_is_taken_over_and_the_takeover_is_recorded")


def test_the_template_is_a_read_only_reader_with_the_frontmatter_hook():
    """Catches: a shipped reader that may use more than Read and Grep, or that has no PreToolUse hook running the allowlist
    script, or whose hook is limited to some tools."""
    text = (REPO / "engine" / "templates" / "fresh-reader.md").read_text(encoding="utf-8")
    assert verdicts.parse_tools(text) == ("Read", "Grep")
    assert "name: fresh-reader" in text and "hooks:" in text and "PreToolUse:" in text
    assert "reader_hook.py" in text
    assert 'matcher: "*"' in text


def test_the_concept_page_has_the_wording_line_under_k3():
    """Catches: the reader's inputs stated nowhere on the page every session reads first."""
    text = (REPO / "engine" / "CONCEPT.md").read_text(encoding="utf-8")
    k3 = text.split("- **K3**", 1)[1].split("- **K4**", 1)[0]
    assert "the reader reads the test file and the Acceptance rows of the named nodes only" in k3


@pytest.mark.engine_repo  # README.md is not in an engine copy
def test_the_readme_states_the_inputs_the_commands_the_ids_the_trust_step_and_the_scope():
    """Catches: a rule whose text lives only in code: the README gives the wording, both commands, the three ids, the trust
    dialog with the quote of the platform documentation, and that a reader of outbox texts is out of scope."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    body = " ".join(text.split("## The reader's allowlist", 1)[1].split("\n## ", 1)[0].split())  # line breaks are layout
    for needed in (WORDING, "mkway reader start", "mkway reader end", "reader-busy", "reader-read-refused",
                   "verdict-reader-unguarded", "workspace trust dialog", "SubagentHandback",
                   "These hooks only run while that specific subagent is active and are cleaned up when it finishes.",
                   "A reader of outbox texts is out of scope"):
        assert needed in body, needed

