"""Card MW-021, rows E4 to E6: the commit check `rule-without-test` of the gate `commit_files`. Synthetic task roots,
real throwaway git repositories; the gate is called with the dispatcher's own context."""
import json
from pathlib import Path

from _commit_fixture import COMMIT, check, git, make_task, reason, save, stage, touch, work

RULES = {"cards": ["rules/*.md"], "test_for": "tests/rules/{id}/test_{id}.py"}
IDS = {"card_prefix": "CARD", "rule_card": "^K[0-9]{2}$"}
PATHS = "`rules/`, `tests/rules/`, `notes/`"  # `tests/` itself is a test root: `card open` refuses it as too wide
CARD, TEST = "rules/K01.md", "tests/rules/K01/test_K01.py"


def _task(tmp_path, **over):
    over.setdefault("rules", RULES)
    over.setdefault("ids", IDS)
    return make_task(tmp_path, card_paths=PATHS, **over)


def _known(root, *rels):
    for rel in rels:
        work(root, rel)
    touch(root, *rels)
    stage(root, *rels)


def test_a_new_rule_card_with_no_test_file_is_refused(tmp_path):
    """E4: a commit that adds a rule card whose test file does not exist is refused `rule-without-test`; the text names
    the card, the test path, says the file does not exist and names the command that fixes it.
    Catches: a rule card that lands with no test behind it, or a refusal that names no way out."""
    root = _task(tmp_path)
    _known(root, CARD)
    v = check(root, COMMIT)
    assert reason(v) == "rule-without-test"
    assert CARD in v.message and TEST in v.message and "does not exist" in v.message
    assert f"git add {TEST}" in v.message
    _known(root, TEST)
    assert reason(check(root, COMMIT)) == "allow"


def test_a_changed_card_needs_its_test_staged_too(tmp_path):
    """E5: a commit that changes a card whose test file exists in the tree is refused while the test is not staged (new
    or changed); staging the test, changed, allows it. The text says the test is not staged and names `git add`.
    Catches: a card edited with its test left as it was."""
    root = _task(tmp_path)
    save(root, CARD)
    save(root, TEST)
    work(root, CARD, "changed\n")
    touch(root, CARD)
    stage(root, CARD)
    v = check(root, COMMIT)
    assert reason(v) == "rule-without-test" and "not staged" in v.message and f"git add {TEST}" in v.message
    work(root, TEST, "changed\n")
    touch(root, TEST)
    stage(root, TEST)
    assert reason(check(root, COMMIT)) == "allow"


def test_the_named_paths_form_is_read_too(tmp_path):
    """E5: with `-- <paths>` the files taken are the named ones; the card alone is refused, the card and its test
    allowed. Catches: a check that reads only the index and misses the pathspec form."""
    root = _task(tmp_path)
    save(root, CARD)
    save(root, TEST)
    for rel in (CARD, TEST):
        work(root, rel, "changed\n")
        touch(root, rel)
    assert reason(check(root, f"{COMMIT} -- {CARD}")) == "rule-without-test"
    assert reason(check(root, f"{COMMIT} -- {CARD} {TEST}")) == "allow"


def test_what_is_allowed(tmp_path):
    """E6: a test changed without its card, a deleted card, a file that matches no card glob, a card file with no id of
    the `ids.rule_card` form: all allowed. Catches: a rule that refuses more than a card changed without a test."""
    root = _task(tmp_path)
    save(root, CARD)
    save(root, TEST)
    work(root, TEST, "changed\n")
    touch(root, TEST)
    stage(root, TEST)
    assert reason(check(root, COMMIT)) == "allow"  # a test changed without its card
    git(root, "restore", "--staged", "--", TEST)
    touch(root, CARD)  # the removal is this session's own write, so the ride-in rule has nothing to say
    git(root, "rm", "-q", "--", CARD)
    assert reason(check(root, COMMIT)) == "allow"  # a deleted card
    git(root, "reset", "-q")
    _known(root, "notes/K01.md", "rules/notes.md")  # outside the glob; inside the glob but no id in its name
    assert reason(check(root, COMMIT)) == "allow"


def test_the_check_is_off_without_both_keys_and_without_the_id_form(tmp_path):
    """E6: with no `rules` keys, with only one of them, or with no `ids.rule_card`, a rule-card file commits as any
    other. Catches: a check that bites a branch that never configured it."""
    for name, over in (("none", {"rules": {}}), ("cards-only", {"rules": {"cards": RULES["cards"]}}),
                       ("test-only", {"rules": {"test_for": RULES["test_for"]}}),
                       ("no-id-form", {"ids": {"card_prefix": "CARD"}})):
        root = _task(tmp_path, name=name, **over)
        _known(root, CARD)
        assert reason(check(root, COMMIT)) == "allow", name


def test_the_manifest_declares_the_reason_in_the_integrity_commit_gate():
    """E6: the entry `commit_files` (class integrity, as MW-006) declares `rule-without-test`. Catches: a reason the
    gate returns that the manifest does not declare."""
    repo = Path(__file__).resolve().parents[1]
    entries = {e["name"]: e for e in json.loads((repo / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]}
    assert entries["commit_files"]["class"] == "integrity"
    assert "rule-without-test" in entries["commit_files"]["reason_ids"]
