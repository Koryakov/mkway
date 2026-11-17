"""Card MW-110, the never-weaker exemption of a removed refusal (ruling R269c): a refusal may disappear in a commit only
when its row in the reason table (`engine/concept.py`) is an exit row with a card number, and the tool that replaces it
exists in the same commit or earlier. The rule keys on the table: the base table is read from the card's base commit,
never from a list written here. Reads git at a pinned commit (read form only); synthetic data only."""
import ast
import subprocess
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import concept
import mkway

REPO = Path(__file__).resolve().parents[1]
BASE = "52c6e65"  # term-scan: allow the pinned base commit of this card (card 1's merge), read only
EXITS = {"tool", "instruction", "remove", "record"}
THIS_CARD = 5


def _rows(source):
    """{reason id: (kind_or_exit, card)} of the REASONS dict literal of a concept.py source, read with ast."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "REASONS":
            return {key.value: tuple(ast.literal_eval(arg) for arg in value.args[:2])
                    for key, value in zip(node.value.keys, node.value.values)}
    raise AssertionError("no REASONS table in the base concept.py")


@pytest.fixture(scope="module")
def base_rows():
    done = subprocess.run(["git", "--no-optional-locks", "show", f"{BASE}:engine/concept.py"], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, (f"the base commit {BASE} of card MW-110 is not in this checkout, so the base table cannot "
                                  f"be read: {done.stderr.strip()[:200]}")  # a rule that cannot run is a failure, never a skip
    return _rows(done.stdout)


@pytest.mark.engine_repo  # MW127-D1 (1): reads the pinned base commit, which only the engine repository holds; a task copy runs -m "not engine_repo"
def test_a_removed_refusal_had_an_exit_row_of_this_card(base_rows):
    """Catches: a refusal that left the engine while its row in the base table was a kind row, had no card number, or
    belonged to another card (R279: THIS card, not any card 2 to 8); and a card that removes nothing (the rule would then
    test nothing)."""
    removed = sorted(set(base_rows) - set(concept.REASONS))
    not_this_card = [i for i in removed if not (base_rows[i][0] in EXITS and base_rows[i][1] == THIS_CARD)]
    assert not_this_card == []
    assert removed != []


def test_the_exit_rule_fails_and_does_not_skip_when_the_base_commit_is_missing():
    """Catches: the rule skipping silently when the base commit is not in the checkout, so a clone without it passes with no
    proof: the fixture asserts on the git result and has no skip call."""
    source = Path(__file__).read_text(encoding="utf-8")
    fixture = source.split("def base_rows", 1)[1].split("def test_", 1)[0]
    assert "pytest.skip" not in fixture
    assert "returncode == 0" in fixture


def test_the_replacing_send_command_exists_with_its_file_form():
    """Checks: the tool that replaces the removed refusal is in this commit: `send` parses with `--file`, and the id it
    sends from is read from the launcher's environment variable."""
    args = mkway._parser().parse_args(["send", "--to", "x", "--kind", "notice", "--file", "body.txt"])
    assert (args.command, args.to, args.kind, args.file) == ("send", "x", "notice", "body.txt")
    assert "SESSION_ENV" in Path(mkway.__file__).read_text(encoding="utf-8").split("def _message_session")[1].split("def _ack")[0]
