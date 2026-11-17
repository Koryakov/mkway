"""Card MW-021, rows E7 and E8: `mkway rules` and the start block line. Synthetic task roots only."""
import json

from _commit_fixture import git, make_task, save
from _engine import cli
import startline

RULES = {"cards": ["rules/*.md"], "test_for": "tests/rules/{id}/test_{id}.py"}
IDS = {"card_prefix": "CARD", "rule_card": "^K[0-9]{2}$"}


def _task(tmp_path, **over):
    over.setdefault("rules", RULES)
    over.setdefault("ids", IDS)
    return make_task(tmp_path, **over)


def _green(root, tree):
    row = {"time": "2026-11-11T00:00:00.000+00:00", "session": "s1", "tree": tree, "command": "x", "result": "pass",
           "duration_seconds": 1.0}
    with (root / "mkway" / "state" / "commit_tests.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_rules_lists_each_card_with_its_test_and_its_last_green_tree(tmp_path):
    """Catches: a listing that calls a card tested when its test file is gone, or a green tree taken from a failed run (E7)."""
    root = _task(tmp_path)
    save(root, "rules/K01.md")
    save(root, "tests/rules/K01/test_K01.py")
    first = git(root, "rev-parse", "HEAD^{tree}").strip()
    save(root, "rules/K02.md")
    second = git(root, "rev-parse", "HEAD^{tree}").strip()
    _green(root, first)
    _green(root, second)
    with (root / "mkway" / "state" / "commit_tests.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"tree": "f" * 40, "result": "fail", "command": "x"}) + "\n")
    code, out, _err = cli(root, "rules")
    assert code == 0
    rows = {line.split()[0]: line.split() for line in out.splitlines() if line.strip()}
    assert rows["K01"] == ["K01", "rules/K01.md", "tests/rules/K01/test_K01.py", "exists", "last", "green", "tree",
                           second[:8]]
    assert rows["K02"] == ["K02", "rules/K02.md", "tests/rules/K02/test_K02.py", "missing", "last", "green", "tree",
                           "none"]
    assert code == 0
    assert cli(root, "rules", session=True)[0] == 0  # a session may run it: it only reads


def test_rules_says_what_to_set_when_the_check_is_off(tmp_path):
    """Catches: an empty answer that reads as «no rule cards» when the keys are unset (E7)."""
    root = _task(tmp_path, rules={})
    code, out, _err = cli(root, "rules")
    assert code == 0
    assert "rules.cards" in out
    assert "rules.test_for" in out
    assert "not set" in out


def test_the_start_block_counts_the_cards_and_the_ones_without_tests(tmp_path):
    """Catches: a start block that hides a rule card with no test, or shows its line with the keys not set (E8)."""
    root = _task(tmp_path)
    save(root, "rules/K01.md")
    save(root, "tests/rules/K01/test_K01.py")
    save(root, "rules/K02.md")
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    text = startline.render(root, root / "mkway" / "profile.json", profile, [], [], {})
    assert "rules: 2 cards, 1 without tests" in text.splitlines()
    off = dict(profile, rules={})
    assert not [x for x in startline.render(root, root / "mkway" / "profile.json", off, [], [], {}).splitlines()
                if x.startswith("rules:")]
