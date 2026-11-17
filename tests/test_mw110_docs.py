"""Card MW-110: the profile key of the transition date, the README section «Messaging order», the register row, the
changelog line. The reasons and the key are read from the manifest and the schema, so the text cannot drift from them.
Synthetic text only."""
import json

import pytest

import _docs as docs
from _engine import REPO, make_profile
from _keys_md import section_rows, unquote
import profiles

pytestmark = pytest.mark.engine_repo

TITLE = "the send tool: a session sends with one engine call and no one-use permit"
KEY = "session_id_watch_until"


def test_the_schema_holds_the_watch_date_as_a_text_key():
    """Catches: a transition date the schema refuses (the owner could not set it) or one typed as a number."""
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    prop = schema["properties"]["messaging"]["properties"][KEY]
    assert prop["type"] == "string"
    assert profiles.validate(make_profile(messaging={KEY: "2026-12-31"})) == []
    assert profiles.validate(make_profile(messaging={KEY: 5})) != []


@pytest.mark.parametrize("value, expected", [
    pytest.param(None, "", id="absent"),
    pytest.param("", "", id="empty"),
    pytest.param("2026-12-31", "2026-12-31", id="a-date"),
    pytest.param("next week", "", id="not-an-iso-date"),
    pytest.param("2026-13-45", "", id="not-a-calendar-date"),
    pytest.param(20261231, "", id="a-number"),
    pytest.param(True, "", id="a-boolean"),
])
def test_the_accessor_reads_a_date_or_nothing(value, expected):
    """Catches: an unusable value that fails the gate: this accessor reads a date or nothing (R279c Q2: the value that cannot
    be read is not hidden as no expiry here, `session_id_watch_unreadable` returns it and the period counts as passed)."""
    profile = make_profile(messaging={} if value is None else {KEY: value})
    assert profiles.session_id_watch_until(profile) == expected


def test_the_accessor_reads_empty_for_no_profile():
    """Checks: a profile that is not an object reads as no expiry, as every accessor does."""
    assert profiles.session_id_watch_until(None) == ""


def test_keys_md_names_the_key_with_its_default():
    """Catches: a key the owner cannot find: KEYS.md has one row with the key and its default (empty)."""
    rows = [r for r in section_rows("Added keys") if unquote(r[0]) == "messaging.session_id_watch_until"]
    assert len(rows) == 1
    assert "empty" in rows[0][3]


def test_the_readme_states_the_session_id_and_the_launcher_line():
    """Catches: a send tool whose rule lives only in code: the README names the variable, both reasons, the launcher
    line, the key of the transition and the state of mkcl's part."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    body = text.split("## Messaging order", 1)[1].split("\n## ", 1)[0]
    missing = [needed for needed in (
        "MKWAY_SESSION_ID", "`session-id-mismatch`", "`session-id-unset`", "--session-id",
        "`messaging.session_id_watch_until`", "checked with mkcl 0.7.0 in pwsh 7 and 5.1; live when mkcl 0.7.0 is live",
        "free text", "`message-not-in-inbox` is removed") if needed not in body]
    assert missing == []


CONTRACT = "`SESSION_ENV` is the engine's contract with the launcher"


def test_the_readme_states_the_proof_the_new_refusal_and_the_record():
    """Catches: the R279 rules living only in code: the README says the permit is the proof, that the variable alone counts
    only before the end date, names `session-id-unverified` with its way out, the record of sends and acks, and that the
    variable name is the launcher contract (one module constant, no profile key)."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    body = " ".join(text.split("## Messaging order", 1)[1].split("\n## ", 1)[0].split())
    missing = [needed for needed in (
        "`session-id-unverified`", "one-use permit is the proof", "variable alone", "message-record.jsonl",
        "a session with the hooks", CONTRACT) if needed not in body]
    assert missing == []


def test_the_readme_states_the_per_session_permit_the_unreadable_date_and_the_record_first_rule():
    """Catches: the R279c rules living only in code: the README says the permit is written under the session's own id and
    opened by the variable, that with no variable only the most recent permit is taken and only before the end date, that a
    date that cannot be read counts as passed, and that the record is written first (`send-record-failed`)."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    body = " ".join(text.split("## Messaging order", 1)[1].split("\n## ", 1)[0].split())
    missing = [needed for needed in (
        "`permits/<session id>.json`", "opens only its own file", "most recent permit", "counts as passed",
        "`send-record-failed`", "record is written first", "nothing is delivered") if needed not in body]
    assert missing == []


def test_keys_md_names_the_launcher_contract():
    """Catches: a variable name that looks like project configuration: KEYS.md says it is the engine's contract with the
    launcher and stays a module constant, so no profile key is looked for."""
    flat = " ".join((REPO / "engine" / "KEYS.md").read_text(encoding="utf-8").split())
    assert CONTRACT in flat
    assert "module constant" in flat


CARD = REPO / "cards" / "MW-110-send-tool" / "CARD.md"


def test_the_card_log_records_the_fix_round():
    """Checks: the Log names the rulings and the decision of the fix round, the supersede note of R189 (3) and R197 B, the
    block 7 line, and says that the lock gate answers first for a double-quoted text."""
    log = CARD.read_text(encoding="utf-8").split("## 8. Log", 1)[1]
    needed = ("R279", "R279a", "MW110-D3", "R189 (3)", "R197 B", "superseded",
              "block 7, one record row, by card 5; block 7 has no open editor", "the lock gate answers first")
    assert [n for n in needed if n not in log] == []


def test_row_e18_names_the_count_it_really_has():
    """Catches: a card row that counts twelve shapes where the test has six (a hook does not see the age of a permit): the
    row says six and the test holds six."""
    row = next(line for line in CARD.read_text(encoding="utf-8").splitlines() if line.startswith("| E18 |"))
    assert "twelve" not in row
    assert "six" in row


def test_keys_md_says_an_unreadable_value_counts_as_passed():
    """Catches: a KEYS.md row that still says an unusable value reads as no expiry: R279c Q2 says it counts as passed."""
    rows = [r for r in section_rows("Added keys") if unquote(r[0]) == "messaging.session_id_watch_until"]
    assert len(rows) == 1
    assert "counts as passed" in rows[0][4]
    assert "reads as empty" not in rows[0][4]


def test_the_card_records_the_approved_files_and_the_rulings_of_round_two():
    """Checks: the Paths name the four files the orderer approved for R279c (core_lock, gate_lock, startline, install) and
    the Log cites R279b, R279c and the approval."""
    card = CARD.read_text(encoding="utf-8")
    paths = next(line for line in card.splitlines() if line.startswith("| **Paths**"))
    log = card.split("## 8. Log", 1)[1]
    assert [f for f in ("engine/core_lock.py", "engine/gate_lock.py", "engine/startline.py", "engine/install.py")
            if f not in paths] == []
    assert [f for f in ("R279b", "R279c", "approved") if f not in log] == []


def test_the_hook_shapes_file_counts_six_shapes_not_twelve():
    """Catches: a docstring that counts twelve replay shapes where the file holds six (send, inbox and ack, plain and chained)."""
    import ast
    source = (REPO / "tests" / "shell" / "test_mw110_hook_shapes_shell.py").read_text(encoding="utf-8")
    doc = " ".join(ast.get_docstring(ast.parse(source)).split())
    assert "twelve" not in doc
    assert "six replay shapes" in doc


def test_register_changelog_and_card_name_the_card():
    """Checks: a register row, a CHANGELOG line in exactly one release section, the card folder; VERSION is not changed here."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert f"| MW-110 | {TITLE} |" in register
    assert (REPO / "cards" / "MW-110-send-tool" / "CARD.md").is_file()
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"- MW-110: {TITLE}" in docs.changelog_section(changelog, "MW-110")
