"""Card MW-112, the never-weaker exemption of a removed refusal (ruling R269c): a refusal may disappear in a commit only when
its row in the base table is an exit row whose card number is this card, and the replacing role-file line exists in the same
commit or earlier. The rule keys on the table: the base table is read from the card's base commit, never from a list written
here. Ruling R284 removes none: the tool ids keep their errors and the two drop-path rows keep refusing. Reads git at a pinned
commit (read form only); synthetic data only."""
import ast
import re
import subprocess
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import concept

REPO = Path(__file__).resolve().parents[1]
BASE = "6c3b48b"  # term-scan: allow the pinned base commit of this card (master after wave A), read only
KINDS = {"K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8"}
THIS_CARD = 7


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
    assert done.returncode == 0, (f"the base commit {BASE} of card MW-112 is not in this checkout, so the base table cannot "
                                  f"be read: {done.stderr.strip()[:200]}")  # a rule that cannot run is a failure, never a skip
    return _rows(done.stdout)


def _has_role_line(reason):
    return any(f"[{reason}]" in p.read_text(encoding="utf-8") for p in (REPO / "engine" / "roles").glob("*.md"))


def test_a_removed_refusal_had_an_instruction_row_of_this_card_and_its_role_line_exists(base_rows):
    """Catches: a refusal that left the engine while its base row was a kind row, an exit row of another card, or an
    instruction row of this card with no role-file line to replace it (the rule keys on the table, never on a hand list)."""
    removed = sorted(set(base_rows) - set(concept.REASONS))
    bad = [i for i in removed if not (base_rows[i] == ("instruction", THIS_CARD) and _has_role_line(i))]
    assert bad == []


def test_this_card_removes_no_refusal(base_rows):
    """Catches: R284: a refusal that disappeared although the ruling keeps every one (the tool ids keep their errors)."""
    assert sorted(set(base_rows) - set(concept.REASONS)) == []


def test_no_kind_row_of_the_base_table_changes_its_kind(base_rows):
    """Catches: a hard stop (a kind row) turned into an exit row or another kind: never weaker."""
    changed = sorted(i for i, (kind, _card) in base_rows.items() if kind in KINDS and concept.REASONS[i].kind_or_exit != kind)
    assert changed == []


def test_the_exit_rule_fails_and_does_not_skip_when_the_base_commit_is_missing():
    """Catches: the rule skipping silently when the base commit is not in the checkout, so a clone without it passes with no
    proof: the fixture asserts on the git result and has no skip call."""
    source = Path(__file__).read_text(encoding="utf-8")
    fixture = source.split("def base_rows", 1)[1].split("def _has_role_line", 1)[0]
    assert "pytest.skip" not in fixture
    assert "returncode == 0" in fixture


def test_every_instruction_row_of_the_table_keeps_a_role_line():
    """Catches: R269c: an instruction row of this card whose role-file line was removed, so nothing replaces its hook."""
    missing = [i for i, row in concept.REASONS.items() if row.kind_or_exit == "instruction" and not _has_role_line(i)]
    assert missing == []
    assert re.fullmatch(r"[0-9a-f]{7}", BASE)
